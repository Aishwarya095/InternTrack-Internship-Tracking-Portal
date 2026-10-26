"""
INTERNTRACK — 3-4 Month Internship Tracking & Progress Reports Workflow
Tracks active semester internships and manages bi-weekly journal submissions.
"""

import uuid
from datetime import datetime
from database.db import query_one, query_all, execute
from core.audit import log_event
from core.notifications import notify

def get_internships(student_usn=None, status=None):
    """Fetches internships with optional student or status filtering."""
    if student_usn:
        return query_all("""
        SELECT i.*, p.name as student_name, p.branch, p.email
        FROM internships i
        JOIN student_profiles p ON i.student_usn = p.usn
        WHERE i.student_usn = ?
        ORDER BY i.created_at DESC
        """, (student_usn,))
    elif status:
        return query_all("""
        SELECT i.*, p.name as student_name, p.branch, p.email
        FROM internships i
        JOIN student_profiles p ON i.student_usn = p.usn
        WHERE i.status = ?
        ORDER BY i.created_at DESC
        """, (status,))
    else:
        return query_all("""
        SELECT i.*, p.name as student_name, p.branch, p.email
        FROM internships i
        JOIN student_profiles p ON i.student_usn = p.usn
        ORDER BY i.created_at DESC
        """)

def submit_progress_report(internship_id, student_usn, data):
    """
    Student submits a bi-weekly progress journal report.
    Never overwrites previous submitted reports.
    """
    intern = query_one("SELECT * FROM internships WHERE id = ?", (internship_id,))
    if not intern:
        raise ValueError("Internship not found.")
    if intern["student_usn"] != student_usn:
        raise PermissionError("Students cannot submit reports for another student's internship.")

    rep_id = f"REP-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    execute("""
    INSERT INTO progress_reports (
        id, internship_id, student_usn, reporting_period, submission_date,
        work_completed, skills_learned, challenges, next_objectives, hours_logged, mentor_comments, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUBMITTED')
    """, (
        rep_id, internship_id, student_usn,
        data.get("reporting_period", "Weeks 1-2"), now[:10],
        data.get("work_completed", ""), data.get("skills_learned", ""),
        data.get("challenges", ""), data.get("next_objectives", ""),
        int(data.get("hours_logged", 40)), data.get("mentor_comments"),
    ))

    # Update internship status to ONGOING if was UPCOMING
    if intern["status"] == "UPCOMING":
        execute("UPDATE internships SET status = 'ONGOING' WHERE id = ?", (internship_id,))

    log_event(
        actor=student_usn,
        actor_role="STUDENT",
        action="PROGRESS_REPORT_SUBMITTED",
        record_id=rep_id,
        old_status=None,
        new_status="SUBMITTED",
        comments=f"Progress report submitted for {data.get('reporting_period', 'Period')}."
    )

    notify("COORDINATOR", "New Progress Report",
           f"Student {student_usn} submitted report for {intern['company']} ({data.get('reporting_period')}).")

    return query_one("SELECT * FROM progress_reports WHERE id = ?", (rep_id,))

def get_progress_reports(internship_id):
    """Retrieves all submitted progress reports for an internship."""
    return query_all("""
    SELECT * FROM progress_reports WHERE internship_id = ? ORDER BY submission_date ASC
    """, (internship_id,))

def review_progress_report(report_id, coordinator_name, mentor_comments, status="REVIEWED"):
    """Coordinator reviews and signs off on a progress report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute("""
    UPDATE progress_reports SET
        mentor_comments = ?,
        status = ?,
        reviewed_at = ?
    WHERE id = ?
    """, (mentor_comments, status, now, report_id))

    rep = query_one("SELECT * FROM progress_reports WHERE id = ?", (report_id,))
    if rep:
        log_event(
            actor=coordinator_name,
            actor_role="COORDINATOR",
            action="PROGRESS_REPORT_REVIEWED",
            record_id=report_id,
            old_status="SUBMITTED",
            new_status=status,
            comments=mentor_comments
        )
        notify(rep["student_usn"], "Progress Report Reviewed",
               f"Your progress report ({rep['reporting_period']}) was reviewed: {mentor_comments}")

    return rep
