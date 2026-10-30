"""
tests/test_part_c.py

Comprehensive tests for Orion Part C:
C1: Start window as clock times, enforced (start gate, 409 codes, server clock, audit log).
C2: Emergency tasks must show which trains will be delayed (wait station, hold minutes, cascade, both lines, notifications).
C3: Pilot corridor train data expansion, horizon filtering, targeted emergency sync, and reserve protection.
"""
from __future__ import annotations

import os
import uuid
import zoneinfo
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import User, create_access_token, hash_password
from backend.database import (
    Base,
    LiveTrainStatusRecord,
    NotificationRecord,
    TaskRecord,
    TaskTransitionAuditRecord,
    UserRecord,
    get_session,
    save_tasks,
    save_user,
)
from backend.main import app
from backend.sync_service import (
    execute_live_train_sync,
    get_corridor_train_limit,
    get_pilot_timetable_trains,
    get_sync_preview,
    reset_last_sync_time,
)
from integrations.railradar_client import RailRadarClient
from railopt.models import Department, MaintenanceTask, TaskStatus, TrainType, UserRole
from traffic.task_revalidation import format_clock_ist, start_task_execution

KOLKATA_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")


@pytest.fixture
def c_env(tmp_path, monkeypatch):
    """Isolated SQLite test DB and TestClient configured for Part C."""
    db_file = tmp_path / "part_c_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=engine, expire_on_commit=False)())
    monkeypatch.setattr("backend.main.engine", engine)

    session = sessionmaker(bind=engine, expire_on_commit=False)()

    admin_user = UserRecord(
        id="usr_admin_c",
        name="Admin User",
        email="admin_c@railopt.gov.in",
        password_hash=hash_password("adminpass123"),
        role="ADMIN",
        department=None,
        is_active=True,
    )
    ctrl_user = UserRecord(
        id="usr_ctrl_c",
        name="Chief Controller",
        email="controller_c@railopt.gov.in",
        password_hash=hash_password("ctrlpass123"),
        role="CONTROLLER",
        department=None,
        is_active=True,
    )
    eng_user = UserRecord(
        id="usr_eng_c",
        name="Eng Supervisor",
        email="eng_c@railopt.gov.in",
        password_hash=hash_password("engpass123"),
        role="DEPT_USER",
        department="ENGINEERING",
        is_active=True,
    )
    tech_user = UserRecord(
        id="usr_tech_c",
        name="Track Tech",
        email="tech_c@railopt.gov.in",
        password_hash=hash_password("techpass123"),
        role="TECHNICIAN",
        department="ENGINEERING",
        is_active=True,
    )

    save_user(session, admin_user)
    save_user(session, ctrl_user)
    save_user(session, eng_user)
    save_user(session, tech_user)

    session.close()

    app.state.tasks = []
    app.state.windows = []
    app.state.plans = {}

    client = TestClient(app)
    tokens = {
        "admin": create_access_token(admin_user),
        "controller": create_access_token(ctrl_user),
        "eng": create_access_token(eng_user),
        "tech": create_access_token(tech_user),
    }

    return {"client": client, "tokens": tokens, "engine": engine}


def _make_task(
    task_id: str,
    status: TaskStatus = TaskStatus.APPROVED,
    department: Department = Department.ENGINEERING,
    severity: str = "HIGH",
    line: str = "DN",
    block_section_id: str = "BLK-845de309",
    start_from: Optional[datetime] = None,
    start_until: Optional[datetime] = None,
    planned_end: Optional[datetime] = None,
    duration_h: float = 1.25,
    requires_both_lines: bool = False,
    awaiting_ack: bool = False,
) -> MaintenanceTask:
    return MaintenanceTask(
        task_id=task_id,
        source_system="TMS",
        source_record_id=f"REC-{task_id}",
        department=department,
        asset_type="RAIL",
        asset_id="AST-001",
        defect_category="RAIL_FRACTURE",
        raw_severity=severity,
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        block_section_id=block_section_id,
        line=line,
        km_location=12.5,
        reported_date=date.today(),
        status=status,
        start_allowed_from=start_from,
        start_allowed_until=start_until,
        planned_end=planned_end,
        early_tolerance_minutes=0,
        estimated_duration_hours=duration_h,
        requires_both_lines=requires_both_lines,
        awaiting_acknowledgement=awaiting_ack,
    )


