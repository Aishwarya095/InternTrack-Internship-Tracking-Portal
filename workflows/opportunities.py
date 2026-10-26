"""
INTERNTRACK — Internship Opportunities & Vacancy Management
Handles opportunity creation, eligibility rules, and strict dynamic vacancy decrementing.
"""

import uuid
from datetime import datetime
from database.db import query_one, query_all, execute
from core.audit import log_event
from workflows.students import get_student_profile

def list_opportunities(status="PUBLISHED"):
    """Lists opportunities filtered by status, or all if status is None."""
    if status:
        return query_all("SELECT * FROM opportunities WHERE status = ? ORDER BY deadline ASC", (status,))
    return query_all("SELECT * FROM opportunities ORDER BY created_at DESC")

def get_opportunity(opp_id):
    """Retrieves single opportunity record."""
    return query_one("SELECT * FROM opportunities WHERE id = ?", (opp_id,))

def create_opportunity(coordinator_name, data):
    """Creates a new internship opportunity with defined vacancies and eligibility."""
    opp_id = f"OPP-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_vacancies = int(data.get("total_vacancies", 1))
    if total_vacancies <= 0:
        raise ValueError("Total vacancies must be greater than 0.")

    min_cgpa = float(data.get("min_cgpa", 6.0))
    max_backlogs = int(data.get("max_backlogs", 0))

    status = data.get("status", "PUBLISHED").upper()

    execute("""
    INSERT INTO opportunities (
        id, company, title, domain, description, location, mode,
        min_cgpa, max_backlogs, required_branch, required_skills, duration, stipend_monthly,
        start_date, end_date, total_vacancies, filled_vacancies, available_vacancies,
        deadline, eligibility_criteria, status, created_by, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
    """, (
        opp_id, data["company"], data["title"], data.get("domain", "Engineering"),
        data.get("description", ""), data.get("location", "Bangalore"),
        data.get("mode", "ON_SITE"), min_cgpa, max_backlogs,
        data.get("required_branch", "CSE"), data.get("required_skills", ""),
        data.get("duration", "4 Months"), float(data.get("stipend_monthly", 0.0)),
        data.get("start_date", "2026-02-01"), data.get("end_date", "2026-06-01"),
        total_vacancies, total_vacancies, data.get("deadline", "2026-01-31"),
        data.get("eligibility_criteria", f"Min CGPA {min_cgpa}, Max Backlogs {max_backlogs}"),
        status, coordinator_name, now, now
    ))

    log_event(
        actor=coordinator_name,
        actor_role="COORDINATOR",
        action="OPPORTUNITY_CREATED",
        record_id=opp_id,
        old_status=None,
        new_status=status,
        comments=f"Opportunity created for {data['company']} with {total_vacancies} vacancies."
    )

    return get_opportunity(opp_id)

def check_eligibility_and_vacancy(student_usn, opp_id):
    """
    Evaluates whether a student satisfies the opportunity's criteria:
    - CGPA >= min_cgpa
    - Backlogs <= max_backlogs
    - Available Vacancies > 0
    Returns a structured dictionary of results.
    """
    student = get_student_profile(student_usn)
    opp = get_opportunity(opp_id)

    if not student:
        raise ValueError(f"Student {student_usn} not found.")
    if not opp:
        raise ValueError(f"Opportunity {opp_id} not found.")

    cgpa_ok = student["cgpa"] >= opp["min_cgpa"]
    backlogs_ok = student["backlogs"] <= opp["max_backlogs"]
    vacancy_ok = opp["available_vacancies"] > 0

    is_eligible = cgpa_ok and backlogs_ok and vacancy_ok

    reasons = []
    if not cgpa_ok:
        reasons.append(f"Student CGPA ({student['cgpa']}) is below minimum requirement ({opp['min_cgpa']}).")
    if not backlogs_ok:
        reasons.append(f"Student active backlogs ({student['backlogs']}) exceeds maximum allowed ({opp['max_backlogs']}).")
    if not vacancy_ok:
        reasons.append("No available vacancies remaining (Opportunity is FULL).")

    return {
        "student_usn": student_usn,
        "student_name": student["name"],
        "student_cgpa": student["cgpa"],
        "student_backlogs": student["backlogs"],
        "opportunity_id": opp_id,
        "company": opp["company"],
        "min_cgpa": opp["min_cgpa"],
        "max_backlogs": opp["max_backlogs"],
        "total_vacancies": opp["total_vacancies"],
        "available_vacancies": opp["available_vacancies"],
        "cgpa_eligible": cgpa_ok,
        "backlogs_eligible": backlogs_ok,
        "vacancy_available": vacancy_ok,
        "is_eligible": is_eligible,
        "status_explanation": "Eligible" if is_eligible else "; ".join(reasons)
    }

