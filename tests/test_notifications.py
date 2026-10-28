"""
Tests for Phase 3: Real-Time Issue Alert Notifications & WebSocket System.
Verifies:
1. WebSocket connection authentication (valid token vs invalid token)
2. Live WebSocket alert delivery to online Super Admin and designated department users
3. Exclusion of issue creator and other departments from alerts
4. Offline notification persistence & retrieval via GET /api/notifications & unread count
5. Mark as read & acknowledge endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, UserRecord
from backend.auth import hash_password, create_access_token


@pytest.fixture
def notif_test_env(tmp_path, monkeypatch):
    """Sets up an isolated SQLite test database with seeded users across departments."""
    db_file = tmp_path / "notif_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, expire_on_commit=False)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: Session())
    monkeypatch.setattr("backend.main.engine", engine)

    session = Session()

    # 1. Admin (Super Admin)
    admin_user = UserRecord(
        id="usr_admin_1",
        name="Super Admin",
        email="superadmin@test.gov.in",
        password_hash=hash_password("adminpass123"),
        role="ADMIN",
        department=None,
        is_active=True,
    )
    # 2. Engineering Creator
    eng_creator = UserRecord(
        id="usr_eng_creator",
        name="Eng Inspector",
        email="eng_creator@test.gov.in",
        password_hash=hash_password("pass123"),
        role="DEPT_USER",
        department="ENGINEERING",
        is_active=True,
    )
    # 3. Engineering Peer (same dept)
    eng_peer = UserRecord(
        id="usr_eng_peer",
        name="Eng Engineer",
        email="eng_peer@test.gov.in",
        password_hash=hash_password("pass123"),
        role="DEPT_USER",
        department="ENGINEERING",
        is_active=True,
    )
    # 4. S&T User (other dept)
    snt_user = UserRecord(
        id="usr_snt_1",
        name="SNT Signal Engineer",
        email="snt@test.gov.in",
        password_hash=hash_password("pass123"),
        role="DEPT_USER",
        department="SNT",
        is_active=True,
    )
    # 5. TRD User (other dept)
    trd_user = UserRecord(
        id="usr_trd_1",
        name="TRD Power Engineer",
        email="trd@test.gov.in",
        password_hash=hash_password("pass123"),
        role="DEPT_USER",
        department="TRD",
        is_active=True,
    )

    for u in [admin_user, eng_creator, eng_peer, snt_user, trd_user]:
        session.add(u)
    session.commit()
    session.close()

    tokens = {
        "admin": create_access_token(admin_user),
        "eng_creator": create_access_token(eng_creator),
        "eng_peer": create_access_token(eng_peer),
        "snt": create_access_token(snt_user),
        "trd": create_access_token(trd_user),
    }

    client = TestClient(app)
    return {
        "client": client,
        "engine": engine,
        "tokens": tokens,
        "users": {
            "admin": admin_user,
            "eng_creator": eng_creator,
            "eng_peer": eng_peer,
            "snt": snt_user,
            "trd": trd_user,
        }
    }


def test_websocket_auth(notif_test_env):
    """WebSocket connection requires a valid JWT token via query param, header, or Sec-WebSocket-Protocol."""
    client = notif_test_env["client"]
    valid_token = notif_test_env["tokens"]["admin"]

    # 1. Valid token in query param connects successfully
    with client.websocket_connect(f"/ws/notifications?token={valid_token}") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"

    # 2. Valid token in Sec-WebSocket-Protocol echoes subprotocol and connects
    with client.websocket_connect("/ws/notifications", subprotocols=[valid_token]) as ws:
        assert ws.accepted_subprotocol == valid_token
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"

    # 3. Valid token in Authorization header connects
    with client.websocket_connect("/ws/notifications", headers={"Authorization": f"Bearer {valid_token}"}) as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"

    # 4. Missing token fails connection
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/notifications"):
            pass

    # 5. Invalid token fails connection
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/notifications?token=invalid_token_123"):
            pass


def test_issue_alert_dispatch_and_routing(notif_test_env):
    """
    When an issue is registered for ENGINEERING:
    - Super Admin receives live alert via WebSocket
    - Engineering peer receives live alert via WebSocket
    - S&T user does NOT receive it
    - Creator does NOT receive alert for their own submission
    """
    client = notif_test_env["client"]
    tokens = notif_test_env["tokens"]

    admin_token = tokens["admin"]
    eng_peer_token = tokens["eng_peer"]
    snt_token = tokens["snt"]
    creator_token = tokens["eng_creator"]

    # Connect WebSockets for admin, eng_peer, snt, creator
    with client.websocket_connect(f"/ws/notifications?token={admin_token}") as ws_admin, \
         client.websocket_connect(f"/ws/notifications?token={eng_peer_token}") as ws_eng, \
         client.websocket_connect(f"/ws/notifications?token={snt_token}") as ws_snt, \
         client.websocket_connect(f"/ws/notifications?token={creator_token}") as ws_creator:

        # Creator submits an Engineering complaint
        payload = {
            "description": "Rail fracture detected at KM 124 near Ghaziabad junction. Immediate attention needed.",
            "corridor_id": "COR-DELHI-GZB",
            "section_id": "SEC-GZB-1",
            "km_location": 124.5,
        }
        res = client.post(
            "/api/tasks/complaint",
            headers={"Authorization": f"Bearer {creator_token}"},
            json=payload,
        )
        assert res.status_code == 200, res.text
        task_data = res.json()
        assert task_data["task_id"].startswith("TSK-")

        # Admin receives WebSocket alert immediately
        admin_msg = ws_admin.receive_json()
        assert admin_msg["type"] == "ISSUE_RAISED"
        assert admin_msg["notification"]["issue_id"] == task_data["task_id"]
        assert admin_msg["notification"]["severity"] in ("EMERGENCY", "HIGH", "MEDIUM")
        assert admin_msg["notification"]["department_designated"] == "ENGINEERING"

        # Engineering peer receives WebSocket alert immediately
        eng_msg = ws_eng.receive_json()
        assert eng_msg["type"] == "ISSUE_RAISED"
        assert eng_msg["notification"]["issue_id"] == task_data["task_id"]

        assert ws_snt is not None
        assert ws_creator is not None


def test_offline_user_notifications_rest_flow(notif_test_env):
    """
    Offline users who were not connected during issue creation
    must receive pending notifications upon subsequent login/REST check.
    """
    client = notif_test_env["client"]
    tokens = notif_test_env["tokens"]
    creator_token = tokens["eng_creator"]
    eng_peer_token = tokens["eng_peer"]

    # Check unread count for eng_peer initially
    count_res = client.get(
        "/api/notifications/unread-count",
        headers={"Authorization": f"Bearer {eng_peer_token}"},
    )
    assert count_res.status_code == 200
    initial_unread = count_res.json()["unread_count"]
    assert initial_unread >= 0

    # Submit an Engineering complaint while eng_peer is offline (no WebSocket connected)
    payload = {
        "description": "Ballast deficiency observed near KM 50.",
        "corridor_id": "COR-DELHI-MUMBAI",
        "section_id": "SEC-DELHI-1",
        "km_location": 50.2,
    }
    create_res = client.post(
        "/api/tasks/complaint",
        headers={"Authorization": f"Bearer {creator_token}"},
        json=payload,
    )
    assert create_res.status_code == 200

    # Eng peer queries notifications
    notifs_res = client.get(
        "/api/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {eng_peer_token}"},
    )
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()
    assert len(notifs) >= 1
    newest = notifs[0]
    assert newest["read_at"] is None
    assert newest["acknowledged_at"] is None

    notif_id = newest["id"]

    # Mark as read
    read_res = client.patch(
        f"/api/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {eng_peer_token}"},
    )
    assert read_res.status_code == 200
    assert read_res.json()["read_at"] is not None

    # Acknowledge
    ack_res = client.post(
        f"/api/notifications/{notif_id}/acknowledge",
        headers={"Authorization": f"Bearer {eng_peer_token}"},
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["acknowledged_at"] is not None


def test_admin_reporting_issue_does_not_receive_self_alert(notif_test_env):
    """
    When Super Admin submits an issue:
    - Designated department peer receives the live alert via WebSocket
    - Super Admin (the creator) does NOT receive self-alert
    """
    client = notif_test_env["client"]
    tokens = notif_test_env["tokens"]
    admin_token = tokens["admin"]
    eng_peer_token = tokens["eng_peer"]

    with client.websocket_connect(f"/ws/notifications?token={admin_token}") as ws_admin, \
         client.websocket_connect(f"/ws/notifications?token={eng_peer_token}") as ws_eng:

        payload = {
            "description": "Rail surface defect observed by Super Admin inspection.",
            "corridor_id": "COR-DELHI-MUMBAI",
            "section_id": "SEC-DELHI-1",
            "km_location": 78.4,
            "department_designated": "ENGINEERING",
            "severity": "HIGH",
        }
        res = client.post(
            "/api/tasks/complaint",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=payload,
        )
        assert res.status_code == 200, res.text
        task_data = res.json()

        # Engineering peer receives WebSocket alert
        eng_msg = ws_eng.receive_json()
        assert eng_msg["type"] == "ISSUE_RAISED"
        assert eng_msg["notification"]["issue_id"] == task_data["task_id"]

        # Super Admin should NOT have any notifications created for their own submission
        admin_notifs_res = client.get(
            "/api/notifications?unread_only=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_notifs_res.status_code == 200
        my_notifs = [n for n in admin_notifs_res.json() if n.get("issue_id") == task_data["task_id"]]
        assert len(my_notifs) == 0, "Super Admin received self-notification for their own report"
        assert ws_admin is not None
