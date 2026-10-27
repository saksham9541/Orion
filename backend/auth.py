"""
RailOpt - Mock Authentication Module for Hackathon

Tokens are signed JWTs (PyJWT), so they cannot be faked without the server's
secret key. Users are still hardcoded demo users (mock auth, not production auth).

Setup:
    pip install pyjwt python-dotenv
    Set RAILOPT_SECRET (32+ characters) in your environment or in a .env file.
    Never hardcode the secret in this file.
"""

import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Load a .env file if python-dotenv is installed (optional).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from backend.schemas import User
from railopt.models import UserRole, Department

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("RAILOPT_SECRET")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "RAILOPT_SECRET is missing or too short (need 32+ characters). "
        "PowerShell example: $env:RAILOPT_SECRET='put-a-long-random-string-here-1234567890'"
    )

ALGORITHM = "HS256"
TOKEN_LIFETIME_HOURS = 8

# Default: requests with no token get a 401.
# For demos only: set RAILOPT_ALLOW_ANON=1 to let no-token requests act as
# the lowest-privilege user (Technician) instead of getting a 401.
ALLOW_ANONYMOUS = os.environ.get("RAILOPT_ALLOW_ANON", "0") == "1"

security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Hardcoded demo users for the hackathon
# ---------------------------------------------------------------------------
MOCK_USERS = {
    "admin@railopt.gov.in": {
        "email": "admin@railopt.gov.in",
        "password": "password123",
        "role": UserRole.SUPER_ADMIN,
        "department": None,
        "name": "Super Admin",
    },
    "trd@railopt.gov.in": {
        "email": "trd@railopt.gov.in",
        "password": "password123",
        "role": UserRole.DEPT_ADMIN,
        "department": Department.TRD,
        "name": "TRD Admin",
    },
    "snt@railopt.gov.in": {
        "email": "snt@railopt.gov.in",
        "password": "password123",
        "role": UserRole.DEPT_ADMIN,
        "department": Department.SNT,
        "name": "S&T Admin",
    },
    "eng@railopt.gov.in": {
        "email": "eng@railopt.gov.in",
        "password": "password123",
        "role": UserRole.DEPT_ADMIN,
        "department": Department.ENGINEERING,
        "name": "Eng Admin",
    },
    "tech@railopt.gov.in": {
        "email": "tech@railopt.gov.in",
        "password": "password123",
        "role": UserRole.TECHNICIAN,
        "department": None,
        "name": "Maintenance Tech",
    },
}


def authenticate_user(email: str, password: str):
    """
    Check email + password against MOCK_USERS.
    Returns the stored user dict, or None if the login is wrong.
    Use this in the login route so the password is really checked.
    """
    stored_user = MOCK_USERS.get(email)
    if not stored_user:
        return None
    if not hmac.compare_digest(stored_user["password"], password):
        return None
    return stored_user


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def create_access_token(user: dict) -> str:
    """
    Create a signed JWT. Only the email goes in the token.
    Role and department are always looked up from MOCK_USERS on each request,
    so the token can never carry its own privileges.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["email"],
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_LIFETIME_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Verify the JWT and return the matching User.

    - No token: 401 by default (or lowest-privilege user if RAILOPT_ALLOW_ANON=1).
    - Fake, edited, or expired token: 401.
    - Role and department come from MOCK_USERS, never from the token body.
    """
    if not credentials:
        if ALLOW_ANONYMOUS:
            return User(
                email="tech@railopt.gov.in",
                role=UserRole.TECHNICIAN,
                department=None,
                name="Unauthenticated (default: lowest privilege)",
            )
        raise _unauthorized("Not authenticated")

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        stored_user = MOCK_USERS.get(payload.get("sub"))
        if not stored_user:
            raise ValueError("Unknown user")

        return User(
            email=stored_user["email"],
            role=stored_user["role"],
            department=stored_user["department"],
            name=stored_user["name"],
        )
    except Exception:
        raise _unauthorized()


# ---------------------------------------------------------------------------
# Role checks
# ---------------------------------------------------------------------------
def require_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user