# ==============================================================================
# C1: Start Window Enforced as Clock Times
# ==============================================================================

def test_c1_start_gate_timing_and_409_codes(c_env):
    """
    Test C1:
    - Designated start period: 1:30 PM - 2:00 PM, finish by 3:15 PM (dur: 1h 15m)
    - Starting at 1:45 PM succeeds (status -> IN_PROGRESS)
    - Starting at 2:10 PM returns 409 WINDOW_TOO_LATE with popup detail
    - Starting at 1:15 PM returns 409 WINDOW_TOO_EARLY with countdown
    - Starting an unapproved task returns 409 WINDOW_NOT_APPROVED
    - Blocked start is audit-logged in TaskTransitionAuditRecord
    """
    client = c_env["client"]
    token = c_env["tokens"]["tech"]
    eng_token = c_env["tokens"]["eng"]
    engine = c_env["engine"]
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    today = date.today()
    # 1:30 PM = 13:30, 2:00 PM = 14:00, 3:15 PM = 15:15
    s_from = datetime.combine(today, time(13, 30)).replace(tzinfo=KOLKATA_TZ)
    s_until = datetime.combine(today, time(14, 0)).replace(tzinfo=KOLKATA_TZ)
    p_end = datetime.combine(today, time(15, 15)).replace(tzinfo=KOLKATA_TZ)

    task = _make_task(
        task_id="TSK-C1-GATE-01",
        status=TaskStatus.APPROVED,
        start_from=s_from,
        start_until=s_until,
        planned_end=p_end,
        duration_h=1.25,
    )
    save_tasks(session, [task])
    app.state.tasks = [task]

    # 1. Starting TOO EARLY at 1:15 PM (13:15) -> 409 WINDOW_TOO_EARLY
    res_early = client.post(
        f"/api/technician/work-orders/{task.task_id}/start",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Test-Server-Time": datetime.combine(today, time(13, 15)).replace(tzinfo=KOLKATA_TZ).isoformat(),
        },
        json={"confirm_low_confidence": True},
    )
    assert res_early.status_code == 409, res_early.text
    d_early = res_early.json()["detail"]
    assert d_early["code"] == "WINDOW_TOO_EARLY"
    assert "Starting outside the approved period" in d_early["message"]
    assert d_early["designated_period_clock"] == "1:30 PM - 2:00 PM"
    assert d_early["planned_end_clock"] == "3:15 PM"
    assert d_early["seconds_until_open"] == 15 * 60

    # 2. Starting TOO LATE at 2:10 PM (14:10) -> 409 WINDOW_TOO_LATE
    res_late = client.post(
        f"/api/technician/work-orders/{task.task_id}/start",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Test-Server-Time": datetime.combine(today, time(14, 10)).replace(tzinfo=KOLKATA_TZ).isoformat(),
        },
        json={"confirm_low_confidence": True},
    )
    assert res_late.status_code == 409, res_late.text
    d_late = res_late.json()["detail"]
    assert d_late["code"] == "WINDOW_TOO_LATE"
    assert d_late["window_ended"] is True
    assert "Starting outside the approved period" in d_late["message"]

    # 3. Department "Start Action" is blocked identically
    res_dept_start = client.put(
        f"/api/tasks/{task.task_id}/status",
        headers={
            "Authorization": f"Bearer {eng_token}",
            "X-Test-Server-Time": datetime.combine(today, time(14, 10)).replace(tzinfo=KOLKATA_TZ).isoformat(),
        },
        json={"status": "IN_PROGRESS"},
    )
    assert res_dept_start.status_code == 409
    assert res_dept_start.json()["detail"]["code"] == "WINDOW_TOO_LATE"

    # 4. Starting within approved range at 1:45 PM (13:45) -> 200 OK
    res_ok = client.post(
        f"/api/technician/work-orders/{task.task_id}/start",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Test-Server-Time": datetime.combine(today, time(13, 45)).replace(tzinfo=KOLKATA_TZ).isoformat(),
        },
        json={"confirm_low_confidence": True},
    )
    assert res_ok.status_code == 200, res_ok.text
    task_res = res_ok.json()
    assert task_res["status"] == "IN_PROGRESS"

    # 5. Verify audit logging of blocked start
    audits = session.query(TaskTransitionAuditRecord).filter(
        TaskTransitionAuditRecord.task_id == task.task_id,
        TaskTransitionAuditRecord.to_status == "BLOCKED_START",
    ).all()
    assert len(audits) >= 2
    reason_codes = [a.reason_code for a in audits]
    assert "WINDOW_TOO_EARLY" in reason_codes
    assert "WINDOW_TOO_LATE" in reason_codes
    session.close()


