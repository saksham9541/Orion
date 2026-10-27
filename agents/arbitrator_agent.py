"""
Orion — Arbitrator Agent for Multi-Department Block Negotiation.
Resolves cross-departmental conflicts when Engineering, S&T, and TRD
proposals compete for the same track sections and windows.

Primary superpower: Block Merging — coordinates shared track closures,
eliminating redundant railway downtime while respecting departmental safety.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Dict, List, Optional, Set

from railopt.models import BlockType, Department, ScheduledBlock

from .department_agent import DepartmentProposal

logger = logging.getLogger(__name__)


@dataclass
class NegotiationAgreement:
    """Consensus agreement reached by the Arbitrator for a block window."""
    agreement_id: str
    section_id: str
    corridor_id: str
    target_date: date
    start_time: time
    end_time: time
    duration_hours: float
    participating_departments: List[Department]
    task_ids: List[str]
    is_merged: bool
    merge_savings_hours: float
    block_type: BlockType
    rationale: str
    window_id: str = ""
    concessions_made: List[str] = field(default_factory=list)


@dataclass
class ConflictResolution:
    """Detailed summary of conflict detection and resolution."""
    contested_section_id: str
    target_date: date
    competing_proposals: List[str]  # proposal_ids
    departments_involved: List[Department]
    resolution_type: str  # "MERGED" | "PRIORITY_AWARD" | "RESCHEDULED"
    explanation: str
    agreements_generated: List[str]  # agreement_ids


class ArbitratorAgent:
    """
    Arbitrates multi-department block requests, detecting conflicts and
    synthesizing optimal merged schedules.
    """

    def __init__(self):
        self.name = "Central Railway Traffic & Maintenance Arbitrator"

    def arbitrate(
        self,
        proposals: List[DepartmentProposal],
    ) -> tuple[List[NegotiationAgreement], List[ConflictResolution]]:
        """
        Main arbitration entrypoint.
        Groups proposals by section and date, resolves conflicts, and generates agreements.
        """
        if not proposals:
            return [], []

        # Group proposals by (section_id, target_date)
        bids_by_section_date: Dict[tuple[str, date], List[DepartmentProposal]] = {}
        for p in proposals:
            key = (p.section_id, p.target_date)
            bids_by_section_date.setdefault(key, []).append(p)

        agreements: List[NegotiationAgreement] = []
        resolutions: List[ConflictResolution] = []

        for (section_id, target_date), bids in bids_by_section_date.items():
            if len(bids) == 1:
                # No conflict — uncontested departmental proposal
                ag = self._create_single_agreement(bids[0])
                agreements.append(ag)
            else:
                # Conflict or Multi-Department Opportunity
                ag_list, cr = self._resolve_competing_bids(bids, section_id, target_date)
                agreements.extend(ag_list)
                if cr:
                    resolutions.append(cr)

        return agreements, resolutions

    def _create_single_agreement(self, p: DepartmentProposal) -> NegotiationAgreement:
        """Converts an uncontested proposal directly into an approved agreement."""
        block_type = BlockType.POWER_BLOCK if p.requires_power_block else (
            BlockType.TRAFFIC_BLOCK if p.requires_traffic_block else BlockType.NON_TRAFFIC
        )
        return NegotiationAgreement(
            agreement_id=f"AGR-{uuid.uuid4().hex[:8].upper()}",
            section_id=p.section_id,
            corridor_id=p.corridor_id,
            target_date=p.target_date,
            start_time=p.start_time,
            end_time=p.end_time,
            duration_hours=p.requested_duration_hours,
            participating_departments=[p.department],
            task_ids=list(p.task_ids),
            is_merged=False,
            merge_savings_hours=0.0,
            block_type=block_type,
            rationale=f"Direct approval: uncontested request from {p.department.value} for {len(p.task_ids)} tasks.",
            window_id=p.preferred_window_id,
            concessions_made=[],
        )

    def _resolve_competing_bids(
        self,
        bids: List[DepartmentProposal],
        section_id: str,
        target_date: date,
    ) -> tuple[List[NegotiationAgreement], Optional[ConflictResolution]]:
        """
        Evaluates competing proposals on the same section and date.
        Attempts Block Merging first; if incompatible, awards by priority.
        """
        depts_involved = list(set(p.department for p in bids))
        proposal_ids = [p.proposal_id for p in bids]

        # Check merge compatibility
        # On Indian Railways, Engineering track work, S&T signal checking,
        # and TRD overhead work on the same section can be merged into a unified possession.
        can_merge = self._check_merge_feasibility(bids)

        if can_merge:
            merged_agreement = self._build_merged_agreement(bids)
            cr = ConflictResolution(
                contested_section_id=section_id,
                target_date=target_date,
                competing_proposals=proposal_ids,
                departments_involved=depts_involved,
                resolution_type="MERGED",
                explanation=(
                    f"Successfully coordinated multi-department block merge for {', '.join(d.value for d in depts_involved)}. "
                    f"Combined separate closures into single {merged_agreement.duration_hours:.1f}h window, "
                    f"saving {merged_agreement.merge_savings_hours:.1f} hours of track downtime."
                ),
                agreements_generated=[merged_agreement.agreement_id],
            )
            return [merged_agreement], cr
        else:
            # Competing proposals cannot merge (e.g. conflicting physical machinery)
            # Award to highest urgency; reschedule lower
            sorted_bids = sorted(bids, key=lambda p: (p.has_emergency, p.total_urgency_score), reverse=True)
            winner = sorted_bids[0]
            concession_bids = sorted_bids[1:]

            winner_ag = self._create_single_agreement(winner)
            winner_ag.rationale = (
                f"Priority arbitration award: {winner.department.value} had higher urgency score "
                f"({winner.total_urgency_score:.1f}) against competing departments."
            )

            concessions = [
                f"{b.department.value} (Proposal {b.proposal_id}) deferred to next available maintenance slot"
                for b in concession_bids
            ]
            winner_ag.concessions_made = concessions

            cr = ConflictResolution(
                contested_section_id=section_id,
                target_date=target_date,
                competing_proposals=proposal_ids,
                departments_involved=depts_involved,
                resolution_type="PRIORITY_AWARD",
                explanation=(
                    f"Conflicting exclusive requests. Window awarded to {winner.department.value} due to higher urgency. "
                    f"Remaining {len(concession_bids)} requests queued for alternate scheduling."
                ),
                agreements_generated=[winner_ag.agreement_id],
            )
            return [winner_ag], cr

    def _check_merge_feasibility(self, bids: List[DepartmentProposal]) -> bool:
        """Determines if multiple bids can share the same window safely."""
        # Max 3 departments merged in a single block
        if len(bids) > 4:
            return False

        # If any proposal is ultra-inflexible with 0 flexibility and refuses merge
        if any(p.flexibility < 0.05 for p in bids):
            return False

        # If total tasks exceed 10, crowding risk prevents safety coordination
        total_tasks = sum(len(p.task_ids) for p in bids)
        if total_tasks > 10:
            return False

        return True

    def _build_merged_agreement(self, bids: List[DepartmentProposal]) -> NegotiationAgreement:
        """Combines multiple proposals into a single merged block agreement."""
        participating_depts = list(dict.fromkeys(p.department for p in bids))
        all_task_ids = []
        for p in bids:
            all_task_ids.extend(p.task_ids)

        # Unified duration is the max duration required by any participant
        max_duration = max(p.requested_duration_hours for p in bids)
        sum_separate = sum(p.requested_duration_hours for p in bids)
        merge_savings = round(max(0.0, sum_separate - max_duration), 1)

        # Block Type
        has_power = any(p.requires_power_block for p in bids)
        has_traffic = any(p.requires_traffic_block for p in bids)
        if has_power and has_traffic:
            block_type = BlockType.COMBINED
        elif has_power:
            block_type = BlockType.POWER_BLOCK
        else:
            block_type = BlockType.TRAFFIC_BLOCK

        ref_bid = bids[0]
        dept_names = ", ".join(d.value for d in participating_depts)

        return NegotiationAgreement(
            agreement_id=f"MRG-{uuid.uuid4().hex[:8].upper()}",
            section_id=ref_bid.section_id,
            corridor_id=ref_bid.corridor_id,
            target_date=ref_bid.target_date,
            start_time=ref_bid.start_time,
            end_time=ref_bid.end_time,
            duration_hours=max_duration,
            participating_departments=participating_depts,
            task_ids=all_task_ids,
            is_merged=True,
            merge_savings_hours=merge_savings,
            block_type=block_type,
            rationale=(
                f"Multi-department coordinated possession for {dept_names}. "
                f"Consolidated {len(all_task_ids)} tasks into a single {max_duration:.1f}h window."
            ),
            window_id=ref_bid.preferred_window_id,
            concessions_made=[
                f"{p.department.value} adjusted duration to shared window" for p in bids
            ],
        )
