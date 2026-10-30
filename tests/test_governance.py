"""
tests/test_governance.py

Tests for Department Accept/Reject Governance, Safety-Critical Guard,
Plan State Machine Transitions (PROPOSED -> DEPT_REVIEW -> CONFLICT -> READY_FOR_CONTROLLER),
and CP-SAT Re-solve with Forbidden Constraints.
"""
from __future__ import annotations

from datetime import date, time
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app, engine
from backend.auth import create_access_token, User, hash_password
from backend.database import get_session, UserRecord, save_user, save_plan, load_plan
from railopt.models import (
    AssetType,
    BlockDecision,
    BlockPlan,
    BlockRejectReason,
    BlockResponse,
    Department,
    MaintenanceTask,
    PlanHorizon,
    PlanStatus,
    ScheduledBlock,
    UserRole,
    DefectCategory,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def users():
    u_eng = User(id="usr_eng_1", email="eng@railopt.gov.in", name="Engineering Lead", role=UserRole.DEPT_USER, department=Department.ENGINEERING)
    u_snt = User(id="usr_snt_1", email="snt@railopt.gov.in", name="S&T Lead", role=UserRole.DEPT_USER, department=Department.SNT)
    u_ctrl = User(id="usr_ctrl_1", email="ctrl@railopt.gov.in", name="Chief Controller", role=UserRole.CONTROLLER)

    session = get_session(engine)
    try:
        save_user(session, UserRecord(id=u_eng.id, name=u_eng.name, email=u_eng.email, password_hash=hash_password("pass"), role=u_eng.role.value, department=u_eng.department.value, is_active=True))
        save_user(session, UserRecord(id=u_snt.id, name=u_snt.name, email=u_snt.email, password_hash=hash_password("pass"), role=u_snt.role.value, department=u_snt.department.value, is_active=True))
        save_user(session, UserRecord(id=u_ctrl.id, name=u_ctrl.name, email=u_ctrl.email, password_hash=hash_password("pass"), role=u_ctrl.role.value, department=None, is_active=True))
    finally:
        session.close()

    tok_eng = create_access_token(u_eng)
    tok_snt = create_access_token(u_snt)
    tok_ctrl = create_access_token(u_ctrl)

    return {
        "eng": (u_eng, tok_eng),
        "snt": (u_snt, tok_snt),
        "ctrl": (u_ctrl, tok_ctrl),
    }


@pytest.fixture
def sample_plan():
    if not hasattr(app.state, "plans"):
        app.state.plans = {}
    if not hasattr(app.state, "tasks"):
        app.state.tasks = []
    if not hasattr(app.state, "sections"):
        app.state.sections = {}
    if not hasattr(app.state, "windows"):
        app.state.windows = []

    # Setup tasks in app.state.tasks
    t_eng = MaintenanceTask(
        task_id="MT-ENG-101",
        department=Department.ENGINEERING,
        asset_type=AssetType.RAIL,
        defect_category=DefectCategory.RAIL_FRACTURE,
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        km_location=5.0,
        reported_date=date(2026, 11, 1),
        is_safety_critical=True,
    )
    t_snt = MaintenanceTask(
        task_id="MT-SNT-202",
        department=Department.SNT,
        asset_type=AssetType.SIGNAL_POST,
        defect_category=DefectCategory.SIGNAL_FAILURE,
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        km_location=5.2,
        reported_date=date(2026, 11, 1),
        is_safety_critical=False,
    )
    app.state.tasks = [t_eng, t_snt]

    b1 = ScheduledBlock(
        block_id="BLK-TEST-001",
        window_id="WIN-TEST-01",
        corridor_id="COR-82d9c510",
        section_id="SEC-93135bb9",
        section_name="New Delhi–Ghaziabad",
        date=date(2026, 11, 1),
        start_time=time(1, 30),
        end_time=time(4, 30),
        duration_hours=3.0,
        task_ids=["MT-ENG-101", "MT-SNT-202"],
        departments=[Department.ENGINEERING, Department.SNT],
        is_merged=True,
    )

    plan = BlockPlan(
        plan_id=f"PLN-GOV-{uuid.uuid4().hex[:8]}",
        horizon=PlanHorizon.WEEKLY,
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 8),
        scheduled_blocks=[b1],
        status=PlanStatus.PROPOSED,
    )

    app.state.plans[plan.plan_id] = plan
    session = get_session(engine)
    try:
        save_plan(session, plan)
    finally:
        session.close()

    return plan


