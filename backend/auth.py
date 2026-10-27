"""
Orion — Authentication & Role-Based Access Control (RBAC).
Provides:
- Secure password hashing using bcrypt
- Short-lived JWT access tokens (20m) & refresh tokens (7d)
- Database-backed user management and verification
- Login rate-limiting (locks after 5 failed attempts within 15 minutes)
- FastAPI dependencies for token verification and role checking
"""
from __future__ import annotations

import datetime
from datetime import timedelta, timezone
import logging
import os
import uuid
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.database import (
    UserRecord,
    clear_failed_login_attempts,
    get_failed_login_count,
    get_session,
    get_user_by_email,
    get_user_by_id,
    record_login_attempt,
    save_user,
    update_last_login,
)
from backend.schemas import User
from railopt.models import Department, UserRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("RAILOPT_SECRET")
if not JWT_SECRET:
    # Use a fallback for local testing if neither variable is set, but warn
    JWT_SECRET = "orion-default-insecure-dev-secret-key-32chars"
    logger.warning("Neither JWT_SECRET nor RAILOPT_SECRET is set. Using default secret key.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 20
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token Generation & Verification
# ---------------------------------------------------------------------------
def _extract_field(user: UserRecord | dict, field_name: str, default=None):
    if isinstance(user, dict):
        return user.get(field_name, default)
    return getattr(user, field_name, default)


def create_access_token(user: UserRecord | dict) -> str:
    """Create a signed short-lived access token (20 minutes)."""
    now = datetime.datetime.now(timezone.utc)
    user_id = _extract_field(user, "id", "")
    email = _extract_field(user, "email", "")
    role = _extract_field(user, "role", "")
    dept = _extract_field(user, "department", None)
    name = _extract_field(user, "name", "")

    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "role": str(role),
        "department": str(dept) if dept else None,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(user: UserRecord | dict) -> str:
    """Create a signed refresh token (7 days)."""
    now = datetime.datetime.now(timezone.utc)
    user_id = _extract_field(user, "id", "")
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT."""
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )


# ---------------------------------------------------------------------------
# Authentication Service
# ---------------------------------------------------------------------------
def authenticate_user(
    email: str,
    password: str,
    client_ip: Optional[str] = None,
) -> tuple[Optional[UserRecord], Optional[str]]:
    """
    Authenticate against the database with 5-attempt rate-limiting.
    Returns (user, error_message).
    """
    clean_email = email.strip().lower()
    session = get_session()
    try:
        # Check rate-limiting
        failed_count = get_failed_login_count(session, clean_email, window_minutes=LOCKOUT_MINUTES)
        if failed_count >= MAX_FAILED_ATTEMPTS:
            return None, f"Account temporarily locked due to {failed_count} failed attempts. Please try again after {LOCKOUT_MINUTES} minutes."

        user = get_user_by_email(session, clean_email)
        if not user or not verify_password(password, user.password_hash):
            record_login_attempt(session, clean_email, client_ip, False)
            return None, "Invalid email or password"

        if not user.is_active:
            return None, "Account is disabled. Please contact an administrator."

        # Successful login
        record_login_attempt(session, clean_email, client_ip, True)
        clear_failed_login_attempts(session, clean_email)
        user.last_login_at = datetime.datetime.utcnow()
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user, None
    finally:
        session.close()


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """FastAPI dependency to extract and verify the current user from Bearer JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type (access token required)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        session = get_session()
        try:
            db_user = get_user_by_id(session, user_id)
            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User does not exist or has been deleted",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if not db_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is deactivated",
                )

            return User(
                id=db_user.id,
                email=db_user.email,
                role=UserRole(db_user.role),
                department=Department(db_user.department) if db_user.department else None,
                name=db_user.name,
                is_active=db_user.is_active,
            )
        finally:
            session.close()
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_viewer_or_above(current_user: User = Depends(get_current_user)) -> User:
    """Requires any logged-in user (VIEWER, DEPT_USER, CONTROLLER, ADMIN)."""
    return current_user


def require_dept_or_above(current_user: User = Depends(get_current_user)) -> User:
    """Requires role DEPT_USER, CONTROLLER, or ADMIN."""
    if current_user.role not in (UserRole.ADMIN, UserRole.CONTROLLER, UserRole.DEPT_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department user, Controller or Administrator access required",
        )
    return current_user


def require_controller(current_user: User = Depends(get_current_user)) -> User:
    """Requires role CONTROLLER or ADMIN."""
    if current_user.role not in (UserRole.ADMIN, UserRole.CONTROLLER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Controller or Administrator access required",
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requires role ADMIN."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


def can_access_task(user: User, task: Any) -> bool:
    """
    Check if a user has access to a specific task based on role and department:
    - DEPT_USER: only tasks within their assigned department.
    - CONTROLLER, ADMIN, VIEWER: can view tasks across all departments.
    """
    if user.role == UserRole.DEPT_USER:
        task_dept = getattr(task, "department", None)
        if hasattr(task_dept, "value"):
            task_dept = task_dept.value
        user_dept = getattr(user.department, "value", user.department) if user.department else None
        return task_dept == user_dept
    return True