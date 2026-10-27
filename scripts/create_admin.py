"""
Orion — Create Administrator CLI Script.
Creates or updates the initial ADMIN account in the database.
Never prints or logs the plain password.
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.auth import hash_password
from backend.database import (
    UserRecord,
    get_engine,
    get_session,
    get_user_by_email,
    init_db,
    save_user,
)
from railopt.models import UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_or_update_admin(name: str, email: str, password: str) -> None:
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)

    clean_email = email.strip().lower()
    clean_name = name.strip()

    try:
        existing = get_user_by_email(session, clean_email)
        pwd_hash = hash_password(password)

        if existing:
            existing.name = clean_name
            existing.password_hash = pwd_hash
            existing.role = UserRole.ADMIN.value
            existing.is_active = True
            save_user(session, existing)
            print(f"Successfully updated existing user '{clean_email}' to active ADMIN role.")
        else:
            new_user = UserRecord(
                id=f"usr_{uuid.uuid4().hex[:12]}",
                name=clean_name,
                email=clean_email,
                password_hash=pwd_hash,
                role=UserRole.ADMIN.value,
                department=None,
                is_active=True,
            )
            save_user(session, new_user)
            print(f"Successfully created initial ADMIN user: {clean_email} (ID: {new_user.id})")

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update Orion administrator account.")
    parser.add_argument("--name", default=None, help="Administrator full name")
    parser.add_argument("--email", default=None, help="Administrator email address")
    parser.add_argument("--password", default=None, help="Administrator password")

    args = parser.parse_args()

    name = args.name
    if not name:
        name = input("Enter admin name [System Admin]: ").strip() or "System Admin"

    email = args.email
    if not email:
        email = input("Enter admin email [admin@railopt.gov.in]: ").strip() or "admin@railopt.gov.in"

    password = args.password
    if not password:
        password = getpass.getpass("Enter admin password: ").strip()
        confirm = getpass.getpass("Confirm admin password: ").strip()
        if password != confirm:
            print("Error: Passwords do not match.")
            sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        sys.exit(1)

    create_or_update_admin(name, email, password)
