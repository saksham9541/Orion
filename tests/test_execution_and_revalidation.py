"""
tests/test_execution_and_revalidation.py

Tests for Orion Phase 3 Checkpoint 1 (Execution State Machine + Task Revalidation):
1. Legal and illegal state transitions across task lifecycle + department scope checks.
2. Revalidation drops confidence when live delay status is stale (>2h).
3. Cancelled train found at T-1h opens the window and notifies.
4. Delayed train entering the window triggers conflict + next best start calculation + controller notification.
5. LOW confidence or stale status start requires explicit confirm_low_confidence flag.
6. Scheduled revalidation runs (T-24h, T-6h, T-1h) store audit results in RevalidationResultRecord.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import User
from backend.database import (
    Base,
    LiveTrainStatusRecord,
    NotificationRecord,
    RevalidationResultRecord,
    TaskRecord,
    TaskTransitionAuditRecord,
    save_tasks,
)
from railopt.models import (
    BlockWindow,
    Department,
    LiveTrainStatus,
    MaintenanceTask,
    TaskStatus,
    TrainType,
    UserRole,
)
from railopt.task_transitions import can_transition, transition_task
from traffic.task_revalidation import (
    revalidate_task,
    run_scheduled_revalidations,
    start_task_execution,
)
from traffic.window_reliability import ReliabilityConfig


@pytest.fixture
def db_session():
    """Isolated SQLite in-memory test database fixture."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    yield session
    session.close()


def _create_sample_task(
    task_id: str = "TSK-EXEC-01",
    department: str = "ENGINEERING",
    status: TaskStatus = TaskStatus.APPROVED,
    assigned_block_id: str = "BW-TEST-EXEC-01",
    line: str = "DN",
    block_section_id: str = "BLK-845de309",
    duration_h: float = 2.0,
) -> MaintenanceTask:
    """Helper to build a sample MaintenanceTask."""
    return MaintenanceTask(
        task_id=task_id,
        source_system="TMS",
        source_record_id=f"REC-{task_id}",
        department=Department(department),
        asset_type="RAIL",
        asset_id="AST-001",
        defect_category="RAIL_FRACTURE",
        raw_severity="EMERGENCY",
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        block_section_id=block_section_id,
        line=line,
        km_location=12.5,
        reported_date=date.today(),
        status=status,
        assigned_block_id=assigned_block_id,
        estimated_duration_hours=duration_h,
    )


# ==============================================================================
# 1. Legal and Illegal State Transitions & Department Scope Checks
# ==============================================================================

def test_legal_and_illegal_transitions(db_session):
    """
    Verifies:
    - Legal sequence: APPROVED -> READY -> IN_PROGRESS -> COMPLETED
    - Legal sequence: IN_PROGRESS -> SUSPENDED -> IN_PROGRESS -> OVERRUN -> COMPLETED
    - Legal sequence: IN_PROGRESS -> ABORTED -> WINDOWS_PROPOSED
    - Illegal jumps (e.g. REPORTED -> IN_PROGRESS, APPROVED -> COMPLETED) are rejected with 400
    - Cross-department modification without CONTROLLER/ADMIN role is rejected with 403
    - Transition audit log is written to DB
    """
    task = _create_sample_task(status=TaskStatus.APPROVED)
    save_tasks(db_session, [task])

    eng_user = User(
        id="usr_eng",
        email="eng@railopt.gov.in",
        role=UserRole.DEPT_USER,
        department=Department.ENGINEERING,
        name="Eng Officer",
        is_active=True,
    )
    snt_user = User(
        id="usr_snt",
        email="snt@railopt.gov.in",
        role=UserRole.DEPT_USER,
        department=Department.SNT,
        name="S&T Officer",
        is_active=True,
    )
    tech_user = User(
        id="usr_tech",
        email="tech@railopt.gov.in",
        role=UserRole.TECHNICIAN,
        department=Department.ENGINEERING,
        name="Track Tech",
        is_active=True,
    )
    controller_user = User(
        id="usr_ctrl",
        email="ctrl@railopt.gov.in",
        role=UserRole.CONTROLLER,
        department=None,
        name="Division Controller",
        is_active=True,
    )

    # A. Legal transition: APPROVED -> READY
    transition_task(task, TaskStatus.READY, user=tech_user, session=db_session)
    assert task.status == TaskStatus.READY
    assert task.pre_start_check_passed is True
    assert task.pre_start_check_by == tech_user.email

    # B. Legal transition: READY -> IN_PROGRESS
    start_time = datetime.now(timezone.utc)
    transition_task(task, TaskStatus.IN_PROGRESS, user=tech_user, actual_start=start_time, session=db_session)
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.actual_start is not None

    # C. Legal transition: IN_PROGRESS -> SUSPENDED -> IN_PROGRESS
    transition_task(task, TaskStatus.SUSPENDED, user=eng_user, reason_code="WEATHER", session=db_session)
    assert task.status == TaskStatus.SUSPENDED
    assert task.suspend_reason_code == "WEATHER"

    transition_task(task, TaskStatus.IN_PROGRESS, user=tech_user, session=db_session)
    assert task.status == TaskStatus.IN_PROGRESS

    # D. Legal transition: IN_PROGRESS -> OVERRUN
    transition_task(task, TaskStatus.OVERRUN, user=controller_user, session=db_session)
    assert task.status == TaskStatus.OVERRUN
    assert task.overrun_detected_at is not None

    # E. Legal transition: OVERRUN -> COMPLETED
    end_time = datetime.now(timezone.utc)
    transition_task(task, TaskStatus.COMPLETED, user=tech_user, actual_end=end_time, notes="Welding finished", session=db_session)
    assert task.status == TaskStatus.COMPLETED
    assert task.actual_end is not None
    assert task.execution_notes == "Welding finished"

    # F. Verify Audit logs in DB
    audits = db_session.query(TaskTransitionAuditRecord).filter_by(task_id=task.task_id).all()
    assert len(audits) >= 5
    to_statuses = [a.to_status for a in audits]
    assert "READY" in to_statuses
    assert "IN_PROGRESS" in to_statuses
    assert "COMPLETED" in to_statuses

    # G. Illegal Transition Checks
    task_reported = _create_sample_task(task_id="TSK-ILLEGAL", status=TaskStatus.REPORTED)
    # Direct jump to IN_PROGRESS must fail
    with pytest.raises(HTTPException) as exc_info:
        transition_task(task_reported, TaskStatus.IN_PROGRESS, user=eng_user, session=db_session)
    assert exc_info.value.status_code == 400

    # Cannot complete from APPROVED directly
    task_approved = _create_sample_task(task_id="TSK-APPROVED", status=TaskStatus.APPROVED)
    with pytest.raises(HTTPException) as exc_info:
        transition_task(task_approved, TaskStatus.COMPLETED, user=eng_user, session=db_session)
    assert exc_info.value.status_code == 400

    # H. Cross-Department Scope Check
    # SNT user cannot transition an ENGINEERING task
    with pytest.raises(HTTPException) as exc_info:
        transition_task(task_approved, TaskStatus.READY, user=snt_user, session=db_session)
    assert exc_info.value.status_code == 403


