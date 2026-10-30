import pytest
from fastapi.testclient import TestClient
from backend.main import app, engine, on_startup
from backend.database import get_session, UserRecord, save_user
from backend.auth import create_access_token, User, UserRole, hash_password


@pytest.fixture
def auth_client():
    if not hasattr(app.state, "tasks") or not app.state.tasks:
        on_startup()

    u_ctrl = User(
        id="usr_ctrl_smoke",
        email="ctrl_smoke@railopt.gov.in",
        name="Chief Controller Smoke",
        role=UserRole.CONTROLLER,
    )
    session = get_session(engine)
    try:
        save_user(
            session,
            UserRecord(
                id=u_ctrl.id,
                name=u_ctrl.name,
                email=u_ctrl.email,
                password_hash=hash_password("smoke123"),
                role=u_ctrl.role.value,
                department=None,
                is_active=True,
            ),
        )
    finally:
        session.close()

    tok_ctrl = create_access_token(u_ctrl)
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {tok_ctrl}"
    return client


def test_dashboard_api_smoke(auth_client):
    """Smoke test for endpoints consumed by Dashboard.jsx."""
    res_stats = auth_client.get("/api/dashboard/stats")
    assert res_stats.status_code == 200
    data = res_stats.json()
    assert "total_tasks" in data
    assert "total_plans" in data
    assert "tasks_by_department" in data

    res_plans = auth_client.get("/api/plans")
    assert res_plans.status_code == 200
    assert isinstance(res_plans.json(), list)


def test_tasks_api_smoke(auth_client):
    """Smoke test for endpoints consumed by Tasks.jsx."""
    res_tasks = auth_client.get("/api/tasks")
    assert res_tasks.status_code == 200
    assert isinstance(res_tasks.json(), list)

    res_corridors = auth_client.get("/api/corridors")
    assert res_corridors.status_code == 200
    corridors = res_corridors.json()
    assert isinstance(corridors, list)
    assert len(corridors) > 0


def test_block_plan_api_smoke(auth_client):
    """Smoke test for endpoints consumed by BlockPlan.jsx."""
    res_plans = auth_client.get("/api/plans")
    assert res_plans.status_code == 200
    assert isinstance(res_plans.json(), list)


def test_simulator_api_smoke(auth_client):
    """Smoke test for simulator and plans consumed by Simulator.jsx."""
    res_plans = auth_client.get("/api/plans")
    assert res_plans.status_code == 200

    plans = res_plans.json()
    if plans:
        plan_id = plans[0]["plan_id"]
        res_sim = auth_client.post(f"/api/plans/{plan_id}/simulate")
        assert res_sim.status_code == 200
        assert "report" in res_sim.json()


def test_network_api_smoke(auth_client):
    """Smoke test for endpoints consumed by Network.jsx."""
    res_corridors = auth_client.get("/api/corridors")
    assert res_corridors.status_code == 200

    res_plans = auth_client.get("/api/plans")
    assert res_plans.status_code == 200
    plans = res_plans.json()
    if plans:
        plan_id = plans[0]["plan_id"]
        res_map = auth_client.get(f"/api/map/blocks?plan_id={plan_id}")
        assert res_map.status_code == 200
        assert "blocks" in res_map.json()


def test_sources_api_smoke(auth_client):
    """Smoke test for endpoints consumed by Sources.jsx."""
    res_corridors = auth_client.get("/api/corridors")
    assert res_corridors.status_code == 200

    res_snapshots = auth_client.get("/api/sources/snapshots")
    assert res_snapshots.status_code == 200
    data = res_snapshots.json()
    assert "overall_provenance" in data
    assert "ui_label" in data
    assert "hand_written_details" in data
    assert data["overall_provenance"] == "hand_written"
    assert data["ui_label"] == "illustrative, not fetched"


def test_navigation_and_tab_reachability():
    """Verify role-based nav tab visibility and reachability across routes via node."""
    import subprocess
    res = subprocess.run(["node", "frontend/test_nav.js"], capture_output=True, text=True)
    assert res.returncode == 0, f"Navigation test failed: {res.stderr}\n{res.stdout}"
    assert "All navigation and reachability tests passed successfully!" in res.stdout

