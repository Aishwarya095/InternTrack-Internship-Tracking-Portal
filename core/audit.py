"""
INTERNTRACK — Immutable Append-Only Audit Trail
Logs all consequential system events, state transitions, and actor decisions.
"""

import json
import uuid
from datetime import datetime
from database.db import execute, query_all

def log_event(actor, actor_role, action, record_id=None, old_status=None, new_status=None, comments=None, metadata=None):
    """
    Appends an immutable record to the audit_logs table.
    Guarantees that no history is overwritten or deleted.
    """
    log_id = f"AUDIT-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    meta_str = None
    if metadata:
        meta_str = json.dumps(metadata) if not isinstance(metadata, str) else metadata

    execute("""
    INSERT INTO audit_logs (id, actor, actor_role, action, record_id, old_status, new_status, comments, metadata, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (log_id, actor, actor_role, action, record_id, old_status, new_status, comments, meta_str, timestamp))

    return log_id

def get_audit_trail(limit=100, record_id=None):
    """Retrieves chronological audit events in descending order."""
    if record_id:
        return query_all("SELECT * FROM audit_logs WHERE record_id = ? ORDER BY timestamp DESC LIMIT ?", (record_id, limit))
    return query_all("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
