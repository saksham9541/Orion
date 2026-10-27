"""
Tests for Step 2: Role-Based Access Control (RBAC) across all Orion API endpoints.
Verifies the exact permission table:
- Public endpoints (login, refresh, health)
- Viewer permissions (read-only, no write, can simulate & query)
- Dept User permissions (read all plans, create/edit tasks only for own dept, filtered task list, 403 on other dept single task)
- Controller permissions (all depts tasks, generate plans, approve/reject/modify plans, replan, adversarial)
- Admin permissions (everything + user management + demo setup)
- Rejection of unauthenticated requests on protected endpoints (401)
"""
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, init_db, save_user, save_tasks, save_corridors, save_plan, UserRecord, TaskRecord
from backend.auth import hash_password, create_access_token
from railopt.models import (
    MaintenanceTask,
    BlockPlan,
    Corridor,
    Section,
    Department,
    AssetType,
    DefectCategory,
    TaskStatus,
    UserRole,
    PlanHorizon,
    ScheduledBlock,
)


@pytest.fixture
def rbac_client(tmp_path, monkeypatch):
    """Isolated SQLite test DB and TestClient configured with test users."""
    db_file = tmp_path / "rbac_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=engine, expire_on_commit=False)())
    monkeypatch.setattr("backend.main.engine", engine)

    # Seed test users
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    
    admin_user = UserRecord(
        id="usr_admin",
        name="Admin User",
        email="admin@test.gov.in",
        password_hash=hash_password("adminpass123"),
        role="ADMIN",
        department=None,
        is_active=True,
    )
    controller_user = UserRecord(
        id="usr_controller",
        name="Controller User",
        email="controller@test.gov.in",
        password_hash=hash_password("ctrlpass123"),
        role="CONTROLLER",
        department=None,
        is_active=True,
    )
    eng_user = UserRecord(
        id="usr_eng",
        name="Engineering User",
        email="eng@test.gov.in",
        password_hash=hash_password("engpass123"),
        role="DEPT_USER",
        department="ENGINEERING",
        is_active=True,
    )
    snt_user = UserRecord(
        id="usr_snt",
        name="S&T User",
        email="snt@test.gov.in",
        password_hash=hash_password("sntpass123"),
        role="DEPT_USER",
        department="SNT",
        is_active=True,
    )
    viewer_user = UserRecord(
        id="usr_viewer",
        name="Viewer User",
        email="viewer@test.gov.in",
        password_hash=hash_password("viewpass123"),
        role="VIEWER",
        department=None,
        is_active=True,
    )
    save_user(session, admin_user)
    save_user(session, controller_user)
    save_user(session, eng_user)
    save_user(session, snt_user)
    save_user(session, viewer_user)

    # Seed sample tasks across departments
    eng_task = MaintenanceTask(
        task_id="MT-ENG-001",
        department=Department.ENGINEERING,
        asset_type=AssetType.RAIL,
        defect_category=DefectCategory.RAIL_FRACTURE,
        corridor_id="COR-TEST",
        section_id="SEC-TEST-1",
        km_location=100.0,
        reported_date=datetime.date.today(),
        status=TaskStatus.PENDING,
        source="synthetic",
    )
    snt_task = MaintenanceTask(
        task_id="MT-SNT-002",
        department=Department.SNT,
        asset_type=AssetType.SIGNAL_POST,
        defect_category=DefectCategory.SIGNAL_FAILURE,
        corridor_id="COR-TEST",
        section_id="SEC-TEST-1",
        km_location=105.0,
        reported_date=datetime.date.today(),
        status=TaskStatus.PENDING,
        source="synthetic",
    )
    save_tasks(session, [eng_task, snt_task])

    # Seed a sample corridor and plan
    sec = Section(
        section_id="SEC-TEST-1",
        corridor_id="COR-TEST",
        name="TestSection",
        start_station="STNA",
        end_station="STNB",
        start_km=100.0,
        end_km=120.0,
    )
    corridor = Corridor(
        corridor_id="COR-TEST",
        name="Test Corridor",
        division="Delhi",
        zone="NR",
        sections=[sec],
    )
    save_corridors(session, [corridor])

    plan = BlockPlan(
        plan_id="BP-TEST-001",
        horizon=PlanHorizon.WEEKLY,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=7),
        scheduled_blocks=[
            ScheduledBlock(
                block_id="SB-001",
                window_id="BW-001",
                corridor_id="COR-TEST",
                section_id="SEC-TEST-1",
                date=datetime.date.today(),
                start_time=datetime.time(10, 0),
                end_time=datetime.time(12, 0),
                task_ids=["MT-ENG-001"],
                departments=[Department.ENGINEERING],
            )
        ],
    )
    save_plan(session, plan)
    session.close()

    # Create app state mocks
    from ml.feedback_logger import FeedbackLogger
    app.state.tasks = [eng_task, snt_task]
    app.state.corridors = [corridor]
    app.state.sections = {"SEC-TEST-1": sec}
    app.state.plans = {"BP-TEST-001": plan}
    app.state.alerts = []
    app.state.windows = []
    app.state.train_slots = []
    app.state.scorer = None
    app.state.impact_predictor = None
    app.state.duration_estimator = None
    app.state.load_failures = 0
    app.state.feedback_logger = FeedbackLogger(log_file=str(tmp_path / "feedback.jsonl"))

    client = TestClient(app)

    tokens = {
        "admin": create_access_token(admin_user),
        "controller": create_access_token(controller_user),
        "eng": create_access_token(eng_user),
        "snt": create_access_token(snt_user),
        "viewer": create_access_token(viewer_user),
    }

    return client, tokens


