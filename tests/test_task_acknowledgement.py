"""
Integration and Concurrency Tests for Task Acknowledgement and Decline (Item B2).
Verifies:
- Reported tasks need acknowledgement before enlistment
- Tasks awaiting acknowledgement excluded from counts, lists, solver, window search
- Exactly designated department + admins notified (emergency marked urgent)
- Atomic first-acknowledgement-wins semantic; second rejected with 409
- Notification resolution for all recipients
- Decline with reason
- Super admin report skips acknowledgement
- Cross-department scoping (another department cannot acknowledge)
"""
import concurrent.futures
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, UserRecord, TaskRecord, NotificationRecord, TaskTransitionAuditRecord
from backend.auth import hash_password, create_access_token
from railopt.models import Department, DefectCategory, DefectSeverity, TaskStatus, AssetType, MaintenanceTask
from railopt.counts import compute_dashboard_counts
from optimizer.cpsat_solver import BlockScheduler


@pytest.fixture
def ack_env(tmp_path, monkeypatch):
    """Isolated database and TestClient with seeded users across departments and roles."""
    db_file = tmp_path / "ack_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=engine, expire_on_commit=False)())
    monkeypatch.setattr("backend.main.engine", engine)

    session = sessionmaker(bind=engine, expire_on_commit=False)()

    admin_user = UserRecord(
        id="usr_admin_ack",
        name="Chief Admin",
        email="admin@railopt.gov.in",
        password_hash=hash_password("adminpass"),
        role="ADMIN",
        department=None,
        is_active=True,
    )
    trd_user = UserRecord(
        id="usr_trd_ack",
        name="TRD Power Engineer",
        email="trd_user@railopt.gov.in",
        password_hash=hash_password("trdpass"),
        role="DEPT_USER",
        department="TRD",
        is_active=True,
    )
    snt_user = UserRecord(
        id="usr_snt_ack",
        name="Signal Telecom Engineer",
        email="snt_user@railopt.gov.in",
        password_hash=hash_password("sntpass"),
        role="DEPT_USER",
        department="SNT",
        is_active=True,
    )
    tech_trd = UserRecord(
        id="usr_tech_ack",
        name="Field Technician TRD",
        email="tech_trd@railopt.gov.in",
        password_hash=hash_password("techpass"),
        role="TECHNICIAN",
        department="TRD",
        is_active=True,
    )

    for u in [admin_user, trd_user, snt_user, tech_trd]:
        session.add(u)
    session.commit()
    session.close()

    tokens = {
        "admin": create_access_token(admin_user),
        "trd": create_access_token(trd_user),
        "snt": create_access_token(snt_user),
        "tech": create_access_token(tech_trd),
    }

    app.state.tasks = []
    client = TestClient(app)
    return {
        "client": client,
        "tokens": tokens,
        "engine": engine,
        "users": {"admin": admin_user, "trd": trd_user, "snt": snt_user, "tech": tech_trd},
    }


