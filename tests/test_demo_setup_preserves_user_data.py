import hashlib
import pytest
from datetime import date
from fastapi.testclient import TestClient

from backend.main import app, engine
from backend.database import get_session, TaskRecord, save_tasks, UserRecord, save_user, init_db
from backend.auth import create_access_token, hash_password
from railopt.models import MaintenanceTask, DefectCategory, Department, AssetType, UserRole
from railopt.synthetic_data import generate_full_dataset


def test_corridor_and_section_ids_are_deterministic():
    """Corridor and section IDs must be deterministically generated from their names."""
    ds1 = generate_full_dataset(seed=42, num_tasks=50)
    ds2 = generate_full_dataset(seed=999, num_tasks=50)

    # Even with different seeds, topology IDs must be deterministic based on name
    corridor_ids_1 = [c.corridor_id for c in ds1["corridors"]]
    corridor_ids_2 = [c.corridor_id for c in ds2["corridors"]]
    assert corridor_ids_1 == corridor_ids_2

    section_ids_1 = [s.section_id for s in ds1["sections"]]
    section_ids_2 = [s.section_id for s in ds2["sections"]]
    assert section_ids_1 == section_ids_2

    # Check hash structure
    for c in ds1["corridors"]:
        expected_hash = hashlib.md5(c.name.encode()).hexdigest()[:8]
        assert expected_hash in c.corridor_id


def test_demo_setup_preserves_user_data(client=None):
    """
    Demo setup must only delete synthetic data.
    User tasks in memory and DB must be completely preserved.
    """
    init_db(engine)
    client = TestClient(app)

    session = get_session(engine)
    admin_user = UserRecord(
        id="usr_admin",
        name="Admin User",
        email="admin@railways.gov.in",
        password_hash=hash_password("adminpass123"),
        role=UserRole.ADMIN.value,
        department=None,
        is_active=True,
    )
    save_user(session, admin_user)
    session.close()

    admin_token = create_access_token({
        "id": "usr_admin",
        "email": "admin@railways.gov.in",
        "role": UserRole.ADMIN.value,
        "department": None,
    })
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a user task and save it
    user_task = MaintenanceTask(
        task_id="TSK-USER-999",
        source="user",
        department=Department.ENGINEERING,
        asset_type=AssetType.RAIL,
        asset_id="TRK-USR-1",
        defect_category=DefectCategory.RAIL_FRACTURE,
        corridor_id="COR-test",
        section_id="SEC-test",
        km_location=105.5,
        km_start=105.0,
        km_end=106.0,
        reported_date=date.today(),
        is_safety_critical=True,
        requires_traffic_block=True,
    )

    session = get_session(engine)
    save_tasks(session, [user_task])
    session.close()

    app.state.tasks = [user_task]

    # 2. Run /api/demo/setup
    resp = client.post("/api/demo/setup", headers=headers)
    assert resp.status_code == 200

    # 3. Verify user task is still present in app.state.tasks
    task_ids = [t.task_id for t in app.state.tasks]
    assert "TSK-USER-999" in task_ids

    preserved_task = next(t for t in app.state.tasks if t.task_id == "TSK-USER-999")
    assert preserved_task.source == "user"

    # 4. Verify user task is still present in database
    session = get_session(engine)
    db_user_task = session.query(TaskRecord).filter(TaskRecord.task_id == "TSK-USER-999").first()
    assert db_user_task is not None
    assert db_user_task.source == "user"
    session.close()