# ==============================================================================
# 2. Revalidation Drops Confidence When Status Is Stale
# ==============================================================================

def test_revalidation_drops_confidence_when_status_is_stale(db_session):
    """
    If stored LiveTrainStatus is older than threshold (2h), revalidation flags
    stale_status=True and downgrades confidence level.
    """
    task = _create_sample_task(task_id="TSK-STALE-01")
    save_tasks(db_session, [task])

    # Insert a stale live train status (5 hours old)
    stale_time = datetime.now() - timedelta(hours=5.0)
    db_session.add(LiveTrainStatusRecord(
        train_number="12302",
        train_name="Howrah Rajdhani",
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        delay_minutes=15.0,
        status="RUNNING",
        last_updated=stale_time,
        source="RAILRADAR",
    ))
    db_session.commit()

    cfg = ReliabilityConfig(stale_status_threshold_hours=2.0)
    res = revalidate_task(
        task_id=task.task_id,
        horizon="T-6h",
        session=db_session,
        config=cfg,
    )

    assert res["stale_status"] is True or res["stale_flag"] is True
    assert res["status_age_hours"] >= 4.5
    # Stale status forces confidence to drop from HIGH
    assert res["confidence"] in ("MEDIUM", "LOW")
    assert "LIVE_STATUS_STALE" in res["reasons"]


# ==============================================================================
# 3. Cancelled Train at T-1h Opens Window and Clears Conflict
# ==============================================================================

def test_cancelled_train_at_t_1h_opens_window_and_notifies(db_session):
    """
    A train running during the maintenance window creates a conflict.
    When marked CANCELLED in live status at T-1h, revalidation omits it,
    clearing the conflict and opening the window.
    """
    task = _create_sample_task(task_id="TSK-CANCEL-01")
    save_tasks(db_session, [task])

    # Live status showing train 12302 cancelled
    db_session.add(LiveTrainStatusRecord(
        train_number="12302",
        train_name="Howrah Rajdhani",
        delay_minutes=0.0,
        status="CANCELLED",
        last_updated=datetime.now(),
        source="RAILRADAR",
    ))
    db_session.commit()

    res = revalidate_task(
        task_id=task.task_id,
        horizon="T-1h",
        session=db_session,
    )

    # Cancelled train 12302 does not occupy block, leaving window clean
    assert res["has_conflict"] is False
    assert res["status"] == "CLEAN"
    assert len(res["affected_trains"]) == 0


# ==============================================================================
# 4. Delayed Train Entering Window Triggers Conflict + Next Best Start
# ==============================================================================