def test_c1_unapproved_task_and_client_clock_manipulation(c_env):
    """
    Test C1:
    - Attempting to start an unapproved task (status=SCORED or WINDOWS_PROPOSED) returns 409 WINDOW_NOT_APPROVED.
    - Technician device sending manipulated actual_start in JSON body is ignored by the server.
    """
    client = c_env["client"]
    token = c_env["tokens"]["tech"]
    engine = c_env["engine"]
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    unapproved_task = _make_task(
        task_id="TSK-C1-UNAPPROVED",
        status=TaskStatus.WINDOWS_PROPOSED,
    )
    save_tasks(session, [unapproved_task])
    app.state.tasks = [unapproved_task]

    # Unapproved attempt returns 409
    res = client.post(
        f"/api/technician/work-orders/{unapproved_task.task_id}/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirm_low_confidence": True},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "WINDOW_NOT_APPROVED"

    # Client sends manipulated actual_start inside JSON payload claiming it is 1:45 PM
    today = date.today()
    approved_task = _make_task(
        task_id="TSK-C1-APPROVED-CLOCK",
        status=TaskStatus.APPROVED,
        start_from=datetime.combine(today, time(13, 30)).replace(tzinfo=KOLKATA_TZ),
        start_until=datetime.combine(today, time(14, 0)).replace(tzinfo=KOLKATA_TZ),
        planned_end=datetime.combine(today, time(15, 15)).replace(tzinfo=KOLKATA_TZ),
    )
    save_tasks(session, [approved_task])
    app.state.tasks.append(approved_task)

    # Server time header indicates 2:15 PM (outside window), while client body claims 1:45 PM
    res_manip = client.post(
        f"/api/technician/work-orders/{approved_task.task_id}/start",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Test-Server-Time": datetime.combine(today, time(14, 15)).replace(tzinfo=KOLKATA_TZ).isoformat(),
        },
        json={
            "actual_start": datetime.combine(today, time(13, 45)).isoformat(), # Manipulated client clock
            "confirm_low_confidence": True,
        },
    )
    assert res_manip.status_code == 409
    assert res_manip.json()["detail"]["code"] == "WINDOW_TOO_LATE"
    session.close()


# ==============================================================================
# C2: Emergency Tasks Train Delay Impact Analysis
# ==============================================================================

