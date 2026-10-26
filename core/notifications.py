"""
INTERNTRACK — In-App Notification Dispatcher
Sends state alerts to students, coordinators, and HODs.
"""

import uuid
from datetime import datetime
from database.db import execute, query_all

def notify(recipient, title, message, link=None):
    """Inserts an in-app notification for a given student USN or role ('COORDINATOR', 'HOD')."""
    notif_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute("""
    INSERT INTO notifications (id, recipient_usn_or_role, title, message, link, is_read, created_at)
    VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (notif_id, recipient, title, message, link, now))
    return notif_id

def get_notifications(recipient, unread_only=False):
    """Fetches notifications for a given student USN or role."""
    if unread_only:
        return query_all("""
        SELECT * FROM notifications 
        WHERE (recipient_usn_or_role = ? OR recipient_usn_or_role = 'ALL') AND is_read = 0
        ORDER BY created_at DESC LIMIT 50
        """, (recipient,))
    return query_all("""
    SELECT * FROM notifications 
    WHERE (recipient_usn_or_role = ? OR recipient_usn_or_role = 'ALL')
    ORDER BY created_at DESC LIMIT 50
    """, (recipient,))

def mark_read(notif_id):
    """Marks a notification as read."""
    execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
