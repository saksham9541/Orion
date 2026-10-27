"""
Orion — Department Agents for Railway Maintenance.
Represents individual railway departments:
- Engineering (Track/Civil)
- S&T (Signaling & Telecom)
- TRD (Traction Distribution / OHE)

Each agent advocates for its department's operational constraints, packages
backlog defects into coherent block requests, and evaluates flexibility for merging.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Dict, List, Optional

from railopt.models import (
    BlockType,
    BlockWindow,
    DefectSeverity,
    Department,
    MaintenanceTask,
    Section,
    TaskStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class DepartmentProposal:
    """A proposed block request formulated by a DepartmentAgent."""
    proposal_id: str
    department: Department
    section_id: str
    corridor_id: str
    target_date: date
    preferred_window_id: str
    start_time: time
    end_time: time
    requested_duration_hours: float
    task_ids: List[str]
    total_urgency_score: float
    has_emergency: bool
    requires_power_block: bool
    requires_traffic_block: bool
    crew_size_needed: int
    flexibility: float = 0.5  # 0.0 (strictly rigid) to 1.0 (highly willing to share/shift)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DepartmentAgent:
    """
    Autonomous representative for a railway maintenance department.
    Evaluates backlog defects, enforces departmental constraints, and
    negotiates for maintenance block access.
    """

    def __init__(self, department: Department):
        self.department = department
        self.name = f"{department.value} Agent"
        self._init_domain_profile()

    def _init_domain_profile(self) -> None:
        """Sets domain operational characteristics."""
        if self.department == Department.ENGINEERING:
            # Heavy machinery, track tamping, rail replacement
            self.max_daily_blocks = 5
            self.standard_crew_size = 8
            self.default_flexibility = 0.6  # Can readily share track closure with S&T
            self.primary_block_type = BlockType.TRAFFIC_BLOCK
        elif self.department == Department.SNT:
            # Signal testing, point machines, axle counters, track circuits
            self.max_daily_blocks = 6
            self.standard_crew_size = 4
            self.default_flexibility = 0.8  # High flexibility to tag along with Engineering
            self.primary_block_type = BlockType.NON_TRAFFIC
        elif self.department == Department.TRD:
            # OHE mast, catenary wire, power feeder isolation
            self.max_daily_blocks = 4
            self.standard_crew_size = 6
            self.default_flexibility = 0.4  # Strict due to power isolation switching protocols
            self.primary_block_type = BlockType.POWER_BLOCK
        else:
            self.max_daily_blocks = 4
            self.standard_crew_size = 4
            self.default_flexibility = 0.5
            self.primary_block_type = BlockType.TRAFFIC_BLOCK

    def filter_department_tasks(self, tasks: List[MaintenanceTask]) -> List[MaintenanceTask]:
        """Returns pending tasks belonging to this department."""
        return [
            t for t in tasks
            if t.department == self.department
            and t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED, TaskStatus.UNVERIFIED)
        ]

    def score_task_urgency(self, task: MaintenanceTask) -> float:
        """
        Internal departmental urgency scoring.
        Blends safety criticality, days overdue, ML criticality, and recurrence.
        """
        score = task.ml_criticality_score or 20.0

        if task.ml_predicted_severity == DefectSeverity.EMERGENCY or task.raw_severity == "EMERGENCY":
            score = max(score, 98.0)
        elif task.is_safety_critical:
            score = max(score, 75.0)

        # Departmental penalties
        if task.days_overdue > 0:
            score += min(task.days_overdue * 2.0, 20.0)

        if task.historical_failure_count > 0:
            score += min(task.historical_failure_count * 3.0, 15.0)

        # TRD specific: power block necessity escalates urgency when deferred
        if self.department == Department.TRD and task.requires_power_block and task.deferred_count > 0:
            score += 10.0

        return round(min(score, 100.0), 1)

    def formulate_proposals(
        self,
        tasks: List[MaintenanceTask],
        available_windows: List[BlockWindow],
        sections: Dict[str, Section],
    ) -> List[DepartmentProposal]:
        """
        Packages prioritized departmental tasks into optimal block proposals.
        Groups tasks by section and matches them with suitable block windows.
        """
        dept_tasks = self.filter_department_tasks(tasks)
        if not dept_tasks:
            return []

        # Sort tasks by internal urgency descending
        scored_tasks = [(t, self.score_task_urgency(t)) for t in dept_tasks]
        scored_tasks.sort(key=lambda x: x[1], reverse=True)

        # Group by (corridor_id, section_id)
        section_groups: Dict[tuple[str, str], List[tuple[MaintenanceTask, float]]] = {}
        for t, s in scored_tasks:
            key = (t.corridor_id, t.section_id)
            section_groups.setdefault(key, []).append((t, s))

        proposals: List[DepartmentProposal] = []

        # Windows indexed by section
        windows_by_section: Dict[str, List[BlockWindow]] = {}
        for w in available_windows:
            windows_by_section.setdefault(w.section_id, []).append(w)

        for (corridor_id, section_id), group_tasks in section_groups.items():
            candidate_windows = windows_by_section.get(section_id, [])
            if not candidate_windows:
                # If no pre-assigned window for section, pick any window on the corridor
                candidate_windows = [w for w in available_windows if w.corridor_id == corridor_id]
            if not candidate_windows:
                continue

            # Pick top tasks up to capacity (max 4 per single proposal)
            batch = group_tasks[:4]
            task_objs = [item[0] for item in batch]
            urgency_sum = sum(item[1] for item in batch)
            has_emergency = any(item[1] >= 95.0 for item in batch)

            # Determine aggregate requirements
            duration_needed = max(t.estimated_duration_hours for t in task_objs)
            req_power = any(t.requires_power_block for t in task_objs)
            req_traffic = any(t.requires_traffic_block for t in task_objs)
            crew_size = max(t.crew_size_required for t in task_objs)

            # Match with best window (preferring long enough duration)
            chosen_window = candidate_windows[0]
            for w in candidate_windows:
                if w.duration_hours >= duration_needed:
                    chosen_window = w
                    break

            proposal = DepartmentProposal(
                proposal_id=f"PROP-{self.department.value[:3]}-{uuid.uuid4().hex[:6].upper()}",
                department=self.department,
                section_id=section_id,
                corridor_id=corridor_id,
                target_date=chosen_window.date,
                preferred_window_id=chosen_window.window_id,
                start_time=chosen_window.start_time,
                end_time=chosen_window.end_time,
                requested_duration_hours=min(duration_needed, chosen_window.duration_hours),
                task_ids=[t.task_id for t in task_objs],
                total_urgency_score=round(urgency_sum, 1),
                has_emergency=has_emergency,
                requires_power_block=req_power,
                requires_traffic_block=req_traffic,
                crew_size_needed=crew_size,
                flexibility=self.default_flexibility if not has_emergency else 0.1,
                metadata={
                    "task_count": len(task_objs),
                    "section_name": sections.get(section_id).name if section_id in sections else section_id,
                },
            )
            proposals.append(proposal)

        return proposals
