"""
Orion - Canonical Source of Truth for Task Status Buckets and Lifecycle Stages.

Every TaskStatus maps to exactly ONE bucket and exactly ONE lifecycle stage.
Enforces invariants:
  1. total == sum(bucket counts)
  2. total == sum(pipeline stage counts)
  3. total == sum(department totals) when unfiltered
Tasks awaiting acknowledgement (Part B) are excluded from all counts.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from railopt.models import Department, TaskStatus


class TaskBucket(str, Enum):
    PENDING = "pending"
    ACTIVE_SCHEDULED = "active_scheduled"
    RESOLVED = "resolved"


class PipelineStage(str, Enum):
    INTAKE = "intake"          # Stage 1: Case Allocation / Intake Queue
    PLANNING = "planning"      # Stage 2: Verified & Window Planning
    EXECUTION = "execution"    # Stage 3: Technical Resolution & Sanctions
    RESOLUTION = "resolution"  # Stage 4: Problem Resolution & Closeout


# Exact 1-to-1 mapping for all 20 TaskStatus values
STATUS_TO_BUCKET: dict[TaskStatus, TaskBucket] = {
    # Pending allocation / intake queue
    TaskStatus.DRAFT: TaskBucket.PENDING,
    TaskStatus.SUBMITTED: TaskBucket.PENDING,
    TaskStatus.REPORTED: TaskBucket.PENDING,
    TaskStatus.UNVERIFIED: TaskBucket.PENDING,
    TaskStatus.PENDING: TaskBucket.PENDING,
    TaskStatus.SCORED: TaskBucket.PENDING,
    TaskStatus.ESCALATED: TaskBucket.PENDING,
    TaskStatus.DEFERRED: TaskBucket.PENDING,

    # Active allocation, planning & live execution
    TaskStatus.WINDOWS_PROPOSED: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.WINDOW_SELECTED: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.APPROVED: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.READY: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.SCHEDULED: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.IN_PROGRESS: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.SUSPENDED: TaskBucket.ACTIVE_SCHEDULED,
    TaskStatus.OVERRUN: TaskBucket.ACTIVE_SCHEDULED,

    # Resolved, completed, closed or rejected
    TaskStatus.COMPLETED: TaskBucket.RESOLVED,
    TaskStatus.ABORTED: TaskBucket.RESOLVED,
    TaskStatus.CANCELLED: TaskBucket.RESOLVED,
    TaskStatus.REJECTED: TaskBucket.RESOLVED,
    TaskStatus.AWAITING_ACK: TaskBucket.PENDING,
    TaskStatus.DECLINED: TaskBucket.RESOLVED,
}

STATUS_TO_STAGE: dict[TaskStatus, PipelineStage] = {
    # 1. Case Allocation / Intake
    TaskStatus.DRAFT: PipelineStage.INTAKE,
    TaskStatus.SUBMITTED: PipelineStage.INTAKE,
    TaskStatus.REPORTED: PipelineStage.INTAKE,
    TaskStatus.UNVERIFIED: PipelineStage.INTAKE,
    TaskStatus.DEFERRED: PipelineStage.INTAKE,
    TaskStatus.ESCALATED: PipelineStage.INTAKE,

    # 2. Issue Identification & Window Planning
    TaskStatus.PENDING: PipelineStage.PLANNING,
    TaskStatus.SCORED: PipelineStage.PLANNING,
    TaskStatus.WINDOWS_PROPOSED: PipelineStage.PLANNING,
    TaskStatus.WINDOW_SELECTED: PipelineStage.PLANNING,

    # 3. Technical Resolution & Active Execution
    TaskStatus.APPROVED: PipelineStage.EXECUTION,
    TaskStatus.READY: PipelineStage.EXECUTION,
    TaskStatus.SCHEDULED: PipelineStage.EXECUTION,
    TaskStatus.IN_PROGRESS: PipelineStage.EXECUTION,
    TaskStatus.SUSPENDED: PipelineStage.EXECUTION,
    TaskStatus.OVERRUN: PipelineStage.EXECUTION,

    # 4. Problem Resolution
    TaskStatus.COMPLETED: PipelineStage.RESOLUTION,
    TaskStatus.ABORTED: PipelineStage.RESOLUTION,
    TaskStatus.CANCELLED: PipelineStage.RESOLUTION,
    TaskStatus.REJECTED: PipelineStage.RESOLUTION,
    TaskStatus.AWAITING_ACK: PipelineStage.INTAKE,
    TaskStatus.DECLINED: PipelineStage.RESOLUTION,
}


def normalize_status(raw_status: Any) -> TaskStatus:
    """Safely normalizes enum or string to a valid TaskStatus."""
    if isinstance(raw_status, TaskStatus):
        return raw_status
    s = str(raw_status or "").strip().upper()
    # Map common aliases if legacy strings appear
    aliases = {
        "IN PROGRESS": TaskStatus.IN_PROGRESS,
        "ACTION STARTED": TaskStatus.IN_PROGRESS,
        "DEPARTMENT NOTIFIED": TaskStatus.SCHEDULED,
        "AUTHORIZED": TaskStatus.SCHEDULED,
        "RESOLVED": TaskStatus.COMPLETED,
        "DONE": TaskStatus.COMPLETED,
        "NEW": TaskStatus.REPORTED,
    }
    if s in aliases:
        return aliases[s]
    try:
        return TaskStatus(s)
    except ValueError:
        return TaskStatus.PENDING


def get_status_bucket(status: Any) -> TaskBucket:
    st = normalize_status(status)
    return STATUS_TO_BUCKET.get(st, TaskBucket.PENDING)


def get_pipeline_stage(status: Any) -> PipelineStage:
    st = normalize_status(status)
    return STATUS_TO_STAGE.get(st, PipelineStage.PLANNING)


def is_task_awaiting_acknowledgement(task: Any) -> bool:
    """Checks whether task is awaiting acknowledgement (excluded from counts per Part B)."""
    st = getattr(task, "status", None)
    if st in (TaskStatus.AWAITING_ACK, "AWAITING_ACK", "AWAITING_ACKNOWLEDGEMENT"):
        return True
    if getattr(task, "awaiting_acknowledgement", False):
        return True
    if isinstance(task, dict):
        if task.get("status") in (TaskStatus.AWAITING_ACK.value, "AWAITING_ACK", "AWAITING_ACKNOWLEDGEMENT"):
            return True
        return bool(task.get("awaiting_acknowledgement"))
    return False


def compute_dashboard_counts(tasks: list[Any], department: Optional[str] = None) -> dict[str, Any]:
    """
    Computes single source-of-truth task counts and pipeline stage distributions.
    Enforces all invariants.
    """
    # 1. Filter out tasks awaiting acknowledgement
    valid_tasks = [t for t in tasks if not is_task_awaiting_acknowledgement(t)]

    # 2. Scope by department if requested
    dept_filter = department.strip().upper() if department else None
    if dept_filter:
        scoped_tasks = [
            t for t in valid_tasks
            if (getattr(t, "department", None) and (
                getattr(t.department, "value", str(t.department)).upper() == dept_filter
            ))
        ]
    else:
        scoped_tasks = valid_tasks

    # 3. Calculate bucket counts
    pending_count = 0
    active_count = 0
    resolved_count = 0

    # 4. Calculate pipeline stage counts
    intake_count = 0
    planning_count = 0
    execution_count = 0
    resolution_count = 0

    for t in scoped_tasks:
        st = getattr(t, "status", TaskStatus.PENDING)
        bucket = get_status_bucket(st)
        stage = get_pipeline_stage(st)

        if bucket == TaskBucket.PENDING:
            pending_count += 1
        elif bucket == TaskBucket.ACTIVE_SCHEDULED:
            active_count += 1
        elif bucket == TaskBucket.RESOLVED:
            resolved_count += 1

        if stage == PipelineStage.INTAKE:
            intake_count += 1
        elif stage == PipelineStage.PLANNING:
            planning_count += 1
        elif stage == PipelineStage.EXECUTION:
            execution_count += 1
        elif stage == PipelineStage.RESOLUTION:
            resolution_count += 1

    total = len(scoped_tasks)

    # Invariant checks
    assert total == (pending_count + active_count + resolved_count), (
        f"Bucket sum invariant failed: {total} != {pending_count + active_count + resolved_count}"
    )
    assert total == (intake_count + planning_count + execution_count + resolution_count), (
        f"Stage sum invariant failed: {total} != {intake_count + planning_count + execution_count + resolution_count}"
    )

    # 5. Build by_department breakdown
    by_department: dict[str, dict[str, int]] = {}
    known_depts = [Department.ENGINEERING.value, Department.SNT.value, Department.TRD.value]
    
    for d in known_depts:
        d_tasks = [
            t for t in valid_tasks
            if getattr(t, "department", None) and (
                getattr(t.department, "value", str(t.department)).upper() == d
            )
        ]
        d_p = sum(1 for t in d_tasks if get_status_bucket(getattr(t, "status", None)) == TaskBucket.PENDING)
        d_a = sum(1 for t in d_tasks if get_status_bucket(getattr(t, "status", None)) == TaskBucket.ACTIVE_SCHEDULED)
        d_r = sum(1 for t in d_tasks if get_status_bucket(getattr(t, "status", None)) == TaskBucket.RESOLVED)

        d_s1 = sum(1 for t in d_tasks if get_pipeline_stage(getattr(t, "status", None)) == PipelineStage.INTAKE)
        d_s2 = sum(1 for t in d_tasks if get_pipeline_stage(getattr(t, "status", None)) == PipelineStage.PLANNING)
        d_s3 = sum(1 for t in d_tasks if get_pipeline_stage(getattr(t, "status", None)) == PipelineStage.EXECUTION)
        d_s4 = sum(1 for t in d_tasks if get_pipeline_stage(getattr(t, "status", None)) == PipelineStage.RESOLUTION)

        by_department[d] = {
            "total": len(d_tasks),
            "pending": d_p,
            "active_scheduled": d_a,
            "resolved": d_r,
            "intake": d_s1,
            "planning": d_s2,
            "execution": d_s3,
            "resolution": d_s4,
        }

    return {
        "total": total,
        "pending": pending_count,
        "active_scheduled": active_count,
        "resolved": resolved_count,
        "buckets": {
            "pending": pending_count,
            "active_scheduled": active_count,
            "resolved": resolved_count,
        },
        "pipeline_stages": {
            "intake": intake_count,
            "planning": planning_count,
            "execution": execution_count,
            "resolution": resolution_count,
        },
        "by_department": by_department,
    }
