"""
INTERNTRACK — Lab 2: Tool-Using Agent (Grounded Lookups & Execution Tracing)
Chapter 10: Worklet 10 — Internship Application & Tracking Portal

CRITICAL LAB 2 ACCEPTANCE CRITERION:
"Key numbers and lookups always go through tools, never hand-done in the prompt."

The agent executes typed tools against the real database and produces a transparent
execution trace for visible demonstration.
"""

import time
import json
from database.db import query_one, query_all
from workflows.students import get_student_profile
from workflows.opportunities import get_opportunity, list_opportunities, check_eligibility_and_vacancy
from workflows.submissions import get_submission_by_id, get_submissions_by_student
from workflows.tracking import get_internships, get_progress_reports

from aura.lab4_memory import get_or_create_session

# ---- Tool Definitions ----

def read_student_profile(usn):
    """Tool: Fetches factual student profile directly from database and active memory."""
    profile = get_student_profile(usn)
    if not profile:
        return {"error": f"Student with USN '{usn}' not found."}
    
    session = get_or_create_session(usn)
    res = {
        "usn": profile["usn"],
        "name": profile["name"],
        "branch": profile["branch"],
        "semester": profile["semester"],
        "cgpa": profile["cgpa"],
        "backlogs": profile["backlogs"],
        "credits": profile["credits"],
        "placement_status": profile["placement_status"],
        "placed_company": profile["placed_company"]
    }
    if session and session.student_answers:
        res["memory_domain_target"] = session.student_answers.get("domain_interest")
        res["memory_preferred_location"] = session.student_answers.get("preferred_location")
    if session and session.revised_plan:
        res["active_plan_title"] = session.revised_plan.get("title")
        res["plan_version"] = session.revised_plan.get("version", 2)
    elif session and session.active_plan:
        res["active_plan_title"] = session.active_plan.get("title")
        res["plan_version"] = 1
    return res

def read_opportunities(filters=None):
    """Tool: Retrieves open internship opportunities with vacancy counters."""
    opps = list_opportunities(status="PUBLISHED")
    results = []
    for o in opps:
        results.append({
            "id": o["id"],
            "company": o["company"],
            "title": o["title"],
            "domain": o["domain"],
            "min_cgpa": o["min_cgpa"],
            "max_backlogs": o["max_backlogs"],
            "total_vacancies": o["total_vacancies"],
            "available_vacancies": o["available_vacancies"],
            "duration": o["duration"],
            "location": o["location"],
            "deadline": o["deadline"]
        })
    return results

def compute_eligibility(student_usn, opp_id):
    """Tool: Pure deterministic calculation verifying CGPA and backlog thresholds."""
    return check_eligibility_and_vacancy(student_usn, opp_id)

def check_vacancy(opp_id):
    """Tool: Inspects remaining vacancies and capacity status for an opportunity."""
    opp = get_opportunity(opp_id)
    if not opp:
        return {"error": "Opportunity not found."}
    return {
        "opportunity_id": opp["id"],
        "company": opp["company"],
        "total_vacancies": opp["total_vacancies"],
        "filled_vacancies": opp["filled_vacancies"],
        "available_vacancies": opp["available_vacancies"],
        "is_full": opp["available_vacancies"] <= 0,
        "status": opp["status"]
    }

def read_application_submissions(student_usn):
    """Tool: Fetches versioned submission history for a student."""
    subs = get_submissions_by_student(student_usn)
    return [{
        "submission_id": s["id"],
        "version": s["submission_version"],
        "type": s["submission_type"],
        "status": s["status"],
        "coordinator_decision": s["coordinator_decision"],
        "rejection_reason": s["rejection_reason"],
        "approved_company": s["approved_company"],
        "submitted_at": s["submitted_at"]
    } for s in subs]

def read_application_status(submission_id):
    """Tool: Checks the real-time coordinator and HOD status of a specific submission."""
    sub = get_submission_by_id(submission_id)
    if not sub:
        return {"error": "Submission not found."}
    return {
        "submission_id": sub["id"],
        "student_usn": sub["student_usn"],
        "status": sub["status"],
        "coordinator_decision": sub["coordinator_decision"],
        "rejection_reason": sub["rejection_reason"],
        "hod_status": sub["hod_status"],
        "approved_company": sub["approved_company"]
    }