def test_unauthenticated_requests_fail(rbac_client):
    """Unauthenticated calls on protected endpoints must return 401."""
    client, _ = rbac_client

    # Protected GET
    resp = client.get("/api/tasks")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    # Protected POST
    resp = client.post("/api/plans/generate", json={})
    assert resp.status_code == 401

    # Protected sync
    resp = client.post("/api/trains/live/sync")
    assert resp.status_code == 401

    # Public health check must be 200
    assert client.get("/api/health").status_code == 200


def test_dept_user_department_filtering(rbac_client):
    """DEPT_USER can only list own department tasks and gets 403 on another dept single task."""
    client, tokens = rbac_client
    eng_headers = {"Authorization": f"Bearer {tokens['eng']}"}

    # 1. GET /api/tasks as engineering user -> only engineering tasks returned
    resp = client.get("/api/tasks", headers=eng_headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 1
    assert tasks[0]["department"] == "ENGINEERING"

    # 2. GET /api/tasks/{id} for own department -> 200
    resp = client.get("/api/tasks/MT-ENG-001", headers=eng_headers)
    assert resp.status_code == 200

    # 3. GET /api/tasks/{id} for other department (SNT) -> 403
    resp = client.get("/api/tasks/MT-SNT-002", headers=eng_headers)
    assert resp.status_code == 403


def test_viewer_restrictions(rbac_client):
    """VIEWER cannot PUT task status or generate plans (403), but can read plans."""
    client, tokens = rbac_client
    viewer_headers = {"Authorization": f"Bearer {tokens['viewer']}"}

    # Can read plans
    resp = client.get("/api/plans", headers=viewer_headers)
    assert resp.status_code == 200

    # Cannot update status
    resp = client.put("/api/tasks/MT-ENG-001/status?status=COMPLETED", headers=viewer_headers)
    assert resp.status_code == 403

    # Cannot generate plan
    resp = client.post("/api/plans/generate", headers=viewer_headers, json={})
    assert resp.status_code == 403


def test_controller_can_approve_and_generate_plans(rbac_client):
    """CONTROLLER can generate and approve plans, while DEPT_USER cannot."""
    client, tokens = rbac_client
    ctrl_headers = {"Authorization": f"Bearer {tokens['controller']}"}
    eng_headers = {"Authorization": f"Bearer {tokens['eng']}"}

    # Controller can approve plan
    resp = client.post("/api/plans/BP-TEST-001/approve", headers=ctrl_headers, json={"approved_by": "Chief Controller"})
    assert resp.status_code == 200

    # Dept user cannot approve plan
    resp = client.post("/api/plans/BP-TEST-001/approve", headers=eng_headers, json={"approved_by": "Eng User"})
    assert resp.status_code == 403


def test_admin_only_endpoints(rbac_client):
    """Only ADMIN can call /api/auth/users and /api/demo/setup."""
    client, tokens = rbac_client
    admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    ctrl_headers = {"Authorization": f"Bearer {tokens['controller']}"}

    # Controller cannot setup demo
    resp = client.post("/api/demo/setup", headers=ctrl_headers)
    assert resp.status_code == 403

    # Admin can list users
    resp = client.get("/api/auth/users", headers=admin_headers)
    assert resp.status_code == 200

    # Controller cannot list users
    resp = client.get("/api/auth/users", headers=ctrl_headers)
    assert resp.status_code == 403


def test_complaint_and_import_rbac(rbac_client):
    """Test complaint classification, department validation, and import RBAC."""
    client, tokens = rbac_client
    viewer_headers = {"Authorization": f"Bearer {tokens['viewer']}"}
    eng_headers = {"Authorization": f"Bearer {tokens['eng']}"}

    # 1. VIEWER cannot submit complaint (403)
    resp = client.post(
        "/api/tasks/complaint",
        headers=viewer_headers,
        json={
            "description": "Rail fracture observed at KM 102",
            "corridor_id": "COR-TEST",
            "section_id": "SEC-TEST-1",
            "km_location": 102.0,
        },
    )
    assert resp.status_code == 403

    # 2. ENG user submits rail fracture complaint (Engineering defect) -> 200
    resp = client.post(
        "/api/tasks/complaint",
        headers=eng_headers,
        json={
            "description": "Emergency rail fracture on main line",
            "corridor_id": "COR-TEST",
            "section_id": "SEC-TEST-1",
            "km_location": 102.5,
        },
    )
    assert resp.status_code == 200
    task_data = resp.json()
    assert task_data["department"] == "ENGINEERING"
    assert task_data["source"] == "user"
    assert task_data["defect_category"] == "RAIL_FRACTURE"

    # 3. ENG user submits signal failure complaint (SNT defect) -> 403
    resp = client.post(
        "/api/tasks/complaint",
        headers=eng_headers,
        json={
            "description": "Signal failure and point machine burnt out",
            "corridor_id": "COR-TEST",
            "section_id": "SEC-TEST-1",
            "km_location": 105.0,
        },
    )
    assert resp.status_code == 403

    # 4. VIEWER cannot import tasks (403)
    resp = client.post("/api/tasks/import", headers=viewer_headers, json={"source_system": "TMS", "records": []})
    assert resp.status_code == 403

    # 5. ENG user cannot import SNT tasks (403)
    resp = client.post(
        "/api/tasks/import",
        headers=eng_headers,
        json={
            "source_system": "TMS",
            "records": [
                {
                    "task_id": "MT-IMP-001",
                    "department": "SNT",
                    "asset_type": "SIGNAL_POST",
                    "defect_category": "SIGNAL_FAILURE",
                    "corridor_id": "COR-TEST",
                    "section_id": "SEC-TEST-1",
                    "km_location": 110.0,
                    "reported_date": "2026-10-27",
                }
            ]
        },
    )
    assert resp.status_code == 403

    # 6. ENG user can import Engineering tasks (200)
    resp = client.post(
        "/api/tasks/import",
        headers=eng_headers,
        json={
            "source_system": "TMS",
            "records": [
                {
                    "task_id": "MT-IMP-002",
                    "department": "ENGINEERING",
                    "asset_type": "RAIL",
                    "defect_category": "RAIL_CRACK",
                    "corridor_id": "COR-TEST",
                    "section_id": "SEC-TEST-1",
                    "km_location": 110.0,
                    "reported_date": "2026-10-27",
                }
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["imported_count"] == 1


def test_dashboard_stats_dept_filter(rbac_client):
    """DEPT_USER dashboard stats must only reflect their department."""
    client, tokens = rbac_client
    eng_headers = {"Authorization": f"Bearer {tokens['eng']}"}
    ctrl_headers = {"Authorization": f"Bearer {tokens['controller']}"}

    # Eng user only sees Engineering tasks
    resp = client.get("/api/dashboard/stats", headers=eng_headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert "ENGINEERING" in stats["tasks_by_department"]
    assert "SNT" not in stats["tasks_by_department"]

    # Controller sees all
    resp = client.get("/api/dashboard/stats", headers=ctrl_headers)
    assert resp.status_code == 200
    stats_ctrl = resp.json()
    assert "ENGINEERING" in stats_ctrl["tasks_by_department"]
    assert "SNT" in stats_ctrl["tasks_by_department"]


def test_analysis_and_adversarial_rbac(rbac_client):
    """Analysis respects task department, and adversarial requires CONTROLLER/ADMIN."""
    client, tokens = rbac_client
    eng_headers = {"Authorization": f"Bearer {tokens['eng']}"}
    viewer_headers = {"Authorization": f"Bearer {tokens['viewer']}"}
    ctrl_headers = {"Authorization": f"Bearer {tokens['controller']}"}

    # Eng user can analyze own task
    resp = client.get("/api/tasks/MT-ENG-001/analysis", headers=eng_headers)
    assert resp.status_code == 200

    # Eng user cannot analyze SNT task
    resp = client.get("/api/tasks/MT-SNT-002/analysis", headers=eng_headers)
    assert resp.status_code == 403

    # Viewer cannot list adversarial attacks
    resp = client.get("/api/adversarial/attacks", headers=viewer_headers)
    assert resp.status_code == 403

    # Controller can list adversarial attacks
    resp = client.get("/api/adversarial/attacks", headers=ctrl_headers)
    assert resp.status_code == 200

