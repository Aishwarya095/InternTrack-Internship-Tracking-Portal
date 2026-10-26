"""
INTERNTRACK — Student Submission & Coordinator Review Workflow
Implements multi-submission versioning, coordinator review desk, mandatory rejection reasons,
placed-company bypass, and HOD departmental sanction.
"""

import uuid
from datetime import datetime
from database.db import query_one, query_all, execute
from core.audit import log_event
from core.notifications import notify
from workflows.students import get_student_profile, mark_placed_company

def create_submission(usn, data, actor_name=None):
    """
    Creates a new student submission.
    Guarantees that past submissions are NEVER overwritten; creates version N+1.
    Handles Placed Company bypass vs Normal 4 Preferences.
    """
    student = get_student_profile(usn)
    name = data.get("student_name") or data.get("name")
    branch = data.get("branch")
    cgpa = data.get("cgpa")
    from workflows.students import upsert_student_profile
    if not student or name or branch or cgpa:
        student = upsert_student_profile(
            usn=usn,
            name=name or (student["name"] if student else "Student"),
            branch=branch or (student["branch"] if student else "CSE"),
            cgpa=cgpa if cgpa is not None else (student["cgpa"] if student else 8.0)
        )

    # Find highest submission version for student
    latest = query_one("""
    SELECT MAX(submission_version) as max_v FROM student_submissions WHERE student_usn = ?
    """, (usn,))
    next_version = (latest["max_v"] or 0) + 1 if latest else 1

    sub_id = f"SUB-{usn}-{next_version}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    submission_type = data.get("submission_type", "NORMAL").upper()

    if submission_type == "PLACED_COMPANY":
        placed_company = data.get("placed_company_name")
        placement_details = data.get("placement_details", "Campus placement integrated internship")
        placed_duration = data.get("placed_duration", "4 Months")

        if not placed_company or not placed_company.strip():
            raise ValueError("Placed company name is required for campus placement workflow.")

        # Update student profile placement state directly
        mark_placed_company(usn, placed_company, placement_details, placed_duration)

        status = "CONFIRMED"
        coordinator_decision = "APPROVED"
        comments = "Campus placement verified. Standard internship application bypassed."

        execute("""
        INSERT INTO student_submissions (
            id, student_usn, submission_version, submission_type,
            placed_company_name, placement_details, placed_duration,
            status, coordinator_decision, coordinator_comments,
            approved_company, approved_role, approved_duration,
            coordinator_id, coordinator_timestamp, hod_status, hod_timestamp, submitted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sub_id, usn, next_version, "PLACED_COMPANY",
            placed_company, placement_details, placed_duration,
            status, coordinator_decision, comments,
            placed_company, data.get("placed_role", "Software Engineering Intern"), placed_duration,
            "COORDINATOR_SYSTEM", now, "APPROVED", now, now
        ))

        # Create active internship tracking record immediately
        intern_id = f"INT-{uuid.uuid4().hex[:6].upper()}"
        start_date = data.get("start_date", "2026-01-15")
        end_date = data.get("end_date", "2026-05-15")

        execute("""
        INSERT INTO internships (
            id, submission_id, student_usn, company, role, domain, internship_type,
            mentor_name, coordinator_name, start_date, expected_end_date, duration, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            intern_id, sub_id, usn, placed_company,
            data.get("placed_role", "Software Engineering Intern"),
            data.get("placed_domain", "Enterprise Systems"),
            "PLACED_COMPANY", data.get("mentor_name", "Industry Mentor"),
            "Internship Coordinator", start_date, end_date, placed_duration, "ONGOING", now
        ))

        log_event(
            actor=actor_name or student["name"],
            actor_role="STUDENT",
            action="PLACED_COMPANY_INTERNSHIP_CONFIRMED",
            record_id=sub_id,
            old_status=None,
            new_status="CONFIRMED",
            comments=f"Campus placement at {placed_company} directly confirmed. Bypassed application queue.",
            metadata={"company": placed_company, "internship_id": intern_id}
        )

        notify("COORDINATOR", "Placed Student Confirmed",
               f"{student['name']} ({usn}) recorded placed-company internship at {placed_company}.")

        return query_one("SELECT * FROM student_submissions WHERE id = ?", (sub_id,))

    # Standard Normal Form with up to 4 Company Preferences
    p1_company = data.get("pref_1_company")
    p1_role = data.get("pref_1_role")
    p1_loc = data.get("pref_1_location")
    p1_rem = data.get("pref_1_remarks")

    p2_company = data.get("pref_2_company")
    p2_role = data.get("pref_2_role")
    p2_loc = data.get("pref_2_location")
    p2_rem = data.get("pref_2_remarks")

    p3_company = data.get("pref_3_company")
    p3_role = data.get("pref_3_role")
    p3_loc = data.get("pref_3_location")
    p3_rem = data.get("pref_3_remarks")

    p4_company = data.get("pref_4_company")
    p4_role = data.get("pref_4_role")
    p4_loc = data.get("pref_4_location")
    p4_rem = data.get("pref_4_remarks")

    if not p1_company:
        raise ValueError("At least Company Preference 1 is required.")

    status = "SUBMITTED"

    execute("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        pref_1_company, pref_1_role, pref_1_location, pref_1_remarks,
        pref_2_company, pref_2_role, pref_2_location, pref_2_remarks,
        pref_3_company, pref_3_role, pref_3_location, pref_3_remarks,
        pref_4_company, pref_4_role, pref_4_location, pref_4_remarks,
        status, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sub_id, usn, next_version, "NORMAL",
        p1_company, p1_role, p1_loc, p1_rem,
        p2_company, p2_role, p2_loc, p2_rem,
        p3_company, p3_role, p3_loc, p3_rem,
        p4_company, p4_role, p4_loc, p4_rem,
        status, now
    ))

    log_event(
        actor=actor_name or student["name"],
        actor_role="STUDENT",
        action="STUDENT_SUBMITTED_FORM",
        record_id=sub_id,
        old_status=None,
        new_status=status,
        comments=f"Submitted internship preferences (Version {next_version}). Pref 1: {p1_company}.",
        metadata={"version": next_version, "pref1": p1_company}
    )

    notify("COORDINATOR", f"New Submission (v{next_version})",
           f"{student['name']} ({usn}) submitted internship preferences (v{next_version}).")

    return query_one("SELECT * FROM student_submissions WHERE id = ?", (sub_id,))

