"""
Unit and integration tests for Orion unified dashboard counts and invariants (Item A4).
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, UserRecord
from backend.auth import hash_password, create_access_token
from railopt.models import Department, DefectCategory, MaintenanceTask, TaskStatus, AssetType
from railopt.counts import (
    STATUS_TO_BUCKET,
    STATUS_TO_STAGE,
    TaskBucket,
    PipelineStage,
    compute_dashboard_counts,
    get_status_bucket,
    get_pipeline_stage,
)


def _create_task_with_status(status: TaskStatus, dept: Department = Department.TRD, awaiting_ack: bool = False) -> MaintenanceTask:
    t = MaintenanceTask(
        task_id=f"T-{status.value}",
        department=dept,
        asset_type=AssetType.RAIL,
        defect_category=DefectCategory.RAIL_FRACTURE,
        corridor_id="CORR-01",
        section_id="SEC-93135bb9",
        km_location=12.5,
        reported_date=date.today(),
        status=status,
    )
    if awaiting_ack:
        setattr(t, "awaiting_acknowledgement", True)
    return t


def test_every_status_mapped_to_exactly_one_bucket_and_stage():
    """Verify all 22 TaskStatus enum values are mapped to exactly one bucket and one stage."""
    all_statuses = list(TaskStatus)
    assert len(all_statuses) == 22

    for st in all_statuses:
        assert st in STATUS_TO_BUCKET, f"Status {st} missing from STATUS_TO_BUCKET"
        assert st in STATUS_TO_STAGE, f"Status {st} missing from STATUS_TO_STAGE"

        bucket = get_status_bucket(st)
        assert isinstance(bucket, TaskBucket)

        stage = get_pipeline_stage(st)
        assert isinstance(stage, PipelineStage)


def test_dashboard_counts_invariants_across_all_statuses():
    """Seed tasks covering all 20 statuses and verify all mathematical invariants."""
    seeded_tasks = []
    for st in TaskStatus:
        seeded_tasks.append(_create_task_with_status(st, dept=Department.TRD))
        seeded_tasks.append(_create_task_with_status(st, dept=Department.SNT))
        seeded_tasks.append(_create_task_with_status(st, dept=Department.ENGINEERING))

    # Add a task awaiting acknowledgement (must be excluded)
    seeded_tasks.append(_create_task_with_status(TaskStatus.REPORTED, dept=Department.TRD, awaiting_ack=True))

    res = compute_dashboard_counts(seeded_tasks)

    # 21 enlisted statuses * 3 departments = 63 valid tasks (AWAITING_ACK and awaiting_ack excluded)
    assert res["total"] == 63

    # Invariant 1: total == sum of bucket counts
    assert res["total"] == res["pending"] + res["active_scheduled"] + res["resolved"]
    assert res["total"] == (
        res["buckets"]["pending"] + res["buckets"]["active_scheduled"] + res["buckets"]["resolved"]
    )

    # Invariant 2: total == sum of pipeline stage counts
    assert res["total"] == (
        res["pipeline_stages"]["intake"]
        + res["pipeline_stages"]["planning"]
        + res["pipeline_stages"]["execution"]
        + res["pipeline_stages"]["resolution"]
    )

    # Invariant 3: sum of department totals == overall total
    dept_sum = sum(d["total"] for d in res["by_department"].values())
    assert res["total"] == dept_sum

    # Department scoped counts
    trd_res = compute_dashboard_counts(seeded_tasks, department="TRD")
    assert trd_res["total"] == 21
    assert trd_res["total"] == trd_res["pending"] + trd_res["active_scheduled"] + trd_res["resolved"]
    assert trd_res["total"] == (
        trd_res["pipeline_stages"]["intake"]
        + trd_res["pipeline_stages"]["planning"]
        + trd_res["pipeline_stages"]["execution"]
        + trd_res["pipeline_stages"]["resolution"]
    )


def test_trd_example_counts_add_up():
    """Reproduce the exact TRD example from user prompt: 26 PENDING, 1 SCHEDULED."""
    trd_tasks = []
    for i in range(26):
        trd_tasks.append(_create_task_with_status(TaskStatus.PENDING, dept=Department.TRD))
    trd_tasks.append(_create_task_with_status(TaskStatus.SCHEDULED, dept=Department.TRD))

    res = compute_dashboard_counts(trd_tasks, department="TRD")

    # Bento cards: Total 27, Pending 26, Active 1, Resolved 0
    assert res["total"] == 27
    assert res["pending"] == 26
    assert res["active_scheduled"] == 1
    assert res["resolved"] == 0

    # Pipeline columns: Intake 0, Planning 26, Execution 1, Resolution 0 -> sum = 27 (NOT 54!)
    assert res["pipeline_stages"]["intake"] == 0
    assert res["pipeline_stages"]["planning"] == 26
    assert res["pipeline_stages"]["execution"] == 1
    assert res["pipeline_stages"]["resolution"] == 0

    assert (
        res["pipeline_stages"]["intake"]
        + res["pipeline_stages"]["planning"]
        + res["pipeline_stages"]["execution"]
        + res["pipeline_stages"]["resolution"]
    ) == 27


@pytest.fixture
def test_app_client(tmp_path, monkeypatch):
    """Isolated environment with seeded tasks in app.state and a test admin token."""
    db_file = tmp_path / "counts_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=engine, expire_on_commit=False)())
    monkeypatch.setattr("backend.main.engine", engine)

    session = sessionmaker(bind=engine, expire_on_commit=False)()
    admin_user = UserRecord(
        id="usr_admin_counts",
        name="Admin Test",
        email="admin_counts@test.gov.in",
        password_hash=hash_password("adminpass"),
        role="ADMIN",
        department=None,
        is_active=True,
    )
    session.add(admin_user)
    session.commit()
    session.close()

    token = create_access_token(admin_user)

    # Seed app.state.tasks
    seeded_tasks = []
    for st in TaskStatus:
        seeded_tasks.append(_create_task_with_status(st, dept=Department.TRD))
        seeded_tasks.append(_create_task_with_status(st, dept=Department.ENGINEERING))

    app.state.tasks = seeded_tasks

    client = TestClient(app)
    return client, {"Authorization": f"Bearer {token}"}


def test_get_dashboard_counts_api_endpoint(test_app_client):
    """Test the GET /api/dashboard/counts endpoint with authentication and department filtering."""
    client, auth_headers = test_app_client

    resp = client.get("/api/dashboard/counts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "total" in data
    assert "pending" in data
    assert "active_scheduled" in data
    assert "resolved" in data
    assert "buckets" in data
    assert "pipeline_stages" in data

    # Verify invariants on API response
    assert data["total"] == data["pending"] + data["active_scheduled"] + data["resolved"]
    stages = data["pipeline_stages"]
    assert data["total"] == stages["intake"] + stages["planning"] + stages["execution"] + stages["resolution"]

    # Filter by department TRD
    trd_resp = client.get("/api/dashboard/counts?department=TRD", headers=auth_headers)
    assert trd_resp.status_code == 200
    trd_data = trd_resp.json()
    assert trd_data["total"] == 21
    assert trd_data["total"] == trd_data["pending"] + trd_data["active_scheduled"] + trd_data["resolved"]
    trd_stages = trd_data["pipeline_stages"]
    assert trd_data["total"] == (
        trd_stages["intake"] + trd_stages["planning"] + trd_stages["execution"] + trd_stages["resolution"]
    )
