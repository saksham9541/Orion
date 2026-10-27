"""
Unit tests for Step 1 & Step 2:
- PostgreSQL engine normalization and Neon sleeping pre-ping configuration
- User model, source columns, and migration schema
- Password hashing (bcrypt)
- JWT access tokens (short-lived) & refresh tokens
- Login rate limiting (5 wrong attempts -> 15 min block)
- Role verification (ADMIN, CONTROLLER, DEPT_USER, VIEWER)
"""
import datetime
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    authenticate_user,
)
from backend.database import (
    Base,
    init_db,
    get_session,
    save_user,
    get_user_by_email,
    get_failed_login_count,
    record_login_attempt,
    clear_failed_login_attempts,
    get_database_url,
    get_engine,
    UserRecord,
    TaskRecord,
    BlockPlanRecord,
)
from railopt.models import UserRole, Department


@pytest.fixture
def auth_db(tmp_path):
    """Isolated SQLite test DB with full schema."""
    db_file = tmp_path / "test_auth.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


def test_password_hashing():
    pwd = "SuperSecretPassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_tokens():
    user_data = {
        "id": "usr_test123",
        "email": "controller@railopt.gov.in",
        "name": "Head Controller",
        "role": UserRole.CONTROLLER.value,
        "department": None,
    }
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)

    access_payload = decode_token(access_token)
    assert access_payload["sub"] == "usr_test123"
    assert access_payload["role"] == "CONTROLLER"
    assert access_payload["type"] == "access"

    refresh_payload = decode_token(refresh_token)
    assert refresh_payload["sub"] == "usr_test123"
    assert refresh_payload["type"] == "refresh"


def test_source_column_defaults(auth_db):
    """Test that tasks and plans default to source='synthetic'."""
    SessionLocal = sessionmaker(bind=auth_db)
    session = SessionLocal()

    task = TaskRecord(
        task_id="MT-test001",
        reported_date=datetime.date.today(),
        days_overdue=0,
        is_safety_critical=False,
        requires_power_block=False,
        requires_traffic_block=True,
        crew_size_required=2,
        asset_age_years=1.0,
        historical_failure_count=0,
        ml_criticality_score=10.0,
        ml_predicted_duration_hours=2.0,
        ml_duration_confidence_lower=1.0,
        ml_duration_confidence_upper=3.0,
        estimated_duration_hours=2.0,
        deferred_count=0,
    )
    session.add(task)
    session.commit()

    loaded = session.query(TaskRecord).filter(TaskRecord.task_id == "MT-test001").first()
    assert loaded.source == "synthetic"
    session.close()


def test_login_rate_limiting(auth_db, monkeypatch):
    """Test that 5 failed login attempts trigger a 15-minute lockout."""
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=auth_db, expire_on_commit=False)())

    SessionLocal = sessionmaker(bind=auth_db, expire_on_commit=False)
    session = SessionLocal()

    # Create active user
    user = UserRecord(
        id="usr_rate_test",
        name="Dept Engineer",
        email="eng.test@railopt.gov.in",
        password_hash=hash_password("CorrectPassword2026"),
        role=UserRole.DEPT_USER.value,
        department=Department.ENGINEERING.value,
        is_active=True,
    )
    save_user(session, user)
    session.close()

    # Attempt 4 wrong passwords — should fail with invalid credentials
    for i in range(4):
        u, err = authenticate_user("eng.test@railopt.gov.in", f"wrong_pass_{i}")
        assert u is None
        assert err == "Invalid email or password"

    # 5th wrong attempt — should also fail
    u, err = authenticate_user("eng.test@railopt.gov.in", "wrong_pass_5")
    assert u is None

    # 6th attempt even with CORRECT password should be locked out!
    u, err = authenticate_user("eng.test@railopt.gov.in", "CorrectPassword2026")
    assert u is None
    assert "temporarily locked" in err.lower()


def test_successful_login_clears_failures(auth_db, monkeypatch):
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=auth_db, expire_on_commit=False)())

    SessionLocal = sessionmaker(bind=auth_db, expire_on_commit=False)
    session = SessionLocal()

    user = UserRecord(
        id="usr_success_test",
        name="Viewer User",
        email="viewer@railopt.gov.in",
        password_hash=hash_password("ValidPassword123"),
        role=UserRole.VIEWER.value,
        is_active=True,
    )
    save_user(session, user)
    session.close()

    # 2 failed attempts
    authenticate_user("viewer@railopt.gov.in", "badpass1")
    authenticate_user("viewer@railopt.gov.in", "badpass2")

    # 1 correct attempt
    u, err = authenticate_user("viewer@railopt.gov.in", "ValidPassword123")
    assert err is None
    assert u is not None
    assert u.email == "viewer@railopt.gov.in"

    # Verify failed count was reset
    session = SessionLocal()
    assert get_failed_login_count(session, "viewer@railopt.gov.in") == 0
    session.close()


def test_database_url_normalization(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@ep-cool-host.neon.tech/neondb")
    url = get_database_url()
    assert url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in url


def test_auth_api_flow(auth_db, monkeypatch):
    """Test full login, me, and admin user creation flow via FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setattr("backend.database.get_engine", lambda: auth_db)
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=auth_db, expire_on_commit=False)())
    monkeypatch.setattr("backend.main.engine", auth_db)

    SessionLocal = sessionmaker(bind=auth_db, expire_on_commit=False)
    session = SessionLocal()

    # Seed Admin user
    admin = UserRecord(
        id="usr_admin001",
        name="Main Admin",
        email="admin@railopt.gov.in",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    save_user(session, admin)
    session.close()

    client = TestClient(app)

    # 1. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@railopt.gov.in", "password": "AdminPass123!"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["role"] == "ADMIN"
    token = data["access_token"]
    refresh = data["refresh_token"]

    # 2. Get /api/auth/me
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@railopt.gov.in"

    # 3. Refresh token
    refresh_resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

    # 4. Admin creates DEPT_USER without department -> rejected (400)
    bad_user_resp = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Track Inspector",
            "email": "track@railopt.gov.in",
            "password": "Password123!",
            "role": "DEPT_USER",
        },
    )
    assert bad_user_resp.status_code == 400
    assert "department" in bad_user_resp.json()["detail"].lower()

    # 5. Admin creates DEPT_USER with department ENGINEERING -> succeeds (200)
    good_user_resp = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Track Inspector",
            "email": "track@railopt.gov.in",
            "password": "Password123!",
            "role": "DEPT_USER",
            "department": "ENGINEERING",
        },
    )
    assert good_user_resp.status_code == 200
    created = good_user_resp.json()
    assert created["email"] == "track@railopt.gov.in"
    assert created["department"] == "ENGINEERING"
    assert created["role"] == "DEPT_USER"

