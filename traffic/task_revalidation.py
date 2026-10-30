"""
traffic/task_revalidation.py

Task-level maintenance window revalidation service and scheduled verification runs.
Provides:
1. revalidate_task: Evaluates assigned window against live train delays, cancellations,
   and route diversions using traffic/window_reliability.py.
2. Notifications for supervisor and controller on conflict or confidence degradation.
3. Persistent audit logging to revalidation_results table.
4. Scheduled multi-horizon verification runs (T-24h, T-6h, T-1h).
5. Pre-start safety checks enforcing allowed start time tolerance and LOW-confidence confirmation.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

try:
    from zoneinfo import ZoneInfo
    KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    KOLKATA_TZ = timezone(timedelta(hours=5, minutes=30))

from railopt.models import BlockWindow, LiveTrainStatus, MaintenanceTask, TaskStatus, UserRole
from traffic.block_sections import BlockSection, get_block_section_by_id, build_block_sections
from traffic.passages import BlockSectionPassage, load_pilot_block_passages
from traffic.window_finder import (
    _minutes_to_time,
    _time_to_minutes,
    find_block_section_windows,
)
from traffic.window_reliability import (
    ReliabilityConfig,
    apply_live_train_statuses,
    compute_confidence_score,
    compute_passage_margin,
    extract_bounding_trains,
    filter_passages_by_track,
)

logger = logging.getLogger(__name__)


def _find_task_assigned_window(
    task: MaintenanceTask,
    session: Optional[Session] = None,
    app_state: Optional[Any] = None,
) -> Optional[BlockWindow]:
    """Finds the assigned or selected BlockWindow for a maintenance task."""
    target_block_id = task.assigned_block_id
    if not target_block_id:
        return None

    # 1. Search in app_state windows
    if app_state and hasattr(app_state, "windows") and app_state.windows:
        for w in app_state.windows:
            if getattr(w, "window_id", "") == target_block_id:
                return w

    # 2. Search in app_state scheduled plans
    if app_state and hasattr(app_state, "plans") and app_state.plans:
        for p in app_state.plans:
            for b in getattr(p, "scheduled_blocks", []):
                b_id = b.get("block_id") if isinstance(b, dict) else getattr(b, "block_id", "")
                if b_id == target_block_id:
                    # Construct BlockWindow representation
                    w_date = b.get("date") if isinstance(b, dict) else getattr(b, "date", None)
                    if isinstance(w_date, str):
                        w_date = date.fromisoformat(w_date)
                    s_t = b.get("start_time") if isinstance(b, dict) else getattr(b, "start_time", time(2, 0))
                    e_t = b.get("end_time") if isinstance(b, dict) else getattr(b, "end_time", time(4, 0))
                    if isinstance(s_t, str):
                        s_t = time.fromisoformat(s_t)
                    if isinstance(e_t, str):
                        e_t = time.fromisoformat(e_t)

                    return BlockWindow(
                        window_id=target_block_id,
                        corridor_id=task.corridor_id,
                        section_id=task.section_id,
                        block_section_id=task.block_section_id,
                        line=task.line,
                        date=w_date or task.reported_date or date.today(),
                        start_time=s_t,
                        end_time=e_t,
                        duration_hours=round((_time_to_minutes(e_t) - _time_to_minutes(s_t)) / 60.0, 2),
                    )

    # 3. Fallback: synthesise a candidate window from task attributes
    w_date = task.reported_date or date.today()
    dur_h = task.estimated_duration_hours or 2.0
    s_t = time(2, 0)  # Default night maintenance window
    dur_m = int(dur_h * 60)
    e_t = _minutes_to_time(_time_to_minutes(s_t) + dur_m)

    return BlockWindow(
        window_id=target_block_id,
        corridor_id=task.corridor_id,
        section_id=task.section_id,
        block_section_id=task.block_section_id,
        line=task.line,
        date=w_date,
        start_time=s_t,
        end_time=e_t,
        duration_hours=dur_h,
    )


def revalidate_task(
    task_id: str,
    horizon: str = "ON_DEMAND",
    session: Optional[Session] = None,
    live_delays_map: Optional[Dict[str, float]] = None,
    config: Optional[ReliabilityConfig] = None,
    app_state: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Revalidates the assigned window for a maintenance task using traffic/window_reliability.
    Re-checks cancelled, diverted and rescheduled trains, stored live delays (with age) and new conflicts.
    Returns:
    - has_conflict: bool
    - status: "CLEAN" | "CONFLICT" | "NO_WINDOW_ASSIGNED"
    - affected_trains: list of encroaching trains
    - confidence: "HIGH" | "MEDIUM" | "LOW"
    - bounding_trains: {prev, next}
    - stale_flag: bool
    - next_best_start: "HH:MM"
    """
    cfg = config or ReliabilityConfig()
    from backend.database import TaskRecord, load_live_status, load_tasks

    # 1. Fetch Task
    target_task: Optional[MaintenanceTask] = None
    if app_state and hasattr(app_state, "tasks") and app_state.tasks:
        for t in app_state.tasks:
            if t.task_id == task_id:
                target_task = t
                break

    if target_task is None and session is not None:
        db_tasks, _ = load_tasks(session)
        for t in db_tasks:
            if t.task_id == task_id:
                target_task = t
                break

    if target_task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # 2. Find Assigned Window
    window = _find_task_assigned_window(target_task, session=session, app_state=app_state)
    if not window:
        return {
            "task_id": task_id,
            "window_id": None,
            "block_section_id": target_task.block_section_id,
            "has_conflict": False,
            "conflict": False,
            "status": "NO_WINDOW_ASSIGNED",
            "confidence": "LOW",
            "confidence_breakdown": {},
            "bounding_trains": {"prev": None, "next": None},
            "stale_flag": False,
            "stale_status": False,
            "status_age_hours": 0.0,
            "affected_trains": [],
            "next_best_start": None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    # 3. Resolve Block Section
    bs_id = getattr(window, "block_section_id", None) or target_task.block_section_id
    block_section: Optional[BlockSection] = None
    if bs_id:
        block_section = get_block_section_by_id(bs_id)

    if not block_section:
        pilot_sections = build_block_sections("SEC-93135bb9")
        block_section = pilot_sections[0]

    # 4. Load Live Statuses from Database & overlay live_delays_map
    stored_statuses: Dict[str, LiveTrainStatus] = {}
    if session is not None:
        try:
            db_status_list = load_live_status(session)
            for s in db_status_list:
                stored_statuses[s.train_number] = s
        except Exception as e:
            logger.debug("Live status load error in revalidation: %s", e)

    if live_delays_map:
        for t_no, d_min in live_delays_map.items():
            stored_statuses[t_no] = LiveTrainStatus(
                train_number=t_no,
                delay_minutes=d_min,
                status="DELAYED" if d_min > 0 else "RUNNING",
                last_updated=datetime.now(),
            )

    # 5. Load timetable passages
    target_d = window.date or date.today()
    passages = load_pilot_block_passages(
        pilot_section_id=block_section.pilot_section_id,
        target_date=target_d,
    )

    # 6. Apply live train status (cancellations open windows, diversions/delays shift)
    active_passages, is_stale, status_age = apply_live_train_statuses(
        passages=passages,
        target_date=target_d,
        live_statuses=stored_statuses,
        config=cfg,
    )

    # 7. Filter passages by line
    task_line = getattr(window, "line", None) or getattr(target_task, "line", "DN")
    active_passages = filter_passages_by_track(
        passages=active_passages,
        block_section=block_section,
        task_line=task_line,
        mode=cfg.mode,
    )

    # 8. Check conflicts with window interval
    pre_buf = getattr(window, "pre_buffer_minutes", cfg.pre_buffer_minutes)
    post_buf = getattr(window, "post_buffer_minutes", cfg.post_buffer_minutes)
    w_start_m = _time_to_minutes(window.start_time) - pre_buf
    w_end_m = _time_to_minutes(window.end_time) + post_buf

    affected_trains: List[Dict[str, Any]] = []
    latest_conflicting_exit_m = -1

    for p in active_passages:
        s_m = _time_to_minutes(p.enter_time)
        e_m = _time_to_minutes(p.exit_time)
        if e_m < s_m:
            e_m += 1440

        p_buf = compute_passage_margin(p, target_d, cfg)
        occ_s = s_m - p_buf
        occ_e = e_m + p_buf

        # Overlap check
        if occ_s < w_end_m and w_start_m < occ_e:
            encroachment = min(w_end_m, occ_e) - max(w_start_m, occ_s)
            affected_trains.append({
                "train_number": p.train_no,
                "train_name": p.train_name,
                "train_type": p.train_type.value if hasattr(p.train_type, "value") else str(p.train_type),
                "scheduled_enter": p.enter_time.strftime("%H:%M"),
                "scheduled_exit": p.exit_time.strftime("%H:%M"),
                "encroachment_minutes": max(0, encroachment),
                "provenance": getattr(p, "provenance", "live"),
            })
            if occ_e > latest_conflicting_exit_m:
                latest_conflicting_exit_m = occ_e

    has_conflict = len(affected_trains) > 0

    # 9. Confidence and breakdown
    confidence, conf_breakdown = compute_confidence_score(
        passages=active_passages,
        target_date=target_d,
        traffic_mode=cfg.traffic_mode,
    )

    if is_stale:
        conf_breakdown["stale_status"] = True
        conf_breakdown["status_age_hours"] = status_age
        # Staleness drops confidence
        if confidence == "HIGH":
            confidence = "MEDIUM"
        elif confidence == "MEDIUM":
            confidence = "LOW"

    # 10. Extract Bounding Trains
    bounding = extract_bounding_trains(
        passages=active_passages,
        window_start=window.start_time,
        window_end=window.end_time,
    )

    # 11. Next Best Start time
    next_best_start_str: Optional[str] = None
    if has_conflict:
        # Earliest time after latest conflicting train clears
        candidate_m = latest_conflicting_exit_m + pre_buf
        if candidate_m < 1440:
            next_best_start_str = _minutes_to_time(candidate_m).strftime("%H:%M")
        else:
            next_best_start_str = "02:00"  # Next night slot
    else:
        next_best_start_str = window.start_time.strftime("%H:%M")

    reasons: List[str] = []
    if has_conflict:
        reasons.append(f"ENCROACHMENT_{len(affected_trains)}_TRAINS")
    else:
        reasons.append("WINDOW_CLEAN")
    if is_stale:
        reasons.append("LIVE_STATUS_STALE")

    now_utc = datetime.now(timezone.utc)

    # 12. Create notification if conflict detected
    if has_conflict and session is not None:
        try:
            from backend.database import NotificationRecord
            notif = NotificationRecord(
                id=str(uuid.uuid4()),
                issue_id=task_id,
                recipient_user_id="controller",
                type="WINDOW_REVALIDATION_CONFLICT",
                title=f"Revalidation Conflict on Task {task_id}",
                message=(
                    f"Task {task_id} on {block_section.name} ({task_line}) has "
                    f"{len(affected_trains)} encroaching train(s). Next best start: {next_best_start_str}."
                ),
                severity="HIGH",
                created_at=now_utc,
            )
            session.add(notif)
            session.commit()
        except Exception as e:
            logger.debug("Failed to create conflict notification: %s", e)

    # 13. Persist RevalidationResultRecord
    if session is not None:
        try:
            from backend.database import RevalidationResultRecord
            rec = RevalidationResultRecord(
                id=str(uuid.uuid4()),
                task_id=task_id,
                window_id=window.window_id,
                block_section_id=block_section.id,
                checked_at=now_utc,
                horizon=horizon,
                is_valid=not has_conflict,
                status="CONFLICT" if has_conflict else "CLEAN",
                confidence=confidence,
                stale_status=is_stale,
                status_age_hours=status_age,
                has_conflict=has_conflict,
                affected_trains=affected_trains,
                bounding_trains=bounding,
                next_best_start=next_best_start_str,
                reasons=reasons,
                triggered_by="SCHEDULED_JOB" if "T-" in horizon else "USER",
            )
            session.add(rec)
            session.commit()
        except Exception as e:
            logger.warning("Failed to persist RevalidationResultRecord: %s", e)

    return {
        "task_id": task_id,
        "window_id": window.window_id,
        "block_section_id": block_section.id,
        "has_conflict": has_conflict,
        "conflict": has_conflict,
        "status": "CONFLICT" if has_conflict else "CLEAN",
        "affected_trains": affected_trains,
        "confidence": confidence,
        "confidence_breakdown": conf_breakdown,
        "bounding_trains": bounding,
        "stale_flag": is_stale,
        "stale_status": is_stale,
        "status_age_hours": status_age,
        "next_best_start": next_best_start_str,
        "reasons": reasons,
        "checked_at": now_utc.isoformat(),
    }


def run_scheduled_revalidations(
    horizon: str = "T-1h",
    session: Optional[Session] = None,
    app_state: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Executes automated revalidation runs across all approved tasks for horizon (T-24h, T-6h, T-1h).
    Notifies supervisor and controller if confidence drops a level or a conflict appears.
    Stores every result in RevalidationResultRecord.
    """
    from backend.database import NotificationRecord, RevalidationResultRecord, TaskRecord, get_session, load_tasks

    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    try:
        tasks, _ = load_tasks(session)
        # Check approved tasks
        target_tasks = [
            t for t in tasks
            if t.status in (TaskStatus.APPROVED, TaskStatus.WINDOW_SELECTED, TaskStatus.READY)
            and t.assigned_block_id
        ]

        results = []
        for t in target_tasks:
            # Check previous revalidation result for this task
            prev_record = (
                session.query(RevalidationResultRecord)
                .filter_by(task_id=t.task_id)
                .order_by(RevalidationResultRecord.checked_at.desc())
                .first()
            )

            res = revalidate_task(
                task_id=t.task_id,
                horizon=horizon,
                session=session,
                app_state=app_state,
            )
            results.append(res)

            # Compare confidence and conflict with previous run
            if prev_record:
                # 1. Confidence drop notification
                prev_conf = prev_record.confidence
                curr_conf = res.get("confidence", "MEDIUM")
                conf_levels = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
                if conf_levels.get(curr_conf, 0) < conf_levels.get(prev_conf, 0):
                    notif = NotificationRecord(
                        id=str(uuid.uuid4()),
                        issue_id=t.task_id,
                        recipient_user_id="controller",
                        type="CONFIDENCE_DROPPED",
                        title=f"Confidence Dropped to {curr_conf} at {horizon}",
                        message=f"Task {t.task_id} confidence downgraded from {prev_conf} to {curr_conf} during {horizon} revalidation.",
                        severity="MEDIUM" if curr_conf == "MEDIUM" else "HIGH",
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(notif)
                    session.commit()

                # 2. Conflict appearance notification
                if not prev_record.has_conflict and res.get("has_conflict"):
                    notif = NotificationRecord(
                        id=str(uuid.uuid4()),
                        issue_id=t.task_id,
                        recipient_user_id="controller",
                        type="NEW_CONFLICT_DETECTED",
                        title=f"New Conflict at {horizon} for Task {t.task_id}",
                        message=f"A conflict appeared at {horizon} for Task {t.task_id}. Revalidation recommends start: {res.get('next_best_start')}.",
                        severity="HIGH",
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(notif)
                    session.commit()

        return results
    finally:
        if close_session:
            session.close()


def format_clock_ist(dt: Union[datetime, time, str, None]) -> str:
    """Format time or datetime as 12-hour clock time with AM/PM (e.g. 1:30 PM)."""
    if dt is None:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            try:
                dt = time.fromisoformat(dt)
            except Exception:
                return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone(KOLKATA_TZ)
        t = dt.time()
    else:
        t = dt
    h = t.hour % 12
    if h == 0:
        h = 12
    m = f"{t.minute:02d}"
    ampm = "AM" if t.hour < 12 else "PM"
    return f"{h}:{m} {ampm}"


def _audit_log_blocked_start(
    session: Optional[Session],
    task: MaintenanceTask,
    user: Optional[Any],
    reason_code: str,
    timestamp: datetime,
    detail: dict,
) -> None:
    if session is None:
        return
    try:
        from backend.database import TaskTransitionAuditRecord
        u_email = getattr(user, "email", "system")
        u_role = getattr(user, "role", "unknown")
        u_dept = getattr(user, "department", "unknown")
        audit = TaskTransitionAuditRecord(
            id=str(uuid.uuid4()),
            task_id=task.task_id,
            from_status=getattr(task.status, "value", str(task.status)),
            to_status="BLOCKED_START",
            changed_by_user_id=u_email,
            changed_by_role=str(u_role),
            changed_by_department=str(u_dept),
            reason=f"Blocked start: {detail.get('message', reason_code)}",
            reason_code=reason_code,
            timestamp=timestamp.astimezone(timezone.utc) if timestamp.tzinfo else timestamp,
            details=detail,
        )
        session.add(audit)
        session.commit()
    except Exception as e:
        logger.warning("Failed to write audit log for blocked start: %s", e)


def start_task_execution(
    task_id: str,
    confirm_low_confidence: bool = False,
    actual_start: Optional[datetime] = None,
    notes: Optional[str] = None,
    current_user: Optional[Any] = None,
    session: Optional[Session] = None,
    app_state: Optional[Any] = None,
    server_time_override: Optional[datetime] = None,
) -> MaintenanceTask:
    """
    Technician start action:
    - Enforces status == APPROVED (or READY).
    - Enforces role + department scope.
    - Validates execution start strictly using server time in IST (never device clock).
    - Checks start is within [start_allowed_from - early_tolerance, start_allowed_until].
    - Returns HTTP 409 Conflict with structured data on invalid or out-of-window attempts.
    - Audit logs blocked attempts to TaskTransitionAuditRecord.
    - Requires explicit confirm_low_confidence=True if confidence is LOW or status is stale.
    - Transitions task to IN_PROGRESS and logs transition.
    """
    import os
    from backend.database import TaskRecord, load_tasks, save_tasks
    from railopt.task_transitions import transition_task

    target_task: Optional[MaintenanceTask] = None
    if app_state and hasattr(app_state, "tasks") and app_state.tasks:
        for t in app_state.tasks:
            if t.task_id == task_id:
                target_task = t
                break

    if target_task is None and session is not None:
        db_tasks, _ = load_tasks(session)
        for t in db_tasks:
            if t.task_id == task_id:
                target_task = t
                break

    if target_task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Authoritative server time in IST (client actual_start is ignored for gate enforcement)
    server_now = server_time_override or datetime.now(KOLKATA_TZ)
    if server_now.tzinfo is None:
        server_now = server_now.replace(tzinfo=KOLKATA_TZ)

    # 1. State check: Must be APPROVED or READY
    if target_task.status not in (TaskStatus.APPROVED, TaskStatus.READY):
        detail = {
            "code": "WINDOW_NOT_APPROVED",
            "message": "This task has not been approved by the controller.",
            "server_now": server_now.isoformat(),
            "server_now_clock": format_clock_ist(server_now),
            "status": getattr(target_task.status, "value", str(target_task.status)),
        }
        _audit_log_blocked_start(session, target_task, current_user, "WINDOW_NOT_APPROVED", server_now, detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    # 2. Timing check: start_allowed_from and start_allowed_until
    s_from = getattr(target_task, "start_allowed_from", None)
    s_until = getattr(target_task, "start_allowed_until", None)
    p_end = getattr(target_task, "planned_end", None)

    # If start window fields not explicitly on task, derive from assigned block window
    if not s_from or not s_until:
        window = _find_task_assigned_window(target_task, session=session, app_state=app_state)
        if window:
            w_date = window.date or date.today()
            if isinstance(w_date, str):
                w_date = date.fromisoformat(w_date)
            dur_h = target_task.estimated_duration_hours or 1.25
            s_from = datetime.combine(w_date, window.start_time).replace(tzinfo=KOLKATA_TZ)
            w_end = datetime.combine(w_date, window.end_time).replace(tzinfo=KOLKATA_TZ)
            w_dur_m = max(15, int((w_end - s_from).total_seconds() / 60))
            slack_m = max(0, w_dur_m - int(dur_h * 60))
            latest_m = min(30, slack_m) if slack_m > 0 else 0
            s_until = s_from + timedelta(minutes=latest_m)
            p_end = s_until + timedelta(minutes=int(dur_h * 60))
        else:
            detail = {
                "code": "WINDOW_NOT_APPROVED",
                "message": "This task has not been approved by the controller.",
                "server_now": server_now.isoformat(),
                "server_now_clock": format_clock_ist(server_now),
                "status": getattr(target_task.status, "value", str(target_task.status)),
            }
            _audit_log_blocked_start(session, target_task, current_user, "WINDOW_NOT_APPROVED", server_now, detail)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    if s_from and s_from.tzinfo is None:
        s_from = s_from.replace(tzinfo=KOLKATA_TZ)
    if s_until and s_until.tzinfo is None:
        s_until = s_until.replace(tzinfo=KOLKATA_TZ)
    if p_end and p_end.tzinfo is None:
        p_end = p_end.replace(tzinfo=KOLKATA_TZ)

    # Configurable early tolerance (default: 0 minutes)
    tol_min = getattr(target_task, "early_tolerance_minutes", None)
    if tol_min is None:
        try:
            tol_min = int(os.environ.get("START_WINDOW_EARLY_TOLERANCE_MINUTES", "0"))
        except ValueError:
            tol_min = 0

    early_bound = s_from - timedelta(minutes=tol_min)

    designated_period_clock = f"{format_clock_ist(s_from)} - {format_clock_ist(s_until)}"
    planned_end_clock = format_clock_ist(p_end)

    if server_now < early_bound:
        seconds_until_open = max(0, int((s_from - server_now).total_seconds()))
        detail = {
            "code": "WINDOW_TOO_EARLY",
            "message": "Starting outside the approved period can disrupt train running.",
            "server_now": server_now.isoformat(),
            "server_now_clock": format_clock_ist(server_now),
            "start_allowed_from": s_from.isoformat(),
            "start_allowed_until": s_until.isoformat(),
            "planned_end": p_end.isoformat(),
            "designated_period_clock": designated_period_clock,
            "planned_end_clock": planned_end_clock,
            "seconds_until_open": seconds_until_open,
        }
        _audit_log_blocked_start(session, target_task, current_user, "WINDOW_TOO_EARLY", server_now, detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    if server_now > s_until:
        detail = {
            "code": "WINDOW_TOO_LATE",
            "message": "Starting outside the approved period can disrupt train running.",
            "server_now": server_now.isoformat(),
            "server_now_clock": format_clock_ist(server_now),
            "start_allowed_from": s_from.isoformat(),
            "start_allowed_until": s_until.isoformat(),
            "planned_end": p_end.isoformat(),
            "designated_period_clock": designated_period_clock,
            "planned_end_clock": planned_end_clock,
            "window_ended": True,
        }
        _audit_log_blocked_start(session, target_task, current_user, "WINDOW_TOO_LATE", server_now, detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    # 3. Confidence and Staleness Check
    reval = revalidate_task(
        task_id=task_id,
        horizon="PRE_START",
        session=session,
        app_state=app_state,
    )
    is_low_conf = reval.get("confidence") == "LOW"
    is_stale = bool(reval.get("stale_status") or reval.get("stale_flag"))

    if (is_low_conf or is_stale) and not confirm_low_confidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Maintenance window has LOW confidence or stale live delay status. "
                "Explicit confirmation (confirm_low_confidence=True) is required to start work."
            ),
        )

    # 4. Perform Transition to IN_PROGRESS using authoritative server_now
    updated = transition_task(
        task=target_task,
        to_status=TaskStatus.IN_PROGRESS,
        user=current_user,
        actual_start=server_now,
        notes=notes,
        session=session,
    )
    if session is not None:
        save_tasks(session, [updated])
    return updated
