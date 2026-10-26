"""
INTERNTRACK — Authentication & Role-Based Access Control (RBAC)
Enforces backend security policies for Student, Coordinator, and HOD roles.
"""

from database.db import query_one
from config import ROLE_STUDENT, ROLE_COORDINATOR, ROLE_HOD, ROLE_ADMIN

def authenticate_user(email, password):
    """Authenticates credentials against the users table."""
    user = query_one("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
    if not user:
        return None
    # For demo simplicity, match plaintext password or hash
    if user["password_hash"] != password and user["password_hash"] != f"hash_{password}":
        return None
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "usn": user["usn"],
        "full_name": user["full_name"],
    }

def get_user_by_usn(usn):
    """Fetches user info linked to a given USN."""
    return query_one("SELECT * FROM users WHERE usn = ?", (usn,))

def check_permission(actor_role, required_roles):
    """Validates if the actor possesses one of the authorized roles."""
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    return actor_role in required_roles or actor_role == ROLE_ADMIN