def get_submission_by_id(sub_id):
    """Fetches a specific submission with student details."""
    return query_one("""
    SELECT s.*, p.name as student_name, p.branch, p.cgpa, p.backlogs, p.email, p.phone
    FROM student_submissions s
    JOIN student_profiles p ON s.student_usn = p.usn
    WHERE s.id = ?
    """, (sub_id,))

def get_submissions_by_student(usn):
    """Retrieves complete submission history for a student ordered by version descending."""
    return query_all("""
    SELECT * FROM student_submissions 
    WHERE student_usn = ? 
    ORDER BY submission_version DESC
    """, (usn,))

def get_all_submissions(status_filter=None):
    """Lists all submissions for the coordinator review queue."""
    if status_filter:
        return query_all("""
        SELECT s.*, p.name as student_name, p.branch, p.cgpa, p.backlogs
        FROM student_submissions s
        JOIN student_profiles p ON s.student_usn = p.usn
        WHERE s.status = ?
        ORDER BY s.submitted_at DESC
        """, (status_filter,))
    return query_all("""
    SELECT s.*, p.name as student_name, p.branch, p.cgpa, p.backlogs
    FROM student_submissions s
    JOIN student_profiles p ON s.student_usn = p.usn
    ORDER BY s.submitted_at DESC
    """)