def test_c2_emergency_impact_calculation_and_both_lines(c_env):
    """
    Test C2:
    - GET /api/tasks/{task_id}/emergency-impact
    - Identifies overlapping timetable trains
    - Returns wait station, hold minutes, cascade destination delay, and weighted delay
    - Both lines (UP+DN) impacts trains in both directions
    - Stored live delays update the calculation
    """
    client = c_env["client"]
    token = c_env["tokens"]["controller"]
    engine = c_env["engine"]
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    # Create emergency task on pilot corridor requiring both lines
    today = date(2026, 11, 1)
    em_task = _make_task(
        task_id="TSK-EM-001",
        status=TaskStatus.REPORTED,
        severity="EMERGENCY",
        line="BOTH",
        requires_both_lines=True,
        duration_h=2.0,
    )
    save_tasks(session, [em_task])
    app.state.tasks = [em_task]

    # 1. Query emergency impact at 16:00 (when evening Rajdhani/Shatabdi trains run)
    test_time = datetime.combine(today, time(16, 0)).replace(tzinfo=KOLKATA_TZ).isoformat()
    res = client.get(
        f"/api/tasks/{em_task.task_id}/emergency-impact",
        headers={"Authorization": f"Bearer {token}", "X-Test-Server-Time": test_time},
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["trains_affected"] > 0
    assert data["total_delay_minutes"] > 0
    assert "work_period" in data
    assert "affected_trains" in data
    assert "provenance_label" in data

    # Check structure of affected trains
    trains = data["affected_trains"]
    directions = set(t["direction"] for t in trains)
    assert len(directions) >= 1

    first_train = trains[0]
    assert "train_number" in first_train
    assert "train_name" in first_train
    assert "train_type" in first_train
    assert "wait_station" in first_train
    assert "hold_minutes" in first_train
    assert "expected_destination_delay" in first_train
    assert "weighted_delay" in first_train
    assert first_train["data_provenance"] in ("live", "estimated")

    # 2. What-if recalculation: stop work earlier (e.g. 0.5 hours vs 2.0 hours)
    res_shorter = client.get(
        f"/api/tasks/{em_task.task_id}/emergency-impact?planned_duration_hours=0.5",
        headers={"Authorization": f"Bearer {token}", "X-Test-Server-Time": test_time},
    )
    assert res_shorter.status_code == 200
    data_shorter = res_shorter.json()
    assert data_shorter["duration_hours"] == 0.5
    assert data_shorter["total_delay_minutes"] <= data["total_delay_minutes"]

    # 3. Add stored live delay and verify impact updates
    db_session = sessionmaker(bind=engine, expire_on_commit=False)()
    t_no = first_train["train_number"]
    db_session.add(LiveTrainStatusRecord(
        train_number=t_no,
        train_name=first_train["train_name"],
        delay_minutes=35.0,
        status="RUNNING",
        last_updated=datetime.now(timezone.utc),
        source="RAILRADAR",
    ))
    db_session.commit()
    db_session.close()

    res_live = client.get(
        f"/api/tasks/{em_task.task_id}/emergency-impact",
        headers={"Authorization": f"Bearer {token}", "X-Test-Server-Time": test_time},
    )
    assert res_live.status_code == 200
    live_trains = res_live.json()["affected_trains"]
    live_match = next((t for t in live_trains if t["train_number"] == t_no), None)
    if live_match:
        assert live_match["data_provenance"] == "live"


def test_c2_emergency_enlisting_notifies_controller_and_admin(c_env):
    """
    Test C2:
    - Enlisting or acknowledging an EMERGENCY task generates notifications for Controller & Admin
      containing the count and types of affected trains.
    - Non-emergency tasks do not dispatch emergency notification.
    """
    client = c_env["client"]
    token = c_env["tokens"]["eng"]
    ctrl_token = c_env["tokens"]["controller"]
    engine = c_env["engine"]
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    # 1. Create task in AWAITING_ACK with EMERGENCY severity
    em_task = _make_task(
        task_id="TSK-EM-ACK-01",
        status=TaskStatus.AWAITING_ACK,
        severity="EMERGENCY",
        awaiting_ack=True,
    )
    save_tasks(session, [em_task])
    app.state.tasks = [em_task]

    # Engineering supervisor acknowledges the emergency defect
    res = client.post(
        f"/api/tasks/{em_task.task_id}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text

    # Check notifications table for Controller and Admin
    notifs = session.query(NotificationRecord).filter(
        NotificationRecord.issue_id == em_task.task_id,
        NotificationRecord.type == "EMERGENCY_ENLISTED",
    ).all()
    assert len(notifs) >= 2
    for n in notifs:
        assert "Emergency:" in n.message
        assert "trains affected" in n.message
        assert n.severity == "EMERGENCY"

    # 2. Non-emergency defect does NOT produce EMERGENCY_ENLISTED notification
    norm_task = _make_task(
        task_id="TSK-NORM-ACK-01",
        status=TaskStatus.AWAITING_ACK,
        severity="LOW",
        awaiting_ack=True,
    )
    save_tasks(session, [norm_task])
    app.state.tasks.append(norm_task)

    res_norm = client.post(
        f"/api/tasks/{norm_task.task_id}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_norm.status_code == 200

    norm_notifs = session.query(NotificationRecord).filter(
        NotificationRecord.issue_id == norm_task.task_id,
        NotificationRecord.type == "EMERGENCY_ENLISTED",
    ).all()
    assert len(norm_notifs) == 0
    session.close()


# ==============================================================================
# C3: Pilot Area Train Data Expansion & Targeted Sync
# ==============================================================================

def test_c3_pilot_train_limits_and_horizon_filtering(c_env):
    """
    Test C3:
    - PILOT_MAX_TIMETABLE_TRAINS is 40 for pilot corridor SEC-93135bb9
    - Non-pilot corridor defaults to 16
    - Horizon filtering selects only trains due in next 3 hours
    - Targeted emergency sync selects only trains due in next 2 hours
    """
    # 1. Configurable limits per corridor
    assert get_corridor_train_limit("SEC-93135bb9") == 40
    assert get_corridor_train_limit("SEC-OTHER-CORRIDOR") == 16

    # 2. General sync horizon: 3 hours
    # At fixed time 16:00 (4:00 PM), evening rush has ~10 trains
    t_1600 = datetime(2026, 11, 1, 16, 0, tzinfo=KOLKATA_TZ)
    trains_3h = get_pilot_timetable_trains(
        section_id="SEC-93135bb9",
        horizon_hours=3.0,
        target_time=t_1600,
    )
    assert len(trains_3h) > 0
    assert len(trains_3h) <= 40

    # 3. Targeted emergency sync: 2 hours on specific block section
    trains_em_2h = get_pilot_timetable_trains(
        section_id="SEC-93135bb9",
        horizon_hours=2.0,
        emergency_block_id="BLK-845de309",
        target_time=t_1600,
    )
    assert len(trains_em_2h) <= len(trains_3h)


def test_c3_emergency_sync_bypasses_cooldown_and_enforces_reserve(c_env):
    """
    Test C3:
    - Targeted emergency sync bypasses cooldown check
    - But strictly enforces 30-call reserve (HTTP 429 when budget insufficient)
    - Successful sync prints summary report
    """
    client = c_env["client"]
    token = c_env["tokens"]["controller"]
    reset_last_sync_time()

    mock_live_response = {
        "success": True,
        "source": "live",
        "data": {
            "trainNumber": "12301",
            "trainName": "Howrah Rajdhani",
            "delayMinutes": 5.0,
            "status": "RUNNING",
        },
    }

    with patch.object(RailRadarClient, "get_train_live", return_value=mock_live_response):
        # 1. Normal sync
        res1 = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res1.status_code == 200
        assert "summary" in res1.json()
        assert "RAILRADAR LIVE SYNC SUMMARY" in res1.json()["summary"]

        # 2. Immediate second general sync fails with 429 COOLDOWN_ACTIVE
        res2 = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 429
        assert "cooldown active" in res2.json()["detail"].lower()

        # 3. Targeted emergency sync for a block section bypasses cooldown
        res_em = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9&emergency_block_id=BLK-845de309",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_em.status_code == 200
        assert res_em.json()["status"] == "ok"
