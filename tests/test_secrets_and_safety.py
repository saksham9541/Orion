import pytest
import jwt
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, UserRecord, save_user
from backend.auth import (
    get_jwt_secret,
    decode_token,
    authenticate_user,
    hash_password,
)
from backend.main import get_cors_origins


def test_production_refuses_to_start_without_secret(monkeypatch):
    """When ENVIRONMENT=production and JWT_SECRET is missing or < 32 chars, must raise RuntimeError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("RAILOPT_SECRET", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        get_jwt_secret()
    assert "JWT_SECRET" in str(exc_info.value)

    # Shorter than 32 chars
    monkeypatch.setenv("JWT_SECRET", "short_secret_key")
    with pytest.raises(RuntimeError) as exc_info:
        get_jwt_secret()
    assert "at least 32 characters" in str(exc_info.value)


def test_development_generates_random_secret(monkeypatch):
    """In development, missing secret generates a safe ephemeral 32+ char secret."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("RAILOPT_SECRET", raising=False)

    secret = get_jwt_secret()
    assert isinstance(secret, str)
    assert len(secret) >= 32


def test_token_signed_with_wrong_secret_is_rejected():
    """Token signed with an untrusted secret must be rejected with 401."""
    fake_token = jwt.encode(
        {"sub": "usr_123", "role": "ADMIN", "type": "access"},
        "wrong-untrusted-secret-key-32-chars-long",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(fake_token)
    assert exc_info.value.status_code == 401


def test_lockout_by_email_and_ip(tmp_path, monkeypatch):
    """
    Lockout must count by (email, ip).
    Failed attempts from IP A must NOT lock out the user at IP B.
    20 failed attempts from one IP must trigger IP-wide lockout.
    """
    db_file = tmp_path / "test_lockout.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: sessionmaker(bind=engine, expire_on_commit=False)())

    session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = UserRecord(
        id="usr_lockout",
        name="Target User",
        email="target@test.gov.in",
        password_hash=hash_password("correctpass123"),
        role="CONTROLLER",
        department=None,
        is_active=True,
    )
    save_user(session, user)
    session.close()

    # 1. IP A makes 5 wrong attempts on target@test.gov.in
    ip_a = "192.168.1.100"
    for _ in range(5):
        u, err = authenticate_user("target@test.gov.in", "wrongpass", client_ip=ip_a)
        assert u is None

    # 6th attempt from IP A is locked
    u, err = authenticate_user("target@test.gov.in", "correctpass123", client_ip=ip_a)
    assert u is None
    assert "locked" in err.lower()

    # 2. Legitimate user at IP B attempts to login with correct password -> SUCCEEDS!
    ip_b = "10.0.0.50"
    u, err = authenticate_user("target@test.gov.in", "correctpass123", client_ip=ip_b)
    assert u is not None, f"Expected successful login from IP B, but got error: {err}"
    assert err is None

    # 3. IP C sprays 20 different emails -> IP C gets locked out
    ip_c = "203.0.113.1"
    for i in range(20):
        authenticate_user(f"random{i}@test.gov.in", "guess", client_ip=ip_c)

    u, err = authenticate_user("target@test.gov.in", "correctpass123", client_ip=ip_c)
    assert u is None
    assert "too many failed login attempts from this ip" in err.lower()


def test_cors_reads_env_variable(monkeypatch):
    """CORS origins must be read from CORS_ORIGINS environment variable."""
    monkeypatch.setenv("CORS_ORIGINS", "https://orion.railways.gov.in, https://app.railways.gov.in")
    origins = get_cors_origins()
    assert origins == ["https://orion.railways.gov.in", "https://app.railways.gov.in"]