def coordinator_review_submission(sub_id, decision, coordinator_name, data):
    """
    Executes coordinator decision on a submission:
    - APPROVE: Requires approved company, role, duration. Transitions to COORDINATOR_APPROVED.
    - REJECT: MANDATORY REJECTION REASON. Transitions to REJECTED.
    - CORRECTION_REQUIRED: Transitions to CORRECTION_REQUIRED.
    """
    sub = get_submission_by_id(sub_id)
    if not sub:
        raise ValueError(f"Submission {sub_id} not found.")

    decision = decision.upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_status = sub["status"]

    if decision == "APPROVE":
        approved_company = data.get("approved_company") or sub["pref_1_company"]
        approved_role = data.get("approved_role") or sub["pref_1_role"] or "Intern"
        approved_duration = data.get("approved_duration") or "4 Months"
        comments = data.get("coordinator_comments", "Approved after coordinator review.")

        # Update submission status
        new_status = "COORDINATOR_APPROVED"
        execute("""
        UPDATE student_submissions SET
            status = ?,
            coordinator_decision = 'APPROVED',
            coordinator_comments = ?,
            rejection_reason = NULL,
            approved_company = ?,
            approved_role = ?,
            approved_duration = ?,
            coordinator_id = ?,
            coordinator_timestamp = ?
        WHERE id = ?
        """, (new_status, comments, approved_company, approved_role, approved_duration, coordinator_name, now, sub_id))

        # Check if opportunity exists to decrement vacancy dynamically
        opp = query_one("SELECT * FROM opportunities WHERE company LIKE ?", (f"%{approved_company}%",))
        if opp and opp["available_vacancies"] > 0:
            new_avail = opp["available_vacancies"] - 1
            new_filled = opp["filled_vacancies"] + 1
            opp_status = "CLOSED" if new_avail == 0 else opp["status"]
            execute("""
            UPDATE opportunities SET
                available_vacancies = ?,
                filled_vacancies = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """, (new_avail, new_filled, opp_status, now, opp["id"]))

        # Create tracking record (or advance to HOD if required)
        intern_id = f"INT-{uuid.uuid4().hex[:6].upper()}"
        start_date = data.get("start_date", "2026-01-15")
        end_date = data.get("end_date", "2026-05-15")

        execute("""
        INSERT INTO internships (
            id, submission_id, student_usn, company, role, domain, internship_type,
            mentor_name, coordinator_name, start_date, expected_end_date, duration, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            intern_id, sub_id, sub["student_usn"], approved_company, approved_role,
            data.get("domain", "Engineering"), "NORMAL",
            data.get("mentor_name", "Assigned Faculty Mentor"),
            coordinator_name, start_date, end_date, approved_duration, "UPCOMING", now
        ))

        log_event(
            actor=coordinator_name,
            actor_role="COORDINATOR",
            action="COORDINATOR_APPROVED_SUBMISSION",
            record_id=sub_id,
            old_status=old_status,
            new_status=new_status,
            comments=f"Approved for {approved_company} ({approved_duration}).",
            metadata={"company": approved_company, "role": approved_role}
        )

        notify(sub["student_usn"], "Internship Approved! 🎉",
               f"Your internship application has been APPROVED by the Coordinator for {approved_company}.")

        return get_submission_by_id(sub_id)

    elif decision == "REJECT":
        rejection_reason = data.get("rejection_reason")
        # STRICT REQUIREMENT: Rejection reason is mandatory
        if not rejection_reason or not rejection_reason.strip():
            raise ValueError("A mandatory rejection reason must be provided when rejecting a submission.")

        comments = data.get("coordinator_comments", "Application rejected.")
        new_status = "REJECTED"

        execute("""
        UPDATE student_submissions SET
            status = ?,
            coordinator_decision = 'REJECTED',
            rejection_reason = ?,
            coordinator_comments = ?,
            coordinator_id = ?,
            coordinator_timestamp = ?
        WHERE id = ?
        """, (new_status, rejection_reason.strip(), comments, coordinator_name, now, sub_id))

        log_event(
            actor=coordinator_name,
            actor_role="COORDINATOR",
            action="COORDINATOR_REJECTED_SUBMISSION",
            record_id=sub_id,
            old_status=old_status,
            new_status=new_status,
            comments=f"Reason: {rejection_reason.strip()}",
            metadata={"rejection_reason": rejection_reason.strip()}
        )

        notify(sub["student_usn"], "Application Rejected",
               f"Your internship application was rejected. Reason: {rejection_reason.strip()}. You may review feedback and resubmit.")

        return get_submission_by_id(sub_id)

    elif decision == "CORRECTION_REQUIRED":
        comments = data.get("coordinator_comments") or "Please clarify or correct company preferences."
        new_status = "CORRECTION_REQUIRED"

        execute("""
        UPDATE student_submissions SET
            status = ?,
            coordinator_decision = 'NEEDS_CORRECTION',
            coordinator_comments = ?,
            coordinator_id = ?,
            coordinator_timestamp = ?
        WHERE id = ?
        """, (new_status, comments, coordinator_name, now, sub_id))

        log_event(
            actor=coordinator_name,
            actor_role="COORDINATOR",
            action="COORDINATOR_REQUESTED_CORRECTION",
            record_id=sub_id,
            old_status=old_status,
            new_status=new_status,
            comments=comments
        )

        notify(sub["student_usn"], "Correction Requested",
               f"The Coordinator requested corrections on your application: {comments}")

        return get_submission_by_id(sub_id)

    else:
        raise ValueError(f"Invalid coordinator decision: {decision}. Must be APPROVE, REJECT, or CORRECTION_REQUIRED.")

def hod_review_submission(sub_id, decision, hod_name, comments=None):
    """
    Executes HOD departmental review.
    """
    sub = get_submission_by_id(sub_id)
    if not sub:
        raise ValueError(f"Submission {sub_id} not found.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decision = decision.upper()

    if decision == "APPROVE":
        execute("""
        UPDATE student_submissions SET
            status = 'CONFIRMED',
            hod_status = 'APPROVED',
            hod_comments = ?,
            hod_timestamp = ?
        WHERE id = ?
        """, (comments or "HOD Departmental Sanction Approved.", now, sub_id))

        execute("""
        UPDATE internships SET status = 'ONGOING' WHERE submission_id = ?
        """, (sub_id,))

        log_event(
            actor=hod_name,
            actor_role="HOD",
            action="HOD_APPROVED_SUBMISSION",
            record_id=sub_id,
            old_status=sub["status"],
            new_status="CONFIRMED",
            comments=comments or "HOD Sanction Approved."
        )

        notify(sub["student_usn"], "Internship Confirmed by HOD! 🎓",
               "Your internship has received final HOD approval and is now officially CONFIRMED.")

        return get_submission_by_id(sub_id)

    elif decision == "REJECT":
        if not comments:
            raise ValueError("HOD must provide remarks when rejecting.")

        execute("""
        UPDATE student_submissions SET
            status = 'REJECTED',
            hod_status = 'REJECTED',
            hod_comments = ?,
            hod_timestamp = ?
        WHERE id = ?
        """, (comments, now, sub_id))

        log_event(
            actor=hod_name,
            actor_role="HOD",
            action="HOD_REJECTED_SUBMISSION",
            record_id=sub_id,
            old_status=sub["status"],
            new_status="REJECTED",
            comments=comments
        )

        notify(sub["student_usn"], "HOD Decision: Rejected",
               f"Departmental approval was rejected by HOD: {comments}")

        return get_submission_by_id(sub_id)
    else:
        raise ValueError(f"Invalid HOD decision: {decision}")
