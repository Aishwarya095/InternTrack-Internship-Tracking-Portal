"""
INTERNTRACK — Lab 5: Governed MCP-Style Connector
Chapter 10: Worklet 10 — Internship Application & Tracking Portal

CRITICAL LAB 5 ACCEPTANCE CRITERION:
"Expose every data source through one typed connector. No agent touches SQLite directly."

Fronts:
- Student Profiles
- Opportunity Listings
- Application Status & Submissions Feed
"""

import time
import hmac
import hashlib
from config import INTERNTRACK_GOVERNED_MCP_TOKEN
from database.db import query_one, query_all
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities, get_opportunity
from workflows.submissions import get_submissions_by_student, get_submission_by_id

class MCPConnectorServer:
    """
    Unified, schema-governed MCP-style data gateway.
    Enforces Bearer token authentication, role-based authorization, and transparent audit logging.
    """
    def __init__(self, auth_token=None):
        self.auth_token = auth_token or INTERNTRACK_GOVERNED_MCP_TOKEN
        self.access_logs = []

    def issue_token(self, actor_id: str, role: str) -> str:
        """
        Issues a cryptographically signed Bearer token for an actor and role.
        The secret token remains strictly on the server and is never exposed to clients.
        """
        actor_clean = str(actor_id).strip().upper()
        role_clean = str(role).strip().upper()
        payload = f"{actor_clean}:{role_clean}"
        sig = hmac.new(self.auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"mcp-{role_clean.lower()}-{actor_clean}-{sig}"

    def validate_token(self, token: str):
        """
        Validates a Bearer token.
        Returns (actor_id, role) if valid, or (None, None) if invalid/unrecognized.
        """
        if not token or not isinstance(token, str):
            return None, None
        token = token.strip()
        if token == self.auth_token:
            return "SYSTEM_ADMIN", "COORDINATOR"

        if token.startswith("mcp-"):
            rest = token[4:]
            subparts = rest.split("-")
            if len(subparts) >= 3:
                role_part = subparts[0].upper()
                sig_part = subparts[-1]
                actor_part = "-".join(subparts[1:-1]).upper()
                if role_part in ["STUDENT", "COORDINATOR", "HOD"]:
                    expected_sig = hmac.new(
                        self.auth_token.encode("utf-8"),
                        f"{actor_part}:{role_part}".encode("utf-8"),
                        hashlib.sha256
                    ).hexdigest()[:16]
                    if hmac.compare_digest(sig_part, expected_sig):
                        return actor_part, role_part
        return None, None

    def verify_auth(self, token: str):
        """
        Verifies Bearer token presence and cryptographic validity.
        Raises PermissionError if token is missing or invalid.
        """
        actor, role = self.validate_token(token)
        if not actor or not role:
            raise PermissionError("MCP Connector Auth Failed: Invalid or missing bearer token.")
        return actor, role

    def read_student_profile(self, usn: str, token: str):
        """
        Endpoint: read_student_profile
        Rules:
        - STUDENT: may only read their own profile.
        - COORDINATOR / HOD: may read any relevant student profile.
        """
        t0 = time.time()
        actor, role = self.verify_auth(token)
        usn_clean = str(usn).strip().upper()

        if role == "STUDENT" and actor != usn_clean:
            self._log_access("read_student_profile", {"usn": usn_clean}, (time.time() - t0) * 1000,
                             actor=actor, role=role, auth_result="FORBIDDEN_CROSS_STUDENT_ACCESS", status="FORBIDDEN")
            raise PermissionError(f"Access Denied: Student '{actor}' is not authorized to access profile of student '{usn_clean}'.")

        res = get_student_profile(usn_clean)
        self._log_access("read_student_profile", {"usn": usn_clean}, (time.time() - t0) * 1000,
                         actor=actor, role=role, auth_result="AUTHORIZED", status="SUCCESS")
        return res

    def read_opportunity_listings(self, domain=None, token=None):
        """
        Endpoint: read_opportunity_listings
        Rules:
        - STUDENT, COORDINATOR, and HOD may browse published opportunities.
        """
        t0 = time.time()
        actor, role = self.verify_auth(token)

        all_opps = list_opportunities(status="PUBLISHED")
        if domain:
            filtered = [o for o in all_opps if domain.lower() in o.get("domain", "").lower()]
        else:
            filtered = all_opps

        self._log_access("read_opportunity_listings", {"domain": domain}, (time.time() - t0) * 1000,
                         actor=actor, role=role, auth_result="AUTHORIZED", status="SUCCESS")
        return filtered

    def read_application_feed(self, student_usn=None, token=None):
        """
        Endpoint: read_application_feed
        Rules:
        - STUDENT: may only read their own application feed. Must NOT read another student's feed or global feed.
        - COORDINATOR / HOD: may read student application feeds or global coordinator queue.
        """
        t0 = time.time()
        actor, role = self.verify_auth(token)
        target_usn = str(student_usn).strip().upper() if student_usn else None

        if role == "STUDENT":
            if not target_usn or target_usn != actor:
                self._log_access("read_application_feed", {"student_usn": target_usn}, (time.time() - t0) * 1000,
                                 actor=actor, role=role, auth_result="FORBIDDEN_GLOBAL_OR_CROSS_STUDENT_FEED", status="FORBIDDEN")
                raise PermissionError(f"Access Denied: Student '{actor}' may only access their own application feed.")

        if target_usn:
            res = get_submissions_by_student(target_usn)
        else:
            res = query_all("SELECT * FROM student_submissions ORDER BY submitted_at DESC LIMIT 20")

        self._log_access("read_application_feed", {"student_usn": target_usn}, (time.time() - t0) * 1000,
                         actor=actor, role=role, auth_result="AUTHORIZED", status="SUCCESS")
        return res

    def get_connector_schema(self):
        """Returns typed machine-readable schema of exposed endpoints."""
        return {
            "connector_name": "InternTrack-Governed-MCP-Style-Gateway",
            "protocol_version": "1.0-mcp-style",
            "description": "Governed MCP-style data gateway with Bearer token authentication and role-based authorization.",
            "endpoints": [
                {
                    "name": "read_student_profile",
                    "parameters": {"usn": "string (Required)"},
                    "authorization": "STUDENT (self only) | COORDINATOR | HOD",
                    "returns": "StudentProfileSchema"
                },
                {
                    "name": "read_opportunity_listings",
                    "parameters": {"domain": "string (Optional)"},
                    "authorization": "STUDENT | COORDINATOR | HOD",
                    "returns": "List[OpportunitySchema]"
                },
                {
                    "name": "read_application_feed",
                    "parameters": {"student_usn": "string (Optional)"},
                    "authorization": "STUDENT (self only) | COORDINATOR | HOD",
                    "returns": "List[SubmissionStatusSchema]"
                }
            ]
        }

    def _log_access(self, endpoint, params, duration_ms, actor=None, role=None, auth_result="AUTHORIZED", status="SUCCESS"):
        """Logs access telemetry without exposing bearer tokens or credentials."""
        self.access_logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "actor": actor or "SYSTEM",
            "role": role or "UNKNOWN",
            "endpoint": endpoint,
            "params": params,
            "authorization_result": auth_result,
            "status": status,
            "duration_ms": round(duration_ms, 2)
        })

# Global singleton connector instance
mcp_connector = MCPConnectorServer()