def read_internship_progress(student_usn):
    """Tool: Retrieves active 3-4 month internship status and progress journal logs."""
    internships = get_internships(student_usn=student_usn)
    if not internships:
        return {"status": "NO_ACTIVE_INTERNSHIP", "message": "Student does not have an active internship yet."}
    
    intern = internships[0]
    reports = get_progress_reports(intern["id"])
    return {
        "internship_id": intern["id"],
        "company": intern["company"],
        "role": intern["role"],
        "status": intern["status"],
        "duration": intern["duration"],
        "start_date": intern["start_date"],
        "mentor_name": intern["mentor_name"],
        "reports_submitted": len(reports),
        "latest_report": reports[-1] if reports else None
    }


# ---- Dispatcher & Trace Execution Engine ----

TOOL_REGISTRY = {
    "read_student_profile": read_student_profile,
    "read_opportunities": read_opportunities,
    "compute_eligibility": compute_eligibility,
    "check_vacancy": check_vacancy,
    "read_application_submissions": read_application_submissions,
    "read_application_status": read_application_status,
    "read_internship_progress": read_internship_progress,
}

class Lab2ToolUsingAgent:
    def __init__(self):
        self.trace = []

    def execute_query(self, student_usn, query_type="CHECK_ELIGIBILITY", target_company="ABC Technologies"):
        """
        Executes query by strictly orchestrating tool calls.
        Generates visible trace records showing tool, arguments, duration, and output.
        """
        self.trace = []
        t0 = time.time()

        # Step 1: Read student profile
        p_res = self._call_tool("read_student_profile", usn=student_usn)
        
        # Step 2: Read opportunities
        opps = self._call_tool("read_opportunities")

        # Find matching target company opportunity
        matched_opp = None
        for o in opps:
            if target_company.lower() in o["company"].lower():
                matched_opp = o
                break

        if not matched_opp and len(opps) > 0:
            matched_opp = opps[0]

        eligibility_res = None
        vacancy_res = None

        if matched_opp:
            # Step 3: Compute eligibility using pure calculator tool
            eligibility_res = self._call_tool("compute_eligibility", student_usn=student_usn, opp_id=matched_opp["id"])
            # Step 4: Check vacancies using tool
            vacancy_res = self._call_tool("check_vacancy", opp_id=matched_opp["id"])

        # Step 5: Read past submissions
        subs_res = self._call_tool("read_application_submissions", student_usn=student_usn)

        # Synthesize verified response grounded entirely in tool output
        student_name = p_res.get("name", "Student")
        cgpa = p_res.get("cgpa", 0.0)
        backlogs = p_res.get("backlogs", 0)

        if matched_opp and eligibility_res:
            is_eligible = eligibility_res.get("is_eligible", False)
            avail_vacancies = vacancy_res.get("available_vacancies", 0)
            comp_name = matched_opp["company"]
            req_cgpa = matched_opp["min_cgpa"]

            if is_eligible:
                answer = (
                    f"✓ {student_name} ({student_usn}) IS ELIGIBLE for {comp_name} ({matched_opp['title']}). "
                    f"Student CGPA of {cgpa} satisfies the minimum requirement of {req_cgpa}, with {backlogs} backlogs. "
                    f"There are currently {avail_vacancies} of {matched_opp['total_vacancies']} vacancies available."
                )
            else:
                answer = (
                    f"✗ {student_name} ({student_usn}) is NOT currently eligible for {comp_name}. "
                    f"Reason: {eligibility_res.get('status_explanation', 'Criteria mismatch')}. "
                    f"Current CGPA: {cgpa} (Required: {req_cgpa}), Backlogs: {backlogs}."
                )
        else:
            answer = f"Found profile for {student_name} with CGPA {cgpa}, but no matching opportunity found for '{target_company}'."

        total_time_ms = round((time.time() - t0) * 1000, 2)

        return {
            "status": "SUCCESS",
            "query_type": query_type,
            "student_usn": student_usn,
            "target_company": target_company,
            "answer": answer,
            "trace": self.trace,
            "total_execution_time_ms": total_time_ms,
            "tools_called_count": len(self.trace)
        }

    def _call_tool(self, tool_name, **kwargs):
        fn = TOOL_REGISTRY.get(tool_name)
        if not fn:
            raise ValueError(f"Unknown tool: {tool_name}")

        start = time.time()
        result = fn(**kwargs)
        elapsed_ms = round((time.time() - start) * 1000, 2)

        self.trace.append({
            "tool": tool_name,
            "input": kwargs,
            "output": result,
            "duration_ms": elapsed_ms
        })
        return result
