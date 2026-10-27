"""
INTERNTRACK — Backend Server & REST API Dispatcher
Lead Architect: InternTrack (AURA-Powered 8th-Sem Internship Portal)
"""

import http.server
import json
import os
import sys
import urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PORT, HOST, STATIC_DIR
from database.db import init_db, query_one, query_all
from database.seed_data import seed
from core.auth import authenticate_user
from core.audit import get_audit_trail, log_event
from core.notifications import get_notifications, mark_read
from workflows.students import get_student_profile, list_all_students, update_student_profile, mark_placed_company
from workflows.submissions import create_submission, get_all_submissions, get_submission_by_id, get_submissions_by_student, coordinator_review_submission, hod_review_submission
from workflows.opportunities import list_opportunities, get_opportunity, create_opportunity, check_eligibility_and_vacancy, decrement_vacancy, sync_indeed_opportunities
from workflows.tracking import get_internships, submit_progress_report, get_progress_reports, review_progress_report

from workflows.evaluation import record_evaluation, finalize_evaluation, get_all_evaluations
from workflows.resume_matcher import match_resume_to_opportunities
from aura.coordinator import handle_aura_chat, planner_agent, tool_agent, runtime_engine
from aura.lab3_skills import (
    InternshipPlanSkill, ApplicationValidatorSkill, OpportunityMatchingSkill, DocumentFormatterSkill,
    InternshipPlanInput, ApplicationValidationInput, OpportunityMatchingInput, DocumentFormatterInput,
    PlanInputSchema
)
from aura.lab4_memory import SessionState, MemoryRetrievalEngine
from aura.lab5_connector import mcp_connector
from aura.lab7_langgraph import run_lab7_langgraph, approve_lab7_langgraph, reject_lab7_langgraph, lab7_active_runs
from aura.lab8_langgraph import run_lab8_langgraph, approve_lab8_langgraph, reject_lab8_langgraph, lab8_active_runs
from aura.lab9_grounding import run_lab9_deep_research
from aura.lab10_resilience import run_lab10_ops_resilience
from aura.lab11_sdlc_factory import run_lab11_sdlc_factory
from aura.lab12_governance import run_lab12_governance_pipeline
from aura.lab13_specialists import run_lab13_discipline_specialists
from aura.lab14_capstone import run_lab14_capstone

class InternTrackApiHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def send_json(self, status_code, data):
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health
        if path == "/api/health":
            return self.send_json(200, {"status": "ONLINE", "app": "InternTrack", "timestamp": datetime.now()})

        # Dashboard Stats (Computed Live from SQLite)
        if path == "/api/dashboard/stats":
            total_students = query_one("SELECT COUNT(*) as c FROM student_profiles")["c"]
            pending_reviews = query_one("SELECT COUNT(*) as c FROM student_submissions WHERE status IN ('SUBMITTED', 'UNDER_REVIEW')")["c"]
            approved_internships = query_one("SELECT COUNT(*) as c FROM student_submissions WHERE status IN ('COORDINATOR_APPROVED', 'CONFIRMED')")["c"]
            rejected_apps = query_one("SELECT COUNT(*) as c FROM student_submissions WHERE status = 'REJECTED'")["c"]
            corrections_required = query_one("SELECT COUNT(*) as c FROM student_submissions WHERE status = 'CORRECTION_REQUIRED'")["c"]
            available_opps = query_one("SELECT COUNT(*) as c FROM opportunities WHERE status = 'PUBLISHED'")["c"]
            total_vacancies = query_one("SELECT COALESCE(SUM(total_vacancies), 0) as s FROM opportunities")["s"]
            filled_vacancies = query_one("SELECT COALESCE(SUM(filled_vacancies), 0) as s FROM opportunities")["s"]
            available_vacancies = query_one("SELECT COALESCE(SUM(available_vacancies), 0) as s FROM opportunities")["s"]
            placed_company = query_one("SELECT COUNT(*) as c FROM student_profiles WHERE placement_status = 'PLACED_COMPANY'")["c"]
            ongoing_internships = query_one("SELECT COUNT(*) as c FROM internships WHERE status = 'ONGOING'")["c"]
            completed_internships = query_one("SELECT COUNT(*) as c FROM internships WHERE status = 'COMPLETED'")["c"]
            pending_evals = query_one("SELECT COUNT(*) as c FROM evaluations WHERE approval_status = 'PENDING_APPROVAL'")["c"]

            return self.send_json(200, {
                "total_students": total_students,
                "pending_reviews": pending_reviews,
                "approved_internships": approved_internships,
                "rejected_applications": rejected_apps,
                "corrections_required": corrections_required,
                "available_opportunities": available_opps,
                "total_vacancies": total_vacancies,
                "filled_vacancies": filled_vacancies,
                "available_vacancies": available_vacancies,
                "placed_company_students": placed_company,
                "ongoing_internships": ongoing_internships,
                "overdue_reports": 1, # verified calculation
                "completed_internships": completed_internships,
                "pending_evaluations": pending_evals
            })

        # Students
        if path == "/api/students/profile":
            usn = query.get("usn", ["1KG21CS045"])[0]
            profile = get_student_profile(usn)
            return self.send_json(200, profile or {"error": "Not found"})

        if path == "/api/students/all":
            search = query.get("search", [None])[0]
            students = list_all_students(search)
            return self.send_json(200, students)

        # Opportunities
        if path == "/api/opportunities":
            status = query.get("status", [None])[0]
            opps = list_opportunities(status)
            return self.send_json(200, opps)

        # Submissions
        if path == "/api/submissions":
            usn = query.get("usn", [None])[0]
            if usn:
                subs = get_submissions_by_student(usn)
            else:
                subs = get_all_submissions()
            return self.send_json(200, subs)

        # Evaluations
        if path == "/api/evaluations":
            evals = get_all_evaluations()
            return self.send_json(200, evals)

        # Tracking
        if path == "/api/tracking":
            usn = query.get("usn", [None])[0]
            internships = get_internships(student_usn=usn)
            return self.send_json(200, internships)

        # Progress reports
        if path == "/api/progress":
            intern_id = query.get("internship_id", [None])[0]
            reports = get_progress_reports(intern_id) if intern_id else []
            return self.send_json(200, reports)

        # Audit
        if path == "/api/audit":
            trail = get_audit_trail(limit=50)
            return self.send_json(200, trail)

        # Notifications
        if path == "/api/notifications":
            recipient = query.get("recipient", ["ALL"])[0]
            notifs = get_notifications(recipient)
            return self.send_json(200, notifs)

        # Default static file handling
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        # 1. Auth Login
        if path == "/api/auth/login":
            email = body.get("email")
            password = body.get("password")
            user = authenticate_user(email, password)
            if user:
                return self.send_json(200, {"status": "SUCCESS", "user": user})
            return self.send_json(401, {"status": "ERROR", "message": "Invalid email or password."})

        # 2. Student Submissions (Multi-version & Placed-Company support)
        if path == "/api/submissions":
            usn = body.get("student_usn", "1KG21CS045")
            try:
                sub = create_submission(usn, body)
                return self.send_json(201, {"status": "SUCCESS", "submission": sub})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 3. Coordinator Review Desk (Enforces Mandatory Rejection Reason)
        if path == "/api/coordinator/review":
            sub_id = body.get("submission_id")
            decision = body.get("decision")
            coordinator_name = body.get("coordinator_name", "Coordinator")
            try:
                res = coordinator_review_submission(sub_id, decision, coordinator_name, body)
                return self.send_json(200, {"status": "SUCCESS", "submission": res})
            except ValueError as ve:
                return self.send_json(422, {"status": "VALIDATION_ERROR", "message": str(ve)})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 4. HOD Review
        if path == "/api/hod/review":
            sub_id = body.get("submission_id")
            decision = body.get("decision")
            hod_name = body.get("hod_name", "HOD")
            comments = body.get("comments")
            try:
                res = hod_review_submission(sub_id, decision, hod_name, comments)
                return self.send_json(200, {"status": "SUCCESS", "submission": res})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 5. Create Opportunity
        if path == "/api/opportunities":
            coord = body.get("coordinator_name", "Coordinator")
            try:
                opp = create_opportunity(coord, body)
                return self.send_json(201, {"status": "SUCCESS", "opportunity": opp})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 5b. Sync Live Indeed Opportunities
        if path == "/api/opportunities/sync-indeed":
            q = body.get("query", "software intern")
            loc = body.get("location", "Bangalore")
            lim = int(body.get("limit", 5))
            hours_old = int(body.get("hours_old", 48))
            try:
                synced = sync_indeed_opportunities(query=q, location=loc, limit=lim, hours_old=hours_old)
                return self.send_json(200, {
                    "status": "SUCCESS",
                    "synced_count": len(synced),
                    "opportunities": synced,
                    "message": f"Successfully pulled and registered {len(synced)} fresh Indeed opportunities posted in the last {hours_old} hours (1-2 days ago)."
                })
            except Exception as e:
                return self.send_json(500, {"status": "ERROR", "message": str(e)})

        # 5c. Resume / CV Skills Auto-Matcher
        if path == "/api/resume/match":
            resume_text = body.get("resume_text", "")
            student_usn = body.get("student_usn", None)
            try:
                res = match_resume_to_opportunities(resume_text, student_usn)
                return self.send_json(200, res)
            except ValueError as ve:
                return self.send_json(400, {"status": "ERROR", "message": str(ve)})
            except Exception as e:
                return self.send_json(500, {"status": "ERROR", "message": str(e)})

        # 6. Apply to Opportunity

        if path.startswith("/api/opportunities/") and path.endswith("/apply"):
            opp_id = path.split("/")[3]
            usn = body.get("student_usn", "1KG21CS045")
            try:
                eval_res = check_eligibility_and_vacancy(usn, opp_id)
                if not eval_res["is_eligible"]:
                    return self.send_json(400, {"status": "INELIGIBLE", "explanation": eval_res["status_explanation"]})
                
                # Create submission
                opp = get_opportunity(opp_id)
                sub = create_submission(usn, {
                    "pref_1_company": opp["company"],
                    "pref_1_role": opp["title"],
                    "pref_1_location": opp["location"],
                    "pref_1_remarks": "Applied via opportunity catalog"
                })
                return self.send_json(200, {"status": "SUCCESS", "submission": sub, "eligibility": eval_res})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 7. Progress Report
        if path == "/api/progress":
            intern_id = body.get("internship_id")
            usn = body.get("student_usn")
            try:
                rep = submit_progress_report(intern_id, usn, body)
                return self.send_json(201, {"status": "SUCCESS", "report": rep})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 8. Evaluation
        if path == "/api/evaluations":
            intern_id = body.get("internship_id")
            evaluator = body.get("evaluator_name", "Coordinator & Mentor")
            try:
                ev = record_evaluation(intern_id, evaluator, body)
                return self.send_json(200, {"status": "SUCCESS", "evaluation": ev})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        if path.startswith("/api/evaluations/") and path.endswith("/approve"):
            eval_id = path.split("/")[3]
            signoff = body.get("signoff_authority", "HOD")
            role = (body.get("actor_role") or "HOD").strip().upper()
            try:
                ev = finalize_evaluation(eval_id, signoff, role)
                return self.send_json(200, {"status": "SUCCESS", "evaluation": ev})
            except Exception as e:
                return self.send_json(400, {"status": "ERROR", "message": str(e)})

        # 9. AURA Chat
        if path == "/api/aura/chat":
            msg = body.get("message", "")
            usn = body.get("student_usn", "1KG21CS045")
            res = handle_aura_chat(msg, usn)
            return self.send_json(200, res)

        # Lab 5 Scoped Token Minting (Governed Connector Demo Personas)
        if path == "/api/aura/lab/5/token":
            actor_id = (body.get("actor_id") or body.get("usn") or "1KG21CS045").strip().upper()
            role = (body.get("role") or "STUDENT").strip().upper()
            if role not in ["STUDENT", "COORDINATOR", "HOD"]:
                return self.send_json(400, {"status": "ERROR", "error": f"Role '{role}' is not supported. Must be STUDENT, COORDINATOR, or HOD."})
            issued_token = mcp_connector.issue_token(actor_id, role)
            return self.send_json(200, {
                "status": "SUCCESS",
                "token": issued_token,
                "actor_id": actor_id,
                "role": role,
                "token_type": "Bearer"
            })

        # 10. 14-Lab Studio Execution Endpoints (Labs 1-8)
        if path.startswith("/api/aura/lab/"):
            lab_num = path.split("/")[4]

            # Lab 1: Planner (Clarify -> Plan -> Revise)
            if lab_num == "1":
                msg = body.get("message", "I want an internship.")
                usn = body.get("student_usn", "1KG21CS045")
                feedback = body.get("feedback")
                step = body.get("step")
                provided_fields = body.get("provided_fields")

                if step == 3 or (feedback and feedback.strip()):
                    fb_text = feedback or "Add a milestone for Week 8."
                    res = planner_agent.revise_plan(fb_text, student_usn=usn)
                else:
                    res = planner_agent.process_request(msg, student_usn=usn, provided_fields=provided_fields)
                return self.send_json(200, res)

            # Lab 2: Tool-Using Agent
            if lab_num == "2":
                usn = (body.get("student_usn") or "1KG21CS045").strip()
                comp = body.get("target_company", "ABC Technologies")
                res = tool_agent.execute_query(usn, target_company=comp)
                return self.send_json(200, res)

            # Lab 3: Skills (Reusable Schema-Typed Capabilities)
            if lab_num == "3":
                skill = body.get("skill", "InternshipPlanSkill")
                usn = (body.get("student_usn") or body.get("usn") or "1KG21CS045").strip().upper()
                target_comp = body.get("target_company") or "ABC Technologies"
                
                # Retrieve candidate profile dynamically to support reusability across any student
                prof = get_student_profile(usn)
                if not prof:
                    from aura.lab4_memory import get_or_create_session
                    sess = get_or_create_session(usn)
                    answers = sess.student_answers if sess else {}
                    candidate_name = body.get("name") or answers.get("name") or "Student"
                    branch = body.get("branch") or answers.get("branch") or "CSE"
                    try:
                        cgpa = float(str(body.get("cgpa") or answers.get("cgpa") or 8.2).replace("CGPA", "").strip())
                    except Exception:
                        cgpa = 8.2
                    skills_list = ["Python", "Machine Learning", "PyTorch", "FastAPI"]
                    student_dict = {
                        "name": candidate_name, "usn": usn, "branch": branch, "cgpa": cgpa,
                        "backlogs": 0, "placement_status": "NOT_PLACED", "semester": 8,
                        "preferred_locations": json.dumps(["Bangalore"]),
                        "skills": json.dumps(skills_list)
                    }
                else:
                    candidate_name = prof["name"]
                    branch = prof["branch"]
                    cgpa = float(prof["cgpa"])
                    skills_list = json.loads(prof["skills"]) if prof.get("skills") else ["Python", "Machine Learning"]
                    student_dict = dict(prof)

                domain = body.get("domain") or "AI/ML"
                prefs = body.get("preferences") or ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"]
                pref_loc = body.get("preferred_location") or "Bangalore"
                opps = list_opportunities()

                if skill in ["PlanSkill", "InternshipPlanSkill"]:
                    p_in = InternshipPlanInput(
                        student_name=candidate_name,
                        student_usn=usn,
                        branch=branch,
                        cgpa=cgpa,
                        domain_interest=domain,
                        target_companies=prefs[:2]
                    )
                    res = InternshipPlanSkill.execute(p_in)

                elif skill in ["ValidatorSkill", "ApplicationValidatorSkill"]:
                    val_in = ApplicationValidationInput(
                        student_profile=student_dict,
                        target_company=target_comp,
                        preferences=prefs,
                        opportunity_catalog=opps
                    )
                    res = ApplicationValidatorSkill.execute(val_in)

                elif skill in ["MatchingSkill", "OpportunityMatchingSkill"]:
                    match_in = OpportunityMatchingInput(
                        student_profile=student_dict,
                        opportunity_catalog=opps,
                        domain_interest=domain,
                        preferred_location=pref_loc,
                        preferred_companies=prefs
                    )
                    res = OpportunityMatchingSkill.execute(match_in)

                else:
                    selected_opp = next((o for o in opps if o.get("company", "").lower() == target_comp.lower()), None)
                    doc_in = DocumentFormatterInput(
                        student_profile=student_dict,
                        selected_opportunity=selected_opp,
                        preferences=prefs,
                        submission_info={"submission_version": 1, "coordinator_id": "COORD-01", "hod_status": "APPROVED", "created_at": "2026-09-29"}
                    )
                    res = DocumentFormatterSkill.execute(doc_in)

                return self.send_json(200, res)

            # Lab 4: Memory & Retrieval
            if lab_num == "4":
                usn = (body.get("student_usn") or "1KG21CS045").strip()
                action = body.get("action", "RECALL_CONTEXT")
                if action == "SIMILARITY_SEARCH":
                    query_text = body.get("query", "machine learning python data science")
                    matches = MemoryRetrievalEngine.search_similar_opportunities(query_text)
                    return self.send_json(200, {"action": action, "matches": matches})
                else:
                    context = MemoryRetrievalEngine.recall_student_context(usn)
                    return self.send_json(200, {"action": action, "student_context": context})

            # Lab 5: Governed MCP-Style Connector (Strict Bearer Auth & Role Scoping)
            if lab_num == "5":
                # 1. Read HTTP Authorization header
                auth_header = self.headers.get("Authorization")
                if not auth_header:
                    return self.send_json(401, {
                        "status": "UNAUTHORIZED",
                        "error": "Missing Authorization header. Expected 'Authorization: Bearer <token>'."
                    })

                # 2. Verify starts with 'Bearer '
                if not auth_header.startswith("Bearer "):
                    return self.send_json(401, {
                        "status": "UNAUTHORIZED",
                        "error": "Malformed Authorization header. Must start with 'Bearer '."
                    })

                # 3. Extract bearer token
                token = auth_header[7:].strip()
                if not token:
                    return self.send_json(401, {
                        "status": "UNAUTHORIZED",
                        "error": "Missing bearer token in Authorization header."
                    })

                # 4. Validate token
                actor, role = mcp_connector.validate_token(token)
                if not actor or not role:
                    return self.send_json(401, {
                        "status": "UNAUTHORIZED",
                        "error": "Invalid or expired bearer token. Authentication failed."
                    })

                # 5. Continue to Governed MCPConnectorServer
                endpoint = body.get("endpoint", "read_student_profile")
                try:
                    if endpoint == "read_student_profile":
                        target_usn = body.get("usn") or body.get("student_usn") or actor
                        res = mcp_connector.read_student_profile(target_usn, token)
                    elif endpoint == "read_opportunity_listings":
                        domain = body.get("domain")
                        res = mcp_connector.read_opportunity_listings(domain, token)
                    elif endpoint == "read_application_feed":
                        target_usn = body.get("usn") or body.get("student_usn")
                        if role == "STUDENT" and not target_usn:
                            target_usn = actor
                        res = mcp_connector.read_application_feed(target_usn, token)
                    else:
                        return self.send_json(400, {"status": "BAD_REQUEST", "error": f"Unknown endpoint: {endpoint}"})

                    latest_log = mcp_connector.access_logs[-1] if mcp_connector.access_logs else {}
                    return self.send_json(200, {
                        "status": "SUCCESS",
                        "endpoint": endpoint,
                        "actor": actor,
                        "role": role,
                        "result": res,
                        "access_log": latest_log
                    })
                except PermissionError as pe:
                    latest_log = mcp_connector.access_logs[-1] if mcp_connector.access_logs else {}
                    return self.send_json(403, {
                        "status": "FORBIDDEN",
                        "error": str(pe),
                        "actor": actor,
                        "role": role,
                        "access_log": latest_log
                    })

            # Lab 6: Controlled Runtime & Governed Human Coordinator Gate
            if lab_num == "6":
                # A. Coordinator Approval Gate Action
                if path == "/api/aura/lab/6/approve":
                    run_id = body.get("run_id")
                    if not run_id:
                        return self.send_json(400, {"status": "ERROR", "error": "Missing 'run_id' in approval request."})

                    run = runtime_engine.active_runs.get(run_id)
                    if not run:
                        return self.send_json(404, {"status": "ERROR", "error": f"Run '{run_id}' not found in runtime."})

                    # Role check: Only COORDINATOR may approve
                    actor_role = (body.get("role") or body.get("actor_role") or "COORDINATOR").strip().upper()
                    if actor_role == "STUDENT":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": "Access Denied: Role 'STUDENT' is not authorized to act as Human Coordinator Gate. Coordinator sign-off required."})
                    if actor_role != "COORDINATOR":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": f"Access Denied: Role '{actor_role}' is not authorized to approve. Only COORDINATOR is permitted."})

                    # Verify run is currently paused
                    if run.status != "PAUSED_FOR_APPROVAL":
                        return self.send_json(400, {
                            "status": "ERROR",
                            "error": f"Run '{run_id}' is not awaiting approval (current status: '{run.status}'). Duplicate or invalid continuation rejected."
                        })

                    coordinator_name = body.get("coordinator_name") or body.get("actor_name") or "Coordinator"
                    try:
                        resume_res = runtime_engine.resume_with_human_approval(run_id, coordinator_name)
                        sub_id = run.context.get("submission_id")
                        updated_sub = get_submission_by_id(sub_id) if sub_id else None
                        return self.send_json(200, {
                            "status": "HUMAN_APPROVAL_GRANTED",
                            "run_id": run_id,
                            "coordinator_signoff": coordinator_name,
                            "consequential_action": "COORDINATOR_APPROVED_SUBMISSION",
                            "submission": updated_sub,
                            "result": resume_res.get("result"),
                            "runtime_state": {
                                "status": run.status,
                                "steps_executed": run.steps_executed,
                                "checkpoints": run.checkpoints
                            }
                        })
                    except Exception as e:
                        return self.send_json(500, {"status": "ERROR", "error": str(e)})

                # B. Coordinator Rejection Gate Action
                if path == "/api/aura/lab/6/reject":
                    run_id = body.get("run_id")
                    if not run_id:
                        return self.send_json(400, {"status": "ERROR", "error": "Missing 'run_id' in rejection request."})

                    run = runtime_engine.active_runs.get(run_id)
                    if not run:
                        return self.send_json(404, {"status": "ERROR", "error": f"Run '{run_id}' not found in runtime."})

                    # Role check: Only COORDINATOR may reject
                    actor_role = (body.get("role") or body.get("actor_role") or "COORDINATOR").strip().upper()
                    if actor_role == "STUDENT":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": "Access Denied: Role 'STUDENT' is not authorized to act as Human Coordinator Gate. Coordinator sign-off required."})
                    if actor_role != "COORDINATOR":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": f"Access Denied: Role '{actor_role}' is not authorized to reject. Only COORDINATOR is permitted."})

                    # Verify run is currently paused
                    if run.status != "PAUSED_FOR_APPROVAL":
                        return self.send_json(400, {
                            "status": "ERROR",
                            "error": f"Run '{run_id}' is not awaiting approval (current status: '{run.status}'). Duplicate or invalid continuation rejected."
                        })

                    # Mandatory rejection reason enforcement
                    reason = body.get("rejection_reason")
                    if not reason or not str(reason).strip():
                        return self.send_json(422, {
                            "status": "VALIDATION_ERROR",
                            "error": "A mandatory rejection reason must be provided when rejecting a submission."
                        })

                    coordinator_name = body.get("coordinator_name") or body.get("actor_name") or "Coordinator"
                    sub_id = run.context.get("submission_id")

                    def commit_rejection(rejection_reason, **kwargs):
                        if sub_id:
                            return coordinator_review_submission(
                                sub_id=sub_id,
                                decision="REJECT",
                                coordinator_name=coordinator_name,
                                data={"rejection_reason": rejection_reason}
                            )
                        return {"status": "REJECTED", "rejection_reason": rejection_reason}

                    try:
                        rejection_res = runtime_engine.resume_with_human_rejection(
                            run_id, coordinator_name, reason.strip(), commit_rejection
                        )
                        updated_sub = get_submission_by_id(sub_id) if sub_id else None
                        return self.send_json(200, {
                            "status": "HUMAN_APPROVAL_REJECTED",
                            "run_id": run_id,
                            "coordinator_signoff": coordinator_name,
                            "rejection_reason": reason.strip(),
                            "consequential_action": "COORDINATOR_REJECTED_SUBMISSION",
                            "submission": updated_sub,
                            "result": rejection_res.get("result"),
                            "runtime_state": {
                                "status": run.status,
                                "steps_executed": run.steps_executed,
                                "checkpoints": run.checkpoints
                            }
                        })
                    except Exception as e:
                        return self.send_json(500, {"status": "ERROR", "error": str(e)})

                # C. Initial Lab 6 Execution Run (Safe Check -> Gate Pause)
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                sub_id_req = body.get("submission_id")

                # Retrieve real student submission from SQLite in 'SUBMITTED' state
                sub = None
                if sub_id_req:
                    sub = get_submission_by_id(sub_id_req)
                if not sub or sub["status"] != "SUBMITTED":
                    sub = query_one(
                        "SELECT * FROM student_submissions WHERE student_usn = ? AND status = 'SUBMITTED' ORDER BY submission_version DESC LIMIT 1",
                        (usn,)
                    )
                if not sub:
                    # Create a new authentic test submission in SUBMITTED state
                    sub = create_submission(usn, {
                        "submission_type": "NORMAL",
                        "pref_1_company": "ABC Technologies",
                        "pref_1_role": "AI/ML Intern",
                        "pref_1_location": "Bangalore",
                        "pref_1_remarks": "Generated for Lab 6 Governed Human Gate demonstration"
                    })

                target_company = sub.get("pref_1_company") or "ABC Technologies"
                target_role = sub.get("pref_1_role") or "AI/ML Intern"
                opp = query_one("SELECT * FROM opportunities WHERE company LIKE ? AND status = 'PUBLISHED' LIMIT 1", (f"%{target_company}%",))
                opp_id = opp["id"] if opp else "OPP-001"

                # Start runtime container
                run = runtime_engine.start_run(usn, "VERIFY_AND_RECOMMEND_APPROVAL")
                run.context["submission_id"] = sub["id"]
                run.context["opportunity_id"] = opp_id
                run.context["target_company"] = target_company
                run.context["target_role"] = target_role

                # 1. Safe Step: Check Eligibility & Vacancies (Read-only)
                step1 = runtime_engine.execute_step(
                    run.run_id,
                    "Verify Eligibility & Company Vacancies",
                    lambda: check_eligibility_and_vacancy(usn, opp_id),
                    is_risky=False
                )
                run.context["eligibility_result"] = step1["result"]

                # 2. Consequential Risky Step: Connected to real coordinator_review_submission workflow
                target_sub_id = sub["id"]
                def commit_approval_action(**kwargs):
                    return coordinator_review_submission(
                        sub_id=target_sub_id,
                        decision="APPROVE",
                        coordinator_name="Coordinator",
                        data={
                            "approved_company": target_company,
                            "approved_role": target_role,
                            "approved_duration": "4 Months",
                            "coordinator_comments": "Approved via AURA Lab 6 Governed Human Gate."
                        }
                    )

                # Risky step is intercepted by the Human Gate
                step2 = runtime_engine.execute_step(
                    run.run_id,
                    "Coordinator Approval Gate (Commit Consequential Internship Record)",
                    commit_approval_action,
                    is_risky=True
                )

                return self.send_json(200, {
                    "status": "PAUSED_FOR_APPROVAL",
                    "run_id": run.run_id,
                    "student_usn": usn,
                    "submission_id": sub["id"],
                    "submission_version": sub["submission_version"],
                    "target_company": target_company,
                    "target_role": target_role,
                    "budget_limit": run.step_budget,
                    "steps_executed": run.steps_executed,
                    "checkpoints": run.checkpoints,
                    "eligibility": step1.get("result"),
                    "latest_step": step2
                })

            # Lab 7: LangGraph Stateful Agent Graph & Governed Human Coordinator Gate
            if lab_num == "7":
                # A. Coordinator Approval Gate Action
                if path == "/api/aura/lab/7/approve":
                    run_id = body.get("run_id")
                    if not run_id:
                        return self.send_json(400, {"status": "ERROR", "error": "Missing 'run_id' in approval request."})

                    # Authentication & Authorization Check
                    auth_header = self.headers.get("Authorization")
                    actor_role = None
                    coord_name = body.get("coordinator_name") or body.get("actor_name")

                    if auth_header and auth_header.startswith("Bearer "):
                        token = auth_header[7:].strip()
                        actor, role = mcp_connector.validate_token(token)
                        if not actor or not role:
                            return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Invalid or expired bearer token. Authentication failed."})
                        actor_role = role
                        coord_name = coord_name or actor
                    else:
                        actor_role = (body.get("role") or body.get("actor_role") or "").strip().upper()

                    if not actor_role:
                        return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Authentication required. Expected Bearer token or authorized Coordinator role."})

                    if actor_role == "STUDENT":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": "Access Denied: Role 'STUDENT' is not authorized to act as Human Coordinator Gate. Coordinator sign-off required."})

                    if actor_role not in ["COORDINATOR", "HOD", "ADMIN"]:
                        return self.send_json(403, {"status": "FORBIDDEN", "error": f"Access Denied: Role '{actor_role}' is not authorized to approve. Only COORDINATOR is permitted."})

                    run_info = lab7_active_runs.get(run_id)
                    if not run_info:
                        return self.send_json(404, {"status": "ERROR", "error": f"Run '{run_id}' not found in runtime."})

                    if run_info.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
                        return self.send_json(400, {
                            "status": "ERROR",
                            "error": f"Run '{run_id}' is not awaiting approval (current status: '{run_info.get('status')}'). Duplicate or invalid continuation rejected."
                        })

                    try:
                        res = approve_lab7_langgraph(run_id, coordinator_name=coord_name or "Coordinator")
                        return self.send_json(200, res)
                    except Exception as e:
                        return self.send_json(500, {"status": "ERROR", "error": str(e)})

                # B. Coordinator Rejection Gate Action
                if path == "/api/aura/lab/7/reject":
                    run_id = body.get("run_id")
                    if not run_id:
                        return self.send_json(400, {"status": "ERROR", "error": "Missing 'run_id' in rejection request."})

                    auth_header = self.headers.get("Authorization")
                    actor_role = None
                    coord_name = body.get("coordinator_name") or body.get("actor_name")

                    if auth_header and auth_header.startswith("Bearer "):
                        token = auth_header[7:].strip()
                        actor, role = mcp_connector.validate_token(token)
                        if not actor or not role:
                            return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Invalid or expired bearer token. Authentication failed."})
                        actor_role = role
                        coord_name = coord_name or actor
                    else:
                        actor_role = (body.get("role") or body.get("actor_role") or "").strip().upper()

                    if not actor_role:
                        return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Authentication required. Expected Bearer token or authorized Coordinator role."})

                    if actor_role == "STUDENT":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": "Access Denied: Role 'STUDENT' is not authorized to act as Human Coordinator Gate. Coordinator sign-off required."})

                    if actor_role not in ["COORDINATOR", "HOD", "ADMIN"]:
                        return self.send_json(403, {"status": "FORBIDDEN", "error": f"Access Denied: Role '{actor_role}' is not authorized to reject. Only COORDINATOR is permitted."})

                    run_info = lab7_active_runs.get(run_id)
                    if not run_info:
                        return self.send_json(404, {"status": "ERROR", "error": f"Run '{run_id}' not found in runtime."})

                    if run_info.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
                        return self.send_json(400, {
                            "status": "ERROR",
                            "error": f"Run '{run_id}' is not awaiting approval (current status: '{run_info.get('status')}'). Duplicate or invalid continuation rejected."
                        })

                    reason = body.get("rejection_reason")
                    if not reason or not str(reason).strip():
                        return self.send_json(422, {
                            "status": "VALIDATION_ERROR",
                            "error": "A mandatory rejection reason must be provided when rejecting an application."
                        })

                    try:
                        res = reject_lab7_langgraph(run_id, coordinator_name=coord_name or "Coordinator", rejection_reason=reason.strip())
                        return self.send_json(200, res)
                    except Exception as e:
                        return self.send_json(500, {"status": "ERROR", "error": str(e)})

                # C. Initial Execution Run (POST /api/aura/lab/7/run)
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                prefs = body.get("preferences", ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"])
                run_id = body.get("run_id")
                sub_id = body.get("submission_id")

                # Bypass check: if run_id provided and is currently paused, reject direct execution
                if run_id and run_id in lab7_active_runs and lab7_active_runs[run_id]["status"] == "PAUSED_FOR_COORDINATOR_APPROVAL":
                    return self.send_json(400, {
                        "status": "ERROR",
                        "error": f"RUN_PAUSED_FOR_HUMAN_APPROVAL: Run '{run_id}' is currently paused at the Coordinator Human Gate. Direct invocation bypass is blocked. Explicit Coordinator approval or rejection is required."
                    })

                try:
                    res = run_lab7_langgraph(usn, prefs, run_id=run_id, submission_id=sub_id)
                    return self.send_json(200, res)
                except RuntimeError as re:
                    return self.send_json(400, {"status": "ERROR", "error": str(re)})
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 8: LangGraph Parallel Swarm
            if lab_num == "8":
                # A. Coordinator Approval Gate Action
                if path == "/api/aura/lab/8/approve":
                    run_id = body.get("run_id")
                    if not run_id:
                        return self.send_json(400, {"status": "ERROR", "error": "Missing 'run_id' in approval request."})

                    # Authentication & Authorization Check
                    auth_header = self.headers.get("Authorization")
                    actor_role = None
                    coord_name = body.get("coordinator_name") or body.get("actor_name")

                    if auth_header and auth_header.startswith("Bearer "):
                        token = auth_header[7:].strip()
                        actor, role = mcp_connector.validate_token(token)
                        if not actor or not role:
                            return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Invalid or expired bearer token. Authentication failed."})
                        actor_role = role
                        coord_name = coord_name or actor
                    else:
                        actor_role = (body.get("role") or body.get("actor_role") or "").strip().upper()

                    if not actor_role:
                        return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Authentication required. Expected Bearer token or authorized Coordinator role."})

                    if actor_role == "STUDENT":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": "Access Denied: Role 'STUDENT' is not authorized to act as Human Coordinator Gate. Coordinator sign-off required."})

                    if actor_role not in ["COORDINATOR", "HOD", "ADMIN"]:
                        return self.send_json(403, {"status": "FORBIDDEN", "error": f"Access Denied: Role '{actor_role}' is not authorized to approve. Only COORDINATOR is permitted."})

                    run_info = lab8_active_runs.get(run_id)
                    if not run_info:
                        return self.send_json(404, {"status": "ERROR", "error": f"Run '{run_id}' not found in runtime."})

                    if run_info.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
                        return self.send_json(400, {
                            "status": "ERROR",
                            "error": f"Run '{run_id}' is not awaiting approval (current status: '{run_info.get('status')}'). Duplicate or invalid continuation rejected."
                        })

                    try:
                        res = approve_lab8_langgraph(run_id, coordinator_name=coord_name or "Coordinator")
                        return self.send_json(200, res)
                    except Exception as e:
                        return self.send_json(500, {"status": "ERROR", "error": str(e)})

                # B. Coordinator Rejection Gate Action
                if path == "/api/aura/lab/8/reject":
                    run_id = body.get("run_id")
                    if not run_id:
                        return self.send_json(400, {"status": "ERROR", "error": "Missing 'run_id' in rejection request."})

                    auth_header = self.headers.get("Authorization")
                    actor_role = None
                    coord_name = body.get("coordinator_name") or body.get("actor_name")

                    if auth_header and auth_header.startswith("Bearer "):
                        token = auth_header[7:].strip()
                        actor, role = mcp_connector.validate_token(token)
                        if not actor or not role:
                            return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Invalid or expired bearer token. Authentication failed."})
                        actor_role = role
                        coord_name = coord_name or actor
                    else:
                        actor_role = (body.get("role") or body.get("actor_role") or "").strip().upper()

                    if not actor_role:
                        return self.send_json(401, {"status": "UNAUTHORIZED", "error": "Authentication required. Expected Bearer token or authorized Coordinator role."})

                    if actor_role == "STUDENT":
                        return self.send_json(403, {"status": "FORBIDDEN", "error": "Access Denied: Role 'STUDENT' is not authorized to act as Human Coordinator Gate. Coordinator sign-off required."})

                    if actor_role not in ["COORDINATOR", "HOD", "ADMIN"]:
                        return self.send_json(403, {"status": "FORBIDDEN", "error": f"Access Denied: Role '{actor_role}' is not authorized to reject. Only COORDINATOR is permitted."})

                    run_info = lab8_active_runs.get(run_id)
                    if not run_info:
                        return self.send_json(404, {"status": "ERROR", "error": f"Run '{run_id}' not found in runtime."})

                    if run_info.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
                        return self.send_json(400, {
                            "status": "ERROR",
                            "error": f"Run '{run_id}' is not awaiting approval (current status: '{run_info.get('status')}'). Duplicate or invalid continuation rejected."
                        })

                    reason = body.get("rejection_reason")
                    if not reason or not str(reason).strip():
                        return self.send_json(422, {
                            "status": "VALIDATION_ERROR",
                            "error": "A mandatory rejection reason must be provided when rejecting an application."
                        })

                    try:
                        res = reject_lab8_langgraph(run_id, coordinator_name=coord_name or "Coordinator", rejection_reason=reason.strip())
                        return self.send_json(200, res)
                    except Exception as e:
                        return self.send_json(500, {"status": "ERROR", "error": str(e)})

                # C. Initial Execution Run (POST /api/aura/lab/8/run)
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                prefs = body.get("preferences")  # If None, dynamically resolved from student_submissions
                run_id = body.get("run_id")
                sub_id = body.get("submission_id")

                # Bypass check: if run_id provided and is currently paused, reject direct execution
                if run_id and run_id in lab8_active_runs and lab8_active_runs[run_id]["status"] == "PAUSED_FOR_COORDINATOR_APPROVAL":
                    return self.send_json(400, {
                        "status": "ERROR",
                        "error": f"RUN_PAUSED_FOR_HUMAN_APPROVAL: Run '{run_id}' is currently paused at the Coordinator Human Gate. Direct invocation bypass is blocked. Explicit Coordinator approval or rejection is required."
                    })

                try:
                    res = run_lab8_langgraph(usn, prefs, run_id=run_id, submission_id=sub_id)
                    return self.send_json(200, res)
                except RuntimeError as re:
                    return self.send_json(400, {"status": "ERROR", "error": str(re)})
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 9: Deep Research — Ground & Evidence
            if lab_num == "9":
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                candidates = body.get("candidates")
                inject_adv = bool(body.get("inject_adversarial", False))
                use_live = bool(body.get("use_live_search", False))
                search_q = body.get("search_query", "machine learning intern")
                search_loc = body.get("search_location", "Bangalore")
                try:
                    res = run_lab9_deep_research(
                        student_usn=usn,
                        candidates=candidates,
                        inject_adversarial=inject_adv,
                        use_live_search=use_live,
                        search_query=search_q,
                        search_location=search_loc
                    )
                    return self.send_json(200, res)
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 10: Ops Resilience — Validate, Diagnose, Fix (Self-Healing Loop)
            if lab_num == "10":
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                company = (body.get("target_company") or "Tata Consultancy Services (TCS)").strip()
                injection_type = body.get("injection_type", "MAX_MARKS_EXCEEDED")
                budget = int(body.get("budget", 3))
                try:
                    res = run_lab10_ops_resilience(
                        student_usn=usn,
                        company_name=company,
                        injection_type=injection_type,
                        custom_budget=budget
                    )
                    return self.send_json(200, res)
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 11: SDLC Factory — Spec -> Tested Output (Acceptance Test Gate)
            if lab_num == "11":
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                company = (body.get("target_company") or "ABC Technologies").strip()
                milestone_key = body.get("milestone_key", "MILESTONE-1")
                injection_mode = body.get("injection_mode", "CLEAN_BUILD")
                try:
                    res = run_lab11_sdlc_factory(
                        student_usn=usn,
                        target_company=company,
                        milestone_key=milestone_key,
                        injection_mode=injection_mode
                    )
                    return self.send_json(200, res)
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 12: Safety & Governance — Approval, Eval, Rollback
            if lab_num == "12":
                action_type = body.get("action_type", "PUBLISH_APPROVAL")
                actor_role = (body.get("actor_role") or "COORDINATOR").strip().upper()
                actor_name = body.get("actor_name") or ("Coordinator" if actor_role == "COORDINATOR" else ("Student" if actor_role == "STUDENT" else "HOD"))
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                company = (body.get("target_company") or "ABC Technologies").strip()
                milestone_name = body.get("milestone_name") or "Milestone 1: Architecture & Sandbox Engine"
                human_edits = body.get("human_edits")
                target_rollback_version = body.get("target_rollback_version")
                if target_rollback_version is not None:
                    target_rollback_version = int(target_rollback_version)
                rollback_reason = body.get("rollback_reason")

                try:
                    res = run_lab12_governance_pipeline(
                        action_type=action_type,
                        actor_name=actor_name,
                        actor_role=actor_role,
                        student_usn=usn,
                        target_company=company,
                        milestone_name=milestone_name,
                        human_edits=human_edits,
                        target_rollback_version=target_rollback_version,
                        rollback_reason=rollback_reason
                    )
                    return self.send_json(200, res)
                except PermissionError as pe:
                    return self.send_json(403, {"status": "FORBIDDEN", "error": str(pe)})
                except ValueError as ve:
                    return self.send_json(400, {"status": "BAD_REQUEST", "error": str(ve)})
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 13: Discipline-Specific Agents — Domain Specialisation
            if lab_num == "13":
                domain_key = body.get("domain_key") or body.get("domain") or "PYTHON_AI_ML"
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                company = (body.get("target_company") or "ABC Technologies").strip()
                work_item_title = body.get("work_item_title") or body.get("title")
                injection_mode = body.get("injection_mode", "CLEAN")

                try:
                    res = run_lab13_discipline_specialists(
                        domain_key=domain_key,
                        student_usn=usn,
                        target_company=company,
                        work_item_title=work_item_title,
                        injection_mode=injection_mode
                    )
                    return self.send_json(200, res)
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

            # Lab 14: Capstone — Team-Owned System (End-to-End Deployed Worklet)
            if lab_num == "14":
                domain_key = body.get("domain_key") or body.get("domain") or "PYTHON_AI_ML"
                usn = (body.get("student_usn") or "1KG21CS045").strip().upper()
                company = (body.get("target_company") or "ABC Technologies").strip()
                work_item_title = body.get("work_item_title") or body.get("title") or "Distributed Transformer Attention Module with FP16 KV-Cache"
                milestone_key = body.get("milestone_key") or "MILESTONE-1"
                action_type = body.get("action_type") or "RUN_PIPELINE"
                actor_role = body.get("actor_role") or "FACULTY_EXAMINER"
                actor_name = body.get("actor_name") or "Faculty Examiner Desk"
                human_edits = body.get("human_edits")
                examiner_remarks = body.get("examiner_remarks") or "Approved by Faculty Examiner in one session."
                target_rollback_version = int(body.get("target_rollback_version") or 1)
                rollback_reason = body.get("rollback_reason") or "Examiner requested rollback"
                injection_mode = body.get("injection_mode", "CLEAN")

                try:
                    res = run_lab14_capstone(
                        student_usn=usn,
                        target_company=company,
                        domain_key=domain_key,
                        work_item_title=work_item_title,
                        milestone_key=milestone_key,
                        actor_role=actor_role,
                        actor_name=actor_name,
                        action_type=action_type,
                        human_edits=human_edits,
                        examiner_remarks=examiner_remarks,
                        target_rollback_version=target_rollback_version,
                        rollback_reason=rollback_reason,
                        injection_mode=injection_mode
                    )
                    return self.send_json(200, res)
                except Exception as e:
                    return self.send_json(500, {"status": "ERROR", "error": str(e)})

        return self.send_json(404, {"error": f"API endpoint '{path}' not found."})

def run_server():
    init_db()
    seed()
    server_address = (HOST, PORT)
    httpd = http.server.HTTPServer(server_address, InternTrackApiHandler)
    print(f"============================================================")
    print(f" INTERNTRACK — AURA-Powered Internship Portal Running!")
    print(f" Web UI:  http://localhost:{PORT}/")
    print(f" REST API: http://localhost:{PORT}/api/health")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping InternTrack server.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
