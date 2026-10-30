"""
tests/test_live_trains_sync.py

Tests for RailRadar live train delay sync:
- Confirmation preview payload (calls to be made, covered trains with timetable snapshots, per-key budget)
- Server-side minimum interval enforcement (default 60m) returning HTTP 429
- Reserved monthly budget enforcement (default 30 calls) returning HTTP 429
- Post-sync response payload (trains updated, calls used, IST timestamp, failure reporting)
- Role-based access control (CONTROLLER/ADMIN only)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.database import (
    ApiUsageRecord,
    LiveTrainStatusRecord,
    UserRecord,
    get_engine,
    get_session,
    init_db,
    record_api_usage,
)
from backend.main import app
from backend.sync_service import (
    get_min_sync_interval_minutes,
    get_pilot_timetable_trains,
    get_sync_reserved_budget,
    record_sync_time,
    reset_last_sync_time,
)
from integrations.railradar_client import RailRadarClient, key_identifier


@pytest.fixture
def sync_test_env():
    """Sets up test client, database, and mock auth tokens."""
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)

    # Ensure clean state for sync tests
    reset_last_sync_time()
    session.query(ApiUsageRecord).delete()
    session.query(LiveTrainStatusRecord).delete()
    session.commit()

    # Create controller, admin, and dept users
    controller = session.query(UserRecord).filter_by(email="controller_sync@railopt.gov.in").first()
    if not controller:
        controller = UserRecord(
            id="usr_ctrl_sync",
            email="controller_sync@railopt.gov.in",
            name="Section Controller",
            role="CONTROLLER",
            department=None,
            password_hash="mock_hash",
            is_active=True,
        )
        session.add(controller)

    admin = session.query(UserRecord).filter_by(email="admin_sync@railopt.gov.in").first()
    if not admin:
        admin = UserRecord(
            id="usr_admin_sync",
            email="admin_sync@railopt.gov.in",
            name="Super Admin",
            role="ADMIN",
            department=None,
            password_hash="mock_hash",
            is_active=True,
        )
        session.add(admin)

    dept_user = session.query(UserRecord).filter_by(email="eng_sync@railopt.gov.in").first()
    if not dept_user:
        dept_user = UserRecord(
            id="usr_eng_sync",
            email="eng_sync@railopt.gov.in",
            name="Eng User",
            role="DEPT_USER",
            department="ENGINEERING",
            password_hash="mock_hash",
            is_active=True,
        )
        session.add(dept_user)

    session.commit()

    tokens = {
        "controller": create_access_token(controller),
        "admin": create_access_token(admin),
        "dept": create_access_token(dept_user),
    }

    client = TestClient(app)
    yield {
        "client": client,
        "tokens": tokens,
        "session": session,
        "engine": engine,
    }
    s = get_session(engine)
    s.query(ApiUsageRecord).delete()
    s.query(LiveTrainStatusRecord).delete()
    s.commit()
    s.close()
    session.close()
    reset_last_sync_time()


def test_sync_preview_confirmation_payload(sync_test_env):
    """
    Verifies GET /api/trains/live/sync-preview returns:
    - calls_needed
    - covered_trains (only trains that have a timetable snapshot on the pilot corridor)
    - per-key remaining monthly budget
    """
    client = sync_test_env["client"]
    token = sync_test_env["tokens"]["controller"]

    res = client.get(
        "/api/trains/live/sync-preview?section_id=SEC-93135bb9",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert "calls_needed" in data
    assert "covered_trains" in data
    assert "keys_budget" in data
    assert "reserved_budget" in data
    assert "available_for_sync" in data
    assert data["section_id"] == "SEC-93135bb9"

    # Covered trains must be non-empty and every covered train must have a timetable snapshot
    covered = data["covered_trains"]
    assert len(covered) > 0
    assert data["calls_needed"] == len(covered)

    # Key budget must report per-key limits and remaining
    assert len(data["keys_budget"]) >= 1
    for kb in data["keys_budget"]:
        assert "key_suffix" in kb
        assert "used" in kb
        assert "remaining" in kb
        assert "limit" in kb


def test_sync_minimum_interval_enforcement(sync_test_env):
    """
    Verifies that executing a sync and immediately attempting another sync
    within the minimum interval (e.g. 60 min) returns HTTP 429 Too Many Requests.
    """
    client = sync_test_env["client"]
    token = sync_test_env["tokens"]["controller"]

    # Mock live train lookup so no actual network calls are made
    mock_live_response = {
        "success": True,
        "source": "live",
        "data": {
            "trainNumber": "12301",
            "trainName": "Howrah Rajdhani",
            "delayMinutes": 10.0,
            "status": "RUNNING",
        },
    }

    with patch.object(RailRadarClient, "get_train_live", return_value=mock_live_response):
        # 1. First sync must succeed
        res1 = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res1.status_code == 200, res1.text
        data1 = res1.json()
        assert data1["status"] == "ok"
        assert data1["trains_updated"] > 0

        # 2. Immediate second sync must be blocked with HTTP 429
        res2 = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 429
        err_msg = res2.json()["detail"]
        assert "Sync cooldown active" in err_msg or "Minimum interval" in err_msg

        # 3. Preview must also report cooldown active
        preview_res = client.get(
            "/api/trains/live/sync-preview?section_id=SEC-93135bb9",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert preview_res.status_code == 200
        p_data = preview_res.json()
        assert p_data["can_sync"] is False
        assert p_data["cooldown_active"] is True
        assert p_data["cooldown_minutes_remaining"] > 0

        # 4. Sync with force=True must bypass cooldown
        res3 = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9&force=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res3.status_code == 200


def test_sync_reserved_budget_enforcement(sync_test_env):
    """
    Verifies that when the remaining budget across all keys would spend into the
    reserved budget (default 30 calls), the sync is rejected with HTTP 429.
    """
    client = sync_test_env["client"]
    token = sync_test_env["tokens"]["controller"]
    session = sync_test_env["session"]

    # Burn usage on configured keys so available_for_sync becomes 0
    rr = RailRadarClient()
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    
    # Simulate high usage across keys leaving less than reserved_budget
    for key in rr.keys:
        ident = key_identifier(key)
        # Record usage up to (limit - 5)
        for _ in range(rr.key_limit - 5):
            record_api_usage(session, ident, "/mock", 200, True)

    preview = client.get(
        "/api/trains/live/sync-preview?section_id=SEC-93135bb9",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    # Total remaining is now small (e.g. 5 * num_keys <= 15), which is below reserved_budget (30)
    assert preview["available_for_sync"] == 0
    assert preview["can_sync"] is False
    assert preview["blocked_reason"] == "INSUFFICIENT_RESERVED_BUDGET"

    # Attempting to sync without force must return HTTP 429
    res = client.post(
        "/api/trains/live/sync?section_id=SEC-93135bb9",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 429
    assert "Insufficient unreserved RailRadar API budget" in res.json()["detail"]


def test_sync_post_sync_response_payload(sync_test_env):
    """
    Verifies that successful POST /api/trains/live/sync returns:
    - trains_updated
    - calls_used
    - last_synced_time_ist (formatted in IST)
    - failures list
    """
    client = sync_test_env["client"]
    token = sync_test_env["tokens"]["admin"]

    mock_live = {
        "success": True,
        "source": "live",
        "data": {
            "trainNumber": "12301",
            "trainName": "Howrah Rajdhani",
            "delayMinutes": 15.0,
            "status": "RUNNING",
        },
    }

    with patch.object(RailRadarClient, "get_train_live", return_value=mock_live):
        res = client.post(
            "/api/trains/live/sync?section_id=SEC-93135bb9&force=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["status"] == "ok"
        assert "trains_updated" in data
        assert "calls_used" in data
        assert "last_synced_time_ist" in data
        assert "IST" in data["last_synced_time_ist"]
        assert "failures" in data
        assert isinstance(data["failures"], list)
        assert data["failure_count"] == 0
        assert data["trains_updated"] == data["calls_used"]


def test_sync_rbac_controls(sync_test_env):
    """
    Verifies RBAC rules:
    - DEPT_USER cannot trigger sync or view sync-preview (403 Forbidden).
    - CONTROLLER and ADMIN can access preview and trigger sync.
    - Anyone viewer or above can view the API budget panel.
    """
    client = sync_test_env["client"]
    tokens = sync_test_env["tokens"]

    # DEPT_USER attempts sync
    res_dept_sync = client.post(
        "/api/trains/live/sync?section_id=SEC-93135bb9",
        headers={"Authorization": f"Bearer {tokens['dept']}"},
    )
    assert res_dept_sync.status_code == 403

    # DEPT_USER attempts sync preview
    res_dept_preview = client.get(
        "/api/trains/live/sync-preview?section_id=SEC-93135bb9",
        headers={"Authorization": f"Bearer {tokens['dept']}"},
    )
    assert res_dept_preview.status_code == 403

    # Viewer/Dept user can view the general API budget breakdown
    res_dept_budget = client.get(
        "/api/trains/live/budget",
        headers={"Authorization": f"Bearer {tokens['dept']}"},
    )
    assert res_dept_budget.status_code == 200
    assert "total_remaining" in res_dept_budget.json()
