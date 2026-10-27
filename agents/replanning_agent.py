"""
Orion — Replanning Agent for Dynamic Disruption & Emergency Schedule Repair.
Responds autonomously when unexpected defects (such as sudden rail fractures
or catenary wire breaks) occur mid-schedule, repairing the plan with minimum disruption.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional

from railopt.models import (
    BlockPlan,
    BlockType,
    DefectSeverity,
    Department,
    MaintenanceTask,
    ScheduledBlock,
    TaskStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ReplanResult:
    """Output from an autonomous replanning operation."""
    replan_id: str
    original_plan_id: str
    updated_plan: BlockPlan
    emergency_task_id: str
    assigned_block_id: str
    displaced_task_ids: List[str]
    unaffected_blocks_count: int
    mutated_blocks_count: int
    narrative_explanation: str


class ReplanningAgent:
    """
    Autonomous re-planning agent. Employs minimal-perturbation schedule repair
    so that operational crews and booked machinery on other corridors are not disturbed.
    """

    def __init__(self):
        self.name = "Dynamic Emergency Replanning Agent"

    def handle_emergency(
        self,
        current_plan: BlockPlan,
        emergency_task: MaintenanceTask,
        all_tasks: List[MaintenanceTask],
    ) -> ReplanResult:
        """
        Repairs current_plan around emergency_task.
        """
        task_map = {t.task_id: t for t in all_tasks}
        task_map[emergency_task.task_id] = emergency_task

        # Mark emergency task as high priority
        emergency_task.raw_severity = "EMERGENCY"
        emergency_task.is_safety_critical = True
        emergency_task.ml_criticality_score = max(emergency_task.ml_criticality_score or 0.0, 98.0)

        blocks = [b.model_copy(deep=True) for b in current_plan.scheduled_blocks]
        target_section = emergency_task.section_id

        # Candidate blocks on the same section
        compatible_blocks = [b for b in blocks if b.section_id == target_section]

        assigned_block_id = ""
        displaced_task_ids: List[str] = []
        mutated_count = 0

        if compatible_blocks:
            # Check if any compatible block can absorb the emergency task
            best_block = compatible_blocks[0]
            # If TRD emergency, ensure block supports power block
            if emergency_task.department == Department.TRD or emergency_task.requires_power_block:
                best_block.block_type = BlockType.COMBINED
                if Department.TRD not in best_block.departments:
                    best_block.departments.append(Department.TRD)

            # Check capacity: if block has > 4 tasks, displace lowest criticality non-safety task
            if len(best_block.task_ids) >= 4:
                block_tasks = [task_map[tid] for tid in best_block.task_ids if tid in task_map]
                non_safety = [t for t in block_tasks if not t.is_safety_critical and t.task_id != emergency_task.task_id]
                if non_safety:
                    lowest = min(non_safety, key=lambda t: t.ml_criticality_score or 0.0)
                    best_block.task_ids.remove(lowest.task_id)
                    lowest.status = TaskStatus.DEFERRED
                    lowest.deferred_count += 1
                    displaced_task_ids.append(lowest.task_id)

            best_block.task_ids.append(emergency_task.task_id)
            emergency_task.status = TaskStatus.SCHEDULED
            emergency_task.assigned_block_id = best_block.block_id
            assigned_block_id = best_block.block_id
            mutated_count += 1
            best_block.justification = (
                f"Emergency modification: accommodated critical defect {emergency_task.task_id} "
                f"({emergency_task.defect_category.value}) on priority."
            )
        else:
            # No existing block on section: create emergency slot
            new_block_id = f"BLK-EMERGENCY-{uuid.uuid4().hex[:6].upper()}"
            emergency_block = ScheduledBlock(
                block_id=new_block_id,
                window_id=f"WIN-EMG-{uuid.uuid4().hex[:6].upper()}",
                corridor_id=emergency_task.corridor_id,
                section_id=emergency_task.section_id,
                section_name=emergency_task.section_id,
                date=emergency_task.reported_date or date.today(),
                start_time=time(2, 0),
                end_time=time(4, 30),
                duration_hours=max(2.5, emergency_task.estimated_duration_hours),
                task_ids=[emergency_task.task_id],
                departments=[emergency_task.department],
                block_type=BlockType.POWER_BLOCK if emergency_task.requires_power_block else BlockType.TRAFFIC_BLOCK,
                trains_affected=2,
                cumulative_delay_minutes=35.0,
                is_merged=False,
                justification=f"Force-scheduled emergency block for defect {emergency_task.task_id}.",
            )
            blocks.append(emergency_block)
            emergency_task.status = TaskStatus.SCHEDULED
            emergency_task.assigned_block_id = new_block_id
            assigned_block_id = new_block_id
            mutated_count += 1

        unaffected_count = len(blocks) - mutated_count

        # Build updated plan
        new_plan = current_plan.model_copy(deep=True)
        new_plan.plan_id = f"PLN-REPAIR-{uuid.uuid4().hex[:8].upper()}"
        new_plan.scheduled_blocks = blocks
        new_plan.total_tasks_scheduled = sum(len(b.task_ids) for b in blocks)
        if displaced_task_ids:
            deferred = list(new_plan.deferred_task_ids or [])
            deferred.extend(displaced_task_ids)
            new_plan.deferred_task_ids = list(set(deferred))
            new_plan.total_tasks_deferred = len(new_plan.deferred_task_ids)

        narrative = (
            f"Autonomous Replanning Complete: Scheduled emergency {emergency_task.task_id} "
            f"into block {assigned_block_id} on section {target_section}. "
            f"Preserved {unaffected_count} existing blocks across all other corridors. "
            f"{f'Displaced {len(displaced_task_ids)} lower-priority task(s): {displaced_task_ids}.' if displaced_task_ids else 'Zero other tasks were displaced.'}"
        )

        return ReplanResult(
            replan_id=f"RPL-{uuid.uuid4().hex[:8].upper()}",
            original_plan_id=current_plan.plan_id,
            updated_plan=new_plan,
            emergency_task_id=emergency_task.task_id,
            assigned_block_id=assigned_block_id,
            displaced_task_ids=displaced_task_ids,
            unaffected_blocks_count=unaffected_count,
            mutated_blocks_count=mutated_count,
            narrative_explanation=narrative,
        )
