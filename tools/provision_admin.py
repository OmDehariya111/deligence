r"""Provision or reset a DeligenX administrator from environment variables.

Usage (PowerShell):
  $env:ADMIN_EMAIL = "admin@example.com"
  $env:ADMIN_PASSWORD = "a-long-unique-password"
  .\.venv\Scripts\python.exe .\tools\provision_admin.py

The password is deliberately accepted only through an environment variable and
is never written to stdout, the database as plain text, or source control.
"""

import os
import sys
from pathlib import Path

# When this file is executed directly, Python otherwise only adds ``tools/``
# to its import path. Add the repository root explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func

from api.auth_utils import get_password_hash
from api.database import SessionLocal
from api.models import User


def require_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be set.")
    return value


def main() -> int:
    try:
        email = require_setting("ADMIN_EMAIL").lower()
        password = require_setting("ADMIN_PASSWORD")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if len(password) < 12:
        print("Error: ADMIN_PASSWORD must contain at least 12 characters.", file=sys.stderr)
        return 2

    full_name = os.getenv("ADMIN_FULL_NAME", "DeligenX Administrator").strip() or "DeligenX Administrator"
    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).one_or_none()
        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
                is_active=1,
                is_admin=True,
            )
            db.add(user)
            outcome = "created"
        else:
            user.email = email
            user.full_name = full_name
            user.hashed_password = get_password_hash(password)
            user.is_active = 1
            user.is_admin = True
            outcome = "updated"

        db.commit()
        print(f"Administrator account {outcome} for {email}.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
