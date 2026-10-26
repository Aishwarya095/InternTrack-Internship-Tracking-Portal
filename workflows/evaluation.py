"""
INTERNTRACK — Final Internship Evaluation & Academic Credits Workflow
Compiles final evaluation scoring, employer feedback, and 8th-sem credit sign-off.
"""

import uuid
from datetime import datetime
from database.db import query_one, query_all, execute
from core.audit import log_event
from core.notifications import notify

def calculate_grade(total_score):
    """Computes academic letter grade based on final composite score."""
    if total_score >= 90:
        return "S"
    elif total_score >= 80:
        return "A"
    elif total_score >= 70:
        return "B"
    elif total_score >= 60:
        return "C"
    elif total_score >= 50:
        return "D"
    else:
        return "F"

def record_evaluation(internship_id, evaluator_name, data):
    """
    Records or updates a final evaluation for an internship.
    Enforces strict score bounds: Mentor (40), Presentation (30), Report (30).
    """
    intern = query_one("SELECT * FROM internships WHERE id = ?", (internship_id,))
    if not intern:
        raise ValueError("Internship not found.")

    m_score = float(data.get("mentor_score", 0.0))
    p_score = float(data.get("presentation_score", 0.0))
    r_score = float(data.get("report_score", 0.0))

    if not (0 <= m_score <= 40):
        raise ValueError("Mentor score must be between 0 and 40.")
    if not (0 <= p_score <= 30):
        raise ValueError("Presentation score must be between 0 and 30.")
    if not (0 <= r_score <= 30):
        raise ValueError("Report score must be between 0 and 30.")

    total_score = round(m_score + p_score + r_score, 1)
    proposed_grade = calculate_grade(total_score)
    credits = 12

    eval_id = f"EVAL-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing = query_one("SELECT * FROM evaluations WHERE internship_id = ?", (internship_id,))
    if existing:
        execute("""
        UPDATE evaluations SET
            employer_feedback = ?,
            mentor_assessment = ?,
            mentor_score = ?,
            presentation_score = ?,
            report_score = ?,
            total_score = ?,
            proposed_grade = ?,
            evaluator_name = ?,
            evaluated_at = ?
        WHERE internship_id = ?
        """, (
            data.get("employer_feedback", ""), data.get("mentor_assessment", ""),
            m_score, p_score, r_score, total_score, proposed_grade,
            evaluator_name, now, internship_id
        ))
        eval_id = existing["id"]
    else:
        execute("""
        INSERT INTO evaluations (
            id, internship_id, student_usn, employer_feedback, mentor_assessment,
            mentor_score, presentation_score, report_score, total_score, proposed_grade,
            academic_credits, evaluator_name, approval_status, evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_APPROVAL', ?)
        """, (
            eval_id, internship_id, intern["student_usn"],
            data.get("employer_feedback", ""), data.get("mentor_assessment", ""),
            m_score, p_score, r_score, total_score, proposed_grade,
            credits, evaluator_name, now
        ))

    log_event(
        actor=evaluator_name,
        actor_role="COORDINATOR",
        action="FINAL_EVALUATION_RECORDED",
        record_id=eval_id,
        old_status=None,
        new_status="PENDING_APPROVAL",
        comments=f"Final score: {total_score}/100. Proposed Grade: {proposed_grade}.",
        metadata={"total_score": total_score, "grade": proposed_grade}
    )

    notify("HOD", "Evaluation Pending Sign-off",
           f"Final evaluation for {intern['student_usn']} is ready for review and credit sign-off.")

    return query_one("SELECT * FROM evaluations WHERE id = ?", (eval_id,))

def finalize_evaluation(eval_id, signoff_authority, actor_role="HOD"):
    """
    Human sign-off (Coordinator / HOD) to finalize academic credits and grade.
    Both Coordinator and HOD have authority to sanction credits.
    """
    evaluation = query_one("SELECT * FROM evaluations WHERE id = ?", (eval_id,))
    if not evaluation:
        raise ValueError("Evaluation record not found.")

    execute("""
    UPDATE evaluations SET
        approval_status = 'FINALIZED'
    WHERE id = ?
    """, (eval_id,))

    # Update internship to COMPLETED
    execute("""
    UPDATE internships SET status = 'COMPLETED' WHERE id = ?
    """, (evaluation["internship_id"],))

    log_event(
        actor=signoff_authority,
        actor_role=actor_role,
        action="FINAL_EVALUATION_FINALIZED",
        record_id=eval_id,
        old_status="PENDING_APPROVAL",
        new_status="FINALIZED",
        comments=f"Academic credits ({evaluation['academic_credits']}) and Grade ({evaluation['proposed_grade']}) signed off by {signoff_authority} ({actor_role})."
    )

    notify(evaluation["student_usn"], "Internship Grade Finalized! 🎓",
           f"Your 8th-semester internship grade is FINALIZED: Grade {evaluation['proposed_grade']} ({evaluation['total_score']}/100).")

    return query_one("SELECT * FROM evaluations WHERE id = ?", (eval_id,))


def get_all_evaluations():
    """Fetches all final evaluations joined with internship and student details."""
    return query_all("""
    SELECT e.*, i.company, i.role as internship_role, p.name as student_name, p.branch
    FROM evaluations e
    JOIN internships i ON e.internship_id = i.id
    JOIN student_profiles p ON e.student_usn = p.usn
    ORDER BY e.total_score DESC
    """)