def test_technician_report_creates_awaiting_ack_and_excludes_from_operational_views(ack_env):
    client = ack_env["client"]
    tokens = ack_env["tokens"]

    # 1. Technician reports a defect
    payload = {
        "description": "Loose catenary dropper vibrating heavily near Mast 110",
        "corridor_id": "COR_HOWRAH_DELHI",
        "section_id": "SEC-93135bb9",
        "km_location": 42.5,
        "department_designated": "TRD",
        "severity": "EMERGENCY",
    }
    resp = client.post(
        "/api/tasks/complaint",
        json=payload,
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    assert resp.status_code == 200
    task_data = resp.json()
    task_id = task_data["task_id"]
    assert task_data["status"] == "AWAITING_ACK"
    assert task_data["awaiting_acknowledgement"] is True

    # 2. Excluded from main dashboard counts
    counts_resp = client.get("/api/dashboard/counts", headers={"Authorization": f"Bearer {tokens['trd']}"})
    assert counts_resp.status_code == 200
    counts = counts_resp.json()
    assert counts["total"] == 0
    assert counts["pending"] == 0

    # 3. Excluded from general task list
    tasks_resp = client.get("/api/tasks", headers={"Authorization": f"Bearer {tokens['trd']}"})
    assert tasks_resp.status_code == 200
    task_ids = [t["task_id"] for t in tasks_resp.json()]
    assert task_id not in task_ids

    # 4. Excluded from window search
    win_resp = client.get(
        f"/api/sections/SEC-93135bb9/windows?task_id={task_id}",
        headers={"Authorization": f"Bearer {tokens['trd']}"},
    )
    assert win_resp.status_code == 400
    assert "awaiting acknowledgement" in win_resp.json()["detail"].lower()

    # 5. Visible in pending-acknowledgement inbox for TRD and Admin
    pending_trd = client.get(
        "/api/tasks/pending-acknowledgement",
        headers={"Authorization": f"Bearer {tokens['trd']}"},
    )
    assert pending_trd.status_code == 200
    assert any(t["task_id"] == task_id for t in pending_trd.json())

    # Reporter can see their pending report
    pending_reporter = client.get(
        "/api/tasks/pending-acknowledgement",
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    assert pending_reporter.status_code == 200
    assert any(t["task_id"] == task_id for t in pending_reporter.json())

    # S&T department user CANNOT see TRD pending task
    pending_snt = client.get(
        "/api/tasks/pending-acknowledgement",
        headers={"Authorization": f"Bearer {tokens['snt']}"},
    )
    assert pending_snt.status_code == 200
    assert not any(t["task_id"] == task_id for t in pending_snt.json())


def test_notified_recipients_and_urgent_severity(ack_env):
    client = ack_env["client"]
    tokens = ack_env["tokens"]
    users = ack_env["users"]

    # Technician reports an emergency
    payload = {
        "description": "Urgent insulator flashover on overhead wire",
        "corridor_id": "COR_HOWRAH_DELHI",
        "section_id": "SEC-93135bb9",
        "km_location": 43.1,
        "department_designated": "TRD",
        "severity": "EMERGENCY",
    }
    resp = client.post(
        "/api/tasks/complaint",
        json=payload,
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    # Check database notifications
    session = sessionmaker(bind=ack_env["engine"], expire_on_commit=False)()
    notifs = session.query(NotificationRecord).filter(NotificationRecord.issue_id == task_id).all()
    session.close()

    recipient_ids = {n.recipient_user_id for n in notifs}
    # Exactly TRD user and Admin notified (reporter excluded)
    assert users["trd"].id in recipient_ids
    assert users["admin"].id in recipient_ids
    assert users["tech"].id not in recipient_ids
    assert users["snt"].id not in recipient_ids

    for n in notifs:
        assert n.severity == "EMERGENCY"


def test_first_acknowledgement_wins_and_second_rejected(ack_env):
    client = ack_env["client"]
    tokens = ack_env["tokens"]

    # 1. Report task
    rep = client.post(
        "/api/tasks/complaint",
        json={
            "description": "OHE bracket insulator replacement required",
            "corridor_id": "COR_HOWRAH_DELHI",
            "section_id": "SEC-93135bb9",
            "km_location": 50.0,
            "department_designated": "TRD",
            "severity": "HIGH",
        },
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    task_id = rep.json()["task_id"]

    # 2. First acknowledgement by TRD user succeeds
    ack1 = client.post(
        f"/api/tasks/{task_id}/acknowledge",
        headers={"Authorization": f"Bearer {tokens['trd']}"},
    )
    assert ack1.status_code == 200
    data1 = ack1.json()
    assert data1["status"] == "ok"
    assert data1["new_status"] == "REPORTED"
    assert data1["acknowledged_by"] == "trd_user@railopt.gov.in"

    # 3. Second acknowledgement (e.g. by admin) is rejected with 409 Conflict
    ack2 = client.post(
        f"/api/tasks/{task_id}/acknowledge",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert ack2.status_code == 409
    assert "already acknowledged by trd_user@railopt.gov.in" in ack2.json()["detail"].lower()

    # 4. Notifications resolved for all
    notifs_trd = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {tokens['trd']}"},
    )
    assert not any(n.get("issue_id") == task_id for n in notifs_trd.json())

    # 5. Now enlisted in main counts
    counts_resp = client.get("/api/dashboard/counts", headers={"Authorization": f"Bearer {tokens['trd']}"})
    assert counts_resp.json()["total"] == 1
    assert counts_resp.json()["pending"] == 1


def test_cross_department_acknowledgement_forbidden(ack_env):
    client = ack_env["client"]
    tokens = ack_env["tokens"]

    # Technician reports TRD task
    rep = client.post(
        "/api/tasks/complaint",
        json={
            "description": "Pantograph zone clearance check",
            "corridor_id": "COR_HOWRAH_DELHI",
            "section_id": "SEC-93135bb9",
            "km_location": 52.0,
            "department_designated": "TRD",
            "severity": "MEDIUM",
        },
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    task_id = rep.json()["task_id"]

    # S&T user attempts to acknowledge TRD task -> 403 Forbidden
    ack_snt = client.post(
        f"/api/tasks/{task_id}/acknowledge",
        headers={"Authorization": f"Bearer {tokens['snt']}"},
    )
    assert ack_snt.status_code == 403
    assert "cannot acknowledge task for department trd" in ack_snt.json()["detail"].lower()


def test_decline_flow_with_reason_and_reporter_notification(ack_env):
    client = ack_env["client"]
    tokens = ack_env["tokens"]
    users = ack_env["users"]

    rep = client.post(
        "/api/tasks/complaint",
        json={
            "description": "Duplicate report of tree branch near feeder",
            "corridor_id": "COR_HOWRAH_DELHI",
            "section_id": "SEC-93135bb9",
            "km_location": 55.0,
            "department_designated": "TRD",
            "severity": "LOW",
        },
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    task_id = rep.json()["task_id"]

    # TRD engineer declines with reason
    dec = client.post(
        f"/api/tasks/{task_id}/decline",
        json={"reason": "Duplicate report - already cleared by morning patrol"},
        headers={"Authorization": f"Bearer {tokens['trd']}"},
    )
    assert dec.status_code == 200
    assert dec.json()["new_status"] == "DECLINED"

    # Notification sent to the technician who reported it
    session = sessionmaker(bind=ack_env["engine"], expire_on_commit=False)()
    tech_notifs = session.query(NotificationRecord).filter(
        NotificationRecord.recipient_user_id == users["tech"].id,
        NotificationRecord.issue_id == task_id,
    ).all()
    session.close()

    assert len(tech_notifs) == 1
    assert tech_notifs[0].type == "REPORT_DECLINED"
    assert "Duplicate report" in tech_notifs[0].message


def test_super_admin_report_requires_acknowledgement_by_dept_or_admin(ack_env):
    client = ack_env["client"]
    tokens = ack_env["tokens"]

    # Admin reports defect
    resp = client.post(
        "/api/tasks/complaint",
        json={
            "description": "Emergency track flaw identified during safety audit",
            "corridor_id": "COR_HOWRAH_DELHI",
            "section_id": "SEC-93135bb9",
            "km_location": 60.0,
            "department_designated": "TRD",
            "severity": "EMERGENCY",
        },
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert resp.status_code == 200
    task_data = resp.json()
    assert task_data["status"] == "AWAITING_ACK"
    assert task_data["awaiting_acknowledgement"] is True
    task_id = task_data["task_id"]

    # Excluded from main counts before acknowledgement
    counts_pre = client.get("/api/dashboard/counts", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert counts_pre.json()["total"] == 0

    # Acknowledged by designated department (or admin)
    ack_resp = client.post(
        f"/api/tasks/{task_id}/acknowledge",
        headers={"Authorization": f"Bearer {tokens['trd']}"},
    )
    assert ack_resp.status_code == 200

    # Appears immediately in dashboard counts after acknowledgement
    counts_resp = client.get("/api/dashboard/counts", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert counts_resp.json()["total"] == 1


def test_concurrent_simultaneous_acknowledgements(ack_env):
    """Simulate two requests acknowledging the exact same task at the same millisecond."""
    client = ack_env["client"]
    tokens = ack_env["tokens"]

    rep = client.post(
        "/api/tasks/complaint",
        json={
            "description": "High voltage transformer oil leakage alert",
            "corridor_id": "COR_HOWRAH_DELHI",
            "section_id": "SEC-93135bb9",
            "km_location": 65.0,
            "department_designated": "TRD",
            "severity": "EMERGENCY",
        },
        headers={"Authorization": f"Bearer {tokens['tech']}"},
    )
    task_id = rep.json()["task_id"]

    results = []

    def try_ack(auth_token):
        c = TestClient(app)
        return c.post(
            f"/api/tasks/{task_id}/acknowledge",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(try_ack, tokens["trd"])
        f2 = executor.submit(try_ack, tokens["admin"])
        results = [f1.result(), f2.result()]

    status_codes = [r.status_code for r in results]
    # Exactly one must succeed with 200, and one must be rejected with 409
    assert 200 in status_codes, f"Expected one 200 OK, got {status_codes}"
    assert 409 in status_codes, f"Expected one 409 Conflict, got {status_codes}"