def test_get_my_blocks_scoping(client, users, sample_plan):
    _, tok_eng = users["eng"]
    _, tok_snt = users["snt"]

    # Engineering user gets their blocks
    res_eng = client.get(
        f"/api/plans/{sample_plan.plan_id}/my-blocks",
        headers={"Authorization": f"Bearer {tok_eng}"},
    )
    assert res_eng.status_code == 200
    data_eng = res_eng.json()
    assert len(data_eng["blocks"]) == 1
    assert data_eng["blocks"][0]["block_id"] == "BLK-TEST-001"
    assert len(data_eng["blocks"][0]["my_tasks"]) == 1
    assert data_eng["blocks"][0]["my_tasks"][0]["task_id"] == "MT-ENG-101"
    # Shared task from SNT is visible for coordination
    assert len(data_eng["blocks"][0]["shared_tasks"]) == 1
    assert data_eng["blocks"][0]["shared_tasks"][0]["department"] == "SNT"


def test_safety_critical_reject_guard(client, users, sample_plan):
    _, tok_eng = users["eng"]
    _, tok_ctrl = users["ctrl"]

    # 1. DEPT_USER attempts to reject safety-critical block -> Must be rejected with 400
    res_reject = client.post(
        f"/api/plans/{sample_plan.plan_id}/blocks/BLK-TEST-001/respond",
        headers={"Authorization": f"Bearer {tok_eng}"},
        json={
            "decision": "REJECT",
            "reason_code": "RESOURCE_UNAVAILABLE",
            "reason": "Gang unavailable on Sunday morning",
            "controller_override": False,
        },
    )
    assert res_reject.status_code == 400
    assert "safety-critical" in res_reject.json()["detail"].lower()

    # 2. Rejection requires standardized reason_code
    res_no_code = client.post(
        f"/api/plans/{sample_plan.plan_id}/blocks/BLK-TEST-001/respond",
        headers={"Authorization": f"Bearer {tok_ctrl}"},
        json={
            "decision": "REJECT",
            "reason": "Emergency track holding",
            "controller_override": True,
        },
    )
    assert res_no_code.status_code == 400

    # 3. CONTROLLER with override can authorize rejection
    res_override = client.post(
        f"/api/plans/{sample_plan.plan_id}/blocks/BLK-TEST-001/respond",
        headers={"Authorization": f"Bearer {tok_ctrl}"},
        json={
            "decision": "REJECT",
            "reason_code": "OPERATIONAL_PRIORITY",
            "reason": "VIP Rajdhani corridor movement requires window deferral",
            "controller_override": True,
            "department": "ENGINEERING",
        },
    )
    assert res_override.status_code == 200
    assert res_override.json()["plan_status"] == "CONFLICT"


def test_plan_state_machine_accept_all(client, users, sample_plan):
    _, tok_eng = users["eng"]
    _, tok_snt = users["snt"]

    # 1. Engineering accepts
    res_eng = client.post(
        f"/api/plans/{sample_plan.plan_id}/blocks/BLK-TEST-001/respond",
        headers={"Authorization": f"Bearer {tok_eng}"},
        json={"decision": "ACCEPT"},
    )
    assert res_eng.status_code == 200
    # One department accepted, but SNT still pending -> DEPT_REVIEW
    assert res_eng.json()["plan_status"] == "DEPT_REVIEW"

    # 2. S&T accepts
    res_snt = client.post(
        f"/api/plans/{sample_plan.plan_id}/blocks/BLK-TEST-001/respond",
        headers={"Authorization": f"Bearer {tok_snt}"},
        json={"decision": "ACCEPT"},
    )
    assert res_snt.status_code == 200
    # All participating departments accepted -> READY_FOR_CONTROLLER
    assert res_snt.json()["plan_status"] == "READY_FOR_CONTROLLER"


def test_re_solve_with_forbidden_constraints(client, users, sample_plan):
    _, tok_ctrl = users["ctrl"]

    # Reject a block with controller override to trigger CONFLICT
    client.post(
        f"/api/plans/{sample_plan.plan_id}/blocks/BLK-TEST-001/respond",
        headers={"Authorization": f"Bearer {tok_ctrl}"},
        json={
            "decision": "REJECT",
            "reason_code": "RESOURCE_UNAVAILABLE",
            "reason": "Gang unavailable",
            "controller_override": True,
            "department": "ENGINEERING",
        },
    )

    # Trigger re-solve
    res_resolve = client.post(
        f"/api/plans/{sample_plan.plan_id}/re-solve",
        headers={"Authorization": f"Bearer {tok_ctrl}"},
    )
    assert res_resolve.status_code == 200
    data = res_resolve.json()
    assert data["status"] in ("resolved", "conflict_unresolved")
