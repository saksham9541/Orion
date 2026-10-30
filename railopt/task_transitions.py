"""
railopt/task_transitions.py

Server-side state machine and transition enforcement for Orion maintenance tasks.
Enforces:
1. Legal vs illegal lifecycle transitions across Phase 1, Phase 2, and Phase 3 states.
2. Role-based authority per transition (TECHNICIAN, DEPT_USER, CONTROLLER, ADMIN).
3. Strict department scoping: TECHNICIAN and DEPT_USER can only update their own department's tasks.
4. Audit logging of every transition with user ID, role, department, timestamp, and reason codes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from railopt.models import MaintenanceTask, TaskStatus, UserRole

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. Transition Table
# ------------------------------------------------------------------------------

VALID_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.REPORTED: {
        TaskStatus.SCORED,
        TaskStatus.CANCELLED,
        TaskStatus.REJECTED,
    },
    TaskStatus.SCORED: {
        TaskStatus.WINDOWS_PROPOSED,
        TaskStatus.DEFERRED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WINDOWS_PROPOSED: {
        TaskStatus.WINDOW_SELECTED,
        TaskStatus.DEFERRED,
        TaskStatus.ESCALATED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WINDOW_SELECTED: {
        TaskStatus.APPROVED,
        TaskStatus.WINDOWS_PROPOSED,  # If controller rejects or supervisor deselects
        TaskStatus.CANCELLED,
    },
    TaskStatus.APPROVED: {
        TaskStatus.READY,             # Pre-start checks passed
        TaskStatus.IN_PROGRESS,       # Direct start by technician
        TaskStatus.ABORTED,
        TaskStatus.CANCELLED,
        TaskStatus.WINDOWS_PROPOSED,  # Controller revokes approval
    },
    TaskStatus.READY: {
        TaskStatus.IN_PROGRESS,       # Technician start
        TaskStatus.SUSPENDED,
        TaskStatus.ABORTED,
        TaskStatus.APPROVED,          # Revert ready if needed
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.COMPLETED,
        TaskStatus.SUSPENDED,
        TaskStatus.ABORTED,
        TaskStatus.OVERRUN,
    },
    TaskStatus.SUSPENDED: {
        TaskStatus.IN_PROGRESS,       # Resume work
        TaskStatus.ABORTED,
    },
    TaskStatus.OVERRUN: {
        TaskStatus.COMPLETED,
        TaskStatus.ABORTED,
    },
    TaskStatus.ABORTED: {
        TaskStatus.WINDOWS_PROPOSED,  # Re-offers task for scheduling
        TaskStatus.CANCELLED,
    },
    TaskStatus.DEFERRED: {
        TaskStatus.WINDOWS_PROPOSED,
        TaskStatus.REPORTED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.ESCALATED: {
        TaskStatus.WINDOWS_PROPOSED,
        TaskStatus.APPROVED,
        TaskStatus.CANCELLED,
    },
    # Backward compatibility with legacy statuses
    TaskStatus.DRAFT: {TaskStatus.SUBMITTED, TaskStatus.REPORTED},
    TaskStatus.SUBMITTED: {TaskStatus.SCORED, TaskStatus.PENDING, TaskStatus.REJECTED},
    TaskStatus.UNVERIFIED: {TaskStatus.PENDING, TaskStatus.REJECTED},
    TaskStatus.PENDING: {TaskStatus.SCHEDULED, TaskStatus.WINDOWS_PROPOSED, TaskStatus.DEFERRED},
    TaskStatus.SCHEDULED: {TaskStatus.APPROVED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),      # Terminal
    TaskStatus.CANCELLED: set(),      # Terminal
    TaskStatus.REJECTED: set(),       # Terminal
}


# Role permissions per target status (default allowed roles if not explicitly restricted)
ALLOWED_ROLES_BY_TARGET: Dict[TaskStatus, Set[UserRole]] = {
    TaskStatus.SCORED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
    TaskStatus.WINDOWS_PROPOSED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
    TaskStatus.WINDOW_SELECTED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
    TaskStatus.APPROVED: {UserRole.ADMIN, UserRole.CONTROLLER},
    TaskStatus.READY: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER, UserRole.TECHNICIAN},
    TaskStatus.IN_PROGRESS: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER, UserRole.TECHNICIAN},
    TaskStatus.SUSPENDED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER, UserRole.TECHNICIAN},
    TaskStatus.OVERRUN: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER, UserRole.TECHNICIAN},
    TaskStatus.COMPLETED: {UserRole.ADMIN, UserRole.DEPT_USER, UserRole.TECHNICIAN},
    TaskStatus.ABORTED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER, UserRole.TECHNICIAN},
    TaskStatus.CANCELLED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
    TaskStatus.REJECTED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
    TaskStatus.DEFERRED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
    TaskStatus.ESCALATED: {UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER},
}


def can_transition(
    from_status: TaskStatus | str,
    to_status: TaskStatus | str,
    user_role: Optional[UserRole | str] = None,
) -> Tuple[bool, str]:
    """
    Checks if a transition from from_status to to_status is legally valid
    and permitted for user_role.
    """
    try:
        f_st = TaskStatus(from_status) if isinstance(from_status, str) else from_status
        t_st = TaskStatus(to_status) if isinstance(to_status, str) else to_status
    except ValueError as e:
        return False, f"Unknown status: {e}"

    # Super Admin can perform administrative status override
    if user_role is not None:
        try:
            r = UserRole(user_role) if isinstance(user_role, str) else user_role
            if r == UserRole.ADMIN:
                return True, "OK"
        except ValueError:
            pass

    # 1. State machine transition validity
    allowed_targets = VALID_TRANSITIONS.get(f_st, set())
    if t_st not in allowed_targets:
        return False, f"Illegal state transition from {f_st.value} to {t_st.value}."

    # 2. Role permission check (if role provided)
    if user_role is not None:
        try:
            r = UserRole(user_role) if isinstance(user_role, str) else user_role
        except ValueError:
            r = None

        allowed_roles = ALLOWED_ROLES_BY_TARGET.get(t_st, set())
        if r is not None and r not in allowed_roles:
            return False, f"Role {r.value} is not authorized to transition task to {t_st.value}."

    return True, "OK"


def validate_department_scope(task: MaintenanceTask, user: Optional[Any]) -> None:
    """
    Validates that departmental users (DEPT_USER, TECHNICIAN) can only modify
    tasks belonging to their own department. CONTROLLER and ADMIN have division-wide scope.
    """
    if not user:
        return

    user_role = getattr(user, "role", None)
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role.upper())
        except Exception:
            pass

    # Controllers and Admins have global scope
    if user_role in (UserRole.ADMIN, UserRole.CONTROLLER):
        return

    # Department scoped users
    u_dept = getattr(user, "department", None)
    user_dept = (u_dept.value if hasattr(u_dept, "value") else str(u_dept or "")).upper()
    t_dept = getattr(task, "department", None)
    task_dept = (t_dept.value if hasattr(t_dept, "value") else str(t_dept or "")).upper()

    if user_dept and task_dept and user_dept != task_dept:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: User of department {user_dept} cannot modify task belonging to {task_dept}.",
        )


def transition_task(
    task: MaintenanceTask,
    to_status: TaskStatus | str,
    user: Optional[Any] = None,
    reason: Optional[str] = None,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    outcome: Optional[str] = None,
    actual_start: Optional[datetime] = None,
    actual_end: Optional[datetime] = None,
    session: Optional[Session] = None,
) -> MaintenanceTask:
    """
    Transitions task to to_status with server-side validation, role checks,
    department scope validation, field assignments, and audit logging.
    """
    to_st = TaskStatus(to_status) if isinstance(to_status, str) else to_status
    from_st = task.status if isinstance(task.status, TaskStatus) else TaskStatus(task.status)

    user_role = getattr(user, "role", None)
    is_valid, msg = can_transition(from_st, to_st, user_role=user_role)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # Department scope check
    validate_department_scope(task, user)

    now_utc = datetime.now(timezone.utc)

    # Field assignments based on target execution status
    if to_st == TaskStatus.READY:
        task.pre_start_check_passed = True
        task.pre_start_check_by = getattr(user, "email", "system")
        task.pre_start_check_at = now_utc
    elif to_st == TaskStatus.IN_PROGRESS:
        task.actual_start = actual_start or now_utc
    elif to_st == TaskStatus.COMPLETED:
        task.actual_end = actual_end or now_utc
        task.execution_outcome = outcome or "SUCCESS"
        if notes:
            task.execution_notes = notes
    elif to_st == TaskStatus.SUSPENDED:
        task.suspend_reason_code = reason_code or reason or "MANUAL_SUSPENSION"
    elif to_st == TaskStatus.ABORTED:
        task.abort_reason_code = reason_code or reason or "UNSPECIFIED_ABORT"
        if notes:
            task.execution_notes = notes
    elif to_st == TaskStatus.OVERRUN:
        task.overrun_detected_at = now_utc

    # Update status
    task.status = to_st

    # Audit log entry for task.history
    user_id = getattr(user, "id", None) or getattr(user, "user_id", None) or "SYSTEM"
    user_email = getattr(user, "email", "system")
    role_str = (user_role.value if hasattr(user_role, "value") else str(user_role)) if user_role else "SYSTEM"
    dept_str = getattr(user, "department", None)

    audit_entry = {
        "id": f"AUD-{uuid.uuid4().hex[:8]}",
        "from_status": from_st.value,
        "to_status": to_st.value,
        "changed_by": user_email,
        "changed_by_user_id": user_id,
        "role": role_str,
        "department": dept_str,
        "timestamp": now_utc.isoformat(),
        "reason": reason,
        "reason_code": reason_code,
        "notes": notes,
        "outcome": outcome,
    }
    if not isinstance(task.history, list):
        task.history = []
    task.history.append(audit_entry)

    # Persist audit record and update task record if session provided
    if session is not None:
        try:
            from backend.database import TaskRecord, TaskTransitionAuditRecord, save_tasks
            # 1. Record transition audit row
            audit_record = TaskTransitionAuditRecord(
                id=str(uuid.uuid4()),
                task_id=task.task_id,
                from_status=from_st.value,
                to_status=to_st.value,
                changed_by_user_id=str(user_id),
                changed_by_role=role_str,
                changed_by_department=dept_str,
                reason=reason,
                reason_code=reason_code,
                timestamp=now_utc,
                details={"notes": notes, "outcome": outcome},
            )
            session.add(audit_record)
            session.commit()

            # 2. Persist updated task
            save_tasks(session, [task])
        except Exception as e:
            logger.warning("Failed to persist task transition audit record: %s", e)

    return task