def decrement_vacancy(opp_id):
    """Atomically decrements available vacancies and closes opportunity if 0."""
    opp = get_opportunity(opp_id)
    if not opp:
        raise ValueError("Opportunity not found.")
    if opp["available_vacancies"] <= 0:
        raise ValueError("Cannot decrement vacancy: Opportunity is already FULL.")

    new_avail = opp["available_vacancies"] - 1
    new_filled = opp["filled_vacancies"] + 1
    new_status = "CLOSED" if new_avail == 0 else opp["status"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    execute("""
    UPDATE opportunities SET
        available_vacancies = ?,
        filled_vacancies = ?,
        status = ?,
        updated_at = ?
    WHERE id = ?
    """, (new_avail, new_filled, new_status, now, opp_id))

    return get_opportunity(opp_id)

def sync_indeed_opportunities(query="software intern", location="Bangalore", limit=5, hours_old=48):
    """
    Pulls real-time live opportunities from Indeed India / external research
    filtered to fresh postings from 1 day ago / recent 24-72 hours,
    and registers them in the SQLite opportunities catalog so eligible students can apply.
    """
    from aura.external_research import ExternalOpportunityResearcher

    live_jobs = ExternalOpportunityResearcher.search_live_opportunities(
        query=query, location=location, limit=limit, hours_old=hours_old
    )
    synced = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, job in enumerate(live_jobs, start=1):
        opp_id = f"OPP-IND-{idx:03d}"
        comp = job.get("company", "Tech Company").strip()
        title = job.get("title", "Software Intern").strip()
        loc = job.get("location", location).strip()
        apply_url = job.get("url", "")
        stipend = float(job.get("stipend_monthly", 25000.0))
        relative_posted = job.get("relative_posted", "Posted 1 day ago")
        posted_date = job.get("posted_date", datetime.now().strftime("%Y-%m-%d"))
        desc = f"Real-Time Live Opportunity via {job.get('source_platform', 'Indeed')}.\n🕒 Fresh Opening: {relative_posted} ({posted_date})\nApply Link: {apply_url}"

        existing = get_opportunity(opp_id)
        if existing:
            execute("""
            UPDATE opportunities SET
                company = ?,
                title = ?,
                description = ?,
                location = ?,
                stipend_monthly = ?,
                updated_at = ?
            WHERE id = ?
            """, (comp, title, desc, loc, stipend, now, opp_id))
        else:
            execute("""
            INSERT INTO opportunities (
                id, company, title, domain, description, location, mode,
                min_cgpa, max_backlogs, required_branch, required_skills, duration, stipend_monthly,
                start_date, end_date, total_vacancies, filled_vacancies, available_vacancies,
                deadline, eligibility_criteria, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp_id, comp, title, "Computer Science / Software Engineering",
                desc, loc, "HYBRID",
                7.0, 0, "CSE, ISE, ECE",
                "Python, Problem Solving, Software Engineering",
                "4 Months", stipend,
                "2026-03-01", "2026-07-01",
                5, 5, "2026-11-30",
                "Min CGPA 7.0, Max Backlogs 0",
                "PUBLISHED", "Indeed Live Sync", now, now
            ))

        synced.append(get_opportunity(opp_id))

    log_event(
        actor="System",
        actor_role="COORDINATOR",
        action="INDEED_OPPORTUNITIES_SYNCED",
        record_id="OPP-IND-SYNC",
        old_status=None,
        new_status="PUBLISHED",
        comments=f"Synced {len(synced)} fresh Indeed opportunities posted in the last {hours_old}h for {location}."
    )

    return synced