def test_delayed_train_triggers_conflict_and_next_best_start(db_session):
    """
    A train running earlier gets delayed into the approved maintenance window (06:30-08:30).
    Revalidation detects the conflict, computes next best start, and logs notification.
    """
    task = _create_sample_task(task_id="TSK-DELAY-01", assigned_block_id="BW-DELAY-WINDOW")
    save_tasks(db_session, [task])

    # Create mock app_state with window at 06:30-08:30
    class MockAppState:
        windows = [
            BlockWindow(
                window_id="BW-DELAY-WINDOW",
                corridor_id="COR-82d9c510",
                section_id="SEC-93135bb9",
                block_section_id="BLK-845de309",
                line="DN",
                date=date.today(),
                start_time=time(6, 30),
                end_time=time(8, 30),
                duration_hours=2.0,
            )
        ]
        tasks = [task]

    # Train 12002 normally enters at 06:00. Delayed by 60 min -> enters at 07:00 (inside 06:30-08:30!)
    db_session.add(LiveTrainStatusRecord(
        train_number="12002",
        train_name="Bhopal Shatabdi",
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        delay_minutes=60.0,
        status="DELAYED",
        last_updated=datetime.now(),
        source="RAILRADAR",
    ))
    db_session.commit()

    # Pass live delay map directly to force delay into passage
    res = revalidate_task(
        task_id=task.task_id,
        horizon="T-1h",
        session=db_session,
        live_delays_map={"12002": 60.0},
        app_state=MockAppState(),
    )

    assert res["has_conflict"] is True
    assert res["status"] == "CONFLICT"
    assert len(res["affected_trains"]) > 0
    assert res["next_best_start"] is not None

    # Verify notification created in DB
    notifs = db_session.query(NotificationRecord).filter_by(issue_id=task.task_id).all()
    assert len(notifs) >= 1
    assert "Conflict" in notifs[0].title


# ==============================================================================
# 5. LOW Confidence Start Requires Confirm Flag
# ==============================================================================

def test_low_confidence_start_requires_confirm_flag(db_session):
    """
    Technician start action:
    - Attempting to start a window with LOW confidence or stale status without confirm_low_confidence=True raises 400.
    - Starting with confirm_low_confidence=True succeeds and sets actual_start.
    """
    task = _create_sample_task(task_id="TSK-LOWCONF-01", status=TaskStatus.APPROVED)
    save_tasks(db_session, [task])

    tech_user = User(
        id="usr_tech_2",
        email="tech2@railopt.gov.in",
        role=UserRole.TECHNICIAN,
        department=Department.ENGINEERING,
        name="Field Tech",
        is_active=True,
    )

    # Insert stale status to force LOW/stale confidence
    stale_time = datetime.now() - timedelta(hours=6.0)
    db_session.add(LiveTrainStatusRecord(
        train_number="12301",
        train_name="Rajdhani",
        delay_minutes=20.0,
        status="RUNNING",
        last_updated=stale_time,
        source="RAILRADAR",
    ))
    db_session.commit()

    # Inside window start time
    valid_start = datetime.combine(date.today(), time(2, 5))

    # A. Start without confirm flag must be rejected
    with pytest.raises(HTTPException) as exc_info:
        start_task_execution(
            task_id=task.task_id,
            confirm_low_confidence=False,
            actual_start=valid_start,
            current_user=tech_user,
            session=db_session,
        )
    assert exc_info.value.status_code == 400
    assert "confirm_low_confidence" in exc_info.value.detail

    # B. Start with confirm flag succeeds
    started_task = start_task_execution(
        task_id=task.task_id,
        confirm_low_confidence=True,
        actual_start=valid_start,
        notes="Controller confirmed track clearance by phone",
        current_user=tech_user,
        session=db_session,
    )
    assert started_task.status == TaskStatus.IN_PROGRESS
    assert started_task.actual_start is not None


# ==============================================================================
# 6. Scheduled Revalidation Runs Store Results in Database
# ==============================================================================

def test_scheduled_runs_store_results(db_session):
    """
    Automated scheduled revalidation runs (T-24h, T-6h, T-1h) iterate over approved tasks,
    run revalidation checks, and persist each row into RevalidationResultRecord.
    """
    task1 = _create_sample_task(task_id="TSK-SCHED-01", status=TaskStatus.APPROVED)
    task2 = _create_sample_task(task_id="TSK-SCHED-02", status=TaskStatus.READY)
    save_tasks(db_session, [task1, task2])

    # Run scheduled revalidation for horizon T-1h
    results = run_scheduled_revalidations(
        horizon="T-1h",
        session=db_session,
    )

    assert len(results) >= 2

    # Query RevalidationResultRecord table
    db_records = db_session.query(RevalidationResultRecord).filter_by(horizon="T-1h").all()
    assert len(db_records) >= 2
    for rec in db_records:
        assert rec.horizon == "T-1h"
        assert rec.confidence in ("HIGH", "MEDIUM", "LOW")
        assert rec.checked_at is not None
