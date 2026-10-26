"""
Lab 6 Human Gate Verification Script (Verification Test Only)
Tests:
1. Safe steps before gate
2. Runtime actually pauses at Human Gate
3. Consequential database action blocked before approval
4. Attempted bypass without approval
5. Explicit Coordinator approval required
6. Action commits only after approval
7. Rejection path
"""

import json
import urllib.request
import urllib.error
import sqlite3
import os
import sys

BASE_URL = "http://localhost:8000"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "interntrack.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_submission_state(sub_id="SUB-1KG21CS045-1"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, student_usn, status, coordinator_decision, coordinator_id, coordinator_timestamp FROM student_submissions WHERE id = ?", (sub_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_opportunity_state(opp_id="OPP-001"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, company, available_vacancies, filled_vacancies, status FROM opportunities WHERE id = ?", (opp_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_internships_count(usn="1KG21CS045"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM internships WHERE student_usn = ?", (usn,))
    row = c.fetchone()
    conn.close()
    return row["count"] if row else 0

def post_json(endpoint, payload):
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def main():
    print("=" * 60)
    print("LAB 6 COORDINATOR HUMAN GATE VERIFICATION SUITE")
    print("=" * 60)

    # Database Baseline Before Test
    initial_sub = get_submission_state("SUB-1KG21CS045-1")
    initial_opp = get_opportunity_state("OPP-001")
    initial_intern_count = get_internships_count("1KG21CS045")

    print(f"DATABASE BASELINE (Before Execution):")
    print(f"  Submission SUB-1KG21CS045-1 Status: {initial_sub['status']}, Decision: {initial_sub['coordinator_decision']}")
    print(f"  Opportunity OPP-001 Available Vacancies: {initial_opp['available_vacancies']}")
    print(f"  Internships Count for 1KG21CS045: {initial_intern_count}")
    print("-" * 60)

    # ---------------------------------------------------------
    # TEST 1: Execute Lab 6 via API & Verify Pause + DB Unchanged
    # ---------------------------------------------------------
    print("\n[TEST 1] Triggering Lab 6 Runtime via POST /api/aura/lab/6/run...")
    code, api_res = post_json("/api/aura/lab/6/run", {"student_usn": "1KG21CS045"})
    print(f"  HTTP Response Code: {code}")
    print(f"  Run ID: {api_res.get('run_id')}")
    print(f"  Steps Executed: {api_res.get('steps_executed')}")
    print(f"  Checkpoints: {[c['checkpoint_name'] for c in api_res.get('checkpoints', [])]}")
    latest_step = api_res.get("latest_step", {})
    print(f"  Latest Step Status: {latest_step.get('status')}")
    print(f"  Latest Step Message: {latest_step.get('message')}")

    test1_safe_steps = (api_res.get("steps_executed") == 1) # Step 1 completed, Step 2 paused
    test1_runtime_pauses = (latest_step.get("status") == "PAUSED_FOR_APPROVAL")

    # Check DB state immediately after Lab 6 execution
    sub_after_run = get_submission_state("SUB-1KG21CS045-1")
    opp_after_run = get_opportunity_state("OPP-001")
    intern_count_after_run = get_internships_count("1KG21CS045")

    db_unchanged = (
        sub_after_run["status"] == initial_sub["status"] and
        sub_after_run["coordinator_decision"] == initial_sub["coordinator_decision"] and
        opp_after_run["available_vacancies"] == initial_opp["available_vacancies"] and
        intern_count_after_run == initial_intern_count
    )

    print(f"  Database Status After Run:")
    print(f"    Submission Status: {sub_after_run['status']} (Unchanged: {sub_after_run['status'] == initial_sub['status']})")
    print(f"    Coordinator Decision: {sub_after_run['coordinator_decision']} (Unchanged: {sub_after_run['coordinator_decision'] == initial_sub['coordinator_decision']})")
    print(f"    Available Vacancies: {opp_after_run['available_vacancies']} (Unchanged: {opp_after_run['available_vacancies'] == initial_opp['available_vacancies']})")
    print(f"  Test 1 Result: Safe steps before gate = {test1_safe_steps}, Runtime pauses = {test1_runtime_pauses}, DB Unchanged = {db_unchanged}")

    # ---------------------------------------------------------
    # TEST 2: Attempt to Bypass Gate Without Approval
    # ---------------------------------------------------------
    print("\n[TEST 2] Attempting to Bypass Human Gate without Approval...")
    # Does an API endpoint exist to resume without approval or force commitment?
    # Test POST /api/aura/lab/6/run again or endpoints like /resume, /execute, etc.
    code_bypass1, res_bypass1 = post_json("/api/aura/lab/6/resume", {"run_id": api_res.get("run_id")})
    print(f"  POST /api/aura/lab/6/resume HTTP Code: {code_bypass1} (Expected 404 if no resume endpoint exists)")

    code_bypass2, res_bypass2 = post_json("/api/aura/lab/6/approve", {"run_id": api_res.get("run_id")})
    print(f"  POST /api/aura/lab/6/approve HTTP Code: {code_bypass2} (Expected 404 if no resume endpoint exists)")

    # Test direct runtime engine bypass in Python
    from aura.coordinator import runtime_engine
    run_id = api_res.get("run_id")
    state = runtime_engine.active_runs.get(run_id)
    bypass_blocked = False
    if state:
        print(f"  Internal Runtime Engine State for {run_id}: status={state.status}, pending_action={state.pending_approval_action}")
        try:
            # Attempt to execute consequential action without coordinator approval
            # calling execute_step again on risky step or resume without approval
            runtime_engine.resume_with_human_approval(run_id, coordinator_name="", action_fn=None)
        except Exception as e:
            bypass_blocked = True
            print(f"  Direct Bypass Blocked with Exception: {type(e).__name__}: {e}")

    sub_after_bypass = get_submission_state("SUB-1KG21CS045-1")
    print(f"  DB after bypass attempt: Submission Status = {sub_after_bypass['status']}")

    # ---------------------------------------------------------
    # TEST 3: Explicit Coordinator Approval Resumption
    # ---------------------------------------------------------
    print("\n[TEST 3] Testing Explicit Coordinator Approval...")
    # Does the HTTP API expose an endpoint for coordinator approval in Lab 6?
    # Or is resume_with_human_approval only in python ControlledAgentRuntime?
    has_http_resume_endpoint = (code_bypass1 != 404 or code_bypass2 != 404)
    print(f"  HTTP API Endpoint for Lab 6 Approval/Resumption exists: {has_http_resume_endpoint}")

    # Test Python ControlledAgentRuntime's resume_with_human_approval
    runtime_resumed = False
    consequential_committed = False
    if state and state.status == "PAUSED_FOR_APPROVAL":
        # Let's inspect what action_fn was stored in state.pending_approval_action
        print(f"  Pending action in state: {state.pending_approval_action}")
        
        # In server.py, step2 was:
        # runtime_engine.execute_step(run.run_id, "Recommend Approval", lambda: {"recommendation": "APPROVED"}, is_risky=True)
        # Note that the action_fn was a mock lambda!
        # What happens if coordinator approves via runtime_engine.resume_with_human_approval?
        try:
            resume_result = runtime_engine.resume_with_human_approval(
                run_id=run_id,
                coordinator_name="Dr. Ramesh Kulkarni (Coordinator)",
                action_fn=lambda: {"action": "COORDINATOR_SIGN_OFF", "status": "APPROVED"}
            )
            runtime_resumed = (resume_result.get("status") == "COMPLETED")
            print(f"  Python Runtime Resume Result: {resume_result}")
        except Exception as e:
            print(f"  Resume failed: {e}")

    # Check if the database was updated by the Lab 6 runtime resumption
    sub_after_resume = get_submission_state("SUB-1KG21CS045-1")
    print(f"  Database Submission Status After Lab 6 Runtime Resume: {sub_after_resume['status']}")
    print(f"  Coordinator Decision in DB: {sub_after_resume['coordinator_decision']}")
    
    # ---------------------------------------------------------
    # TEST 4: Rejection Path
    # ---------------------------------------------------------
    print("\n[TEST 4] Testing Rejection Path...")
    # Check if ControlledAgentRuntime has a reject method
    has_reject_method = hasattr(runtime_engine, "reject_with_human_approval") or hasattr(runtime_engine, "reject")
    print(f"  ControlledAgentRuntime has rejection method: {has_reject_method}")

    # Summary of findings
    print("\n" + "=" * 60)
    print("DETAILED VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"1. Safe steps before gate: {'PASS' if test1_safe_steps else 'FAIL'}")
    print(f"2. Runtime actually pauses at Human Gate: {'PASS' if test1_runtime_pauses else 'FAIL'}")
    print(f"3. Consequential database action blocked before approval: {'PASS' if db_unchanged else 'FAIL'}")
    print(f"4. Attempted bypass without approval: {'PASS' if bypass_blocked else 'FAIL'}")
    print(f"5. Explicit Coordinator approval required: {'PASS' if test1_runtime_pauses and bypass_blocked else 'FAIL'}")
    print(f"6. Action commits only after approval: {'PASS' if consequential_committed else 'PARTIAL / NOT CONNECTED TO DB'}")
    print(f"7. Rejection path: {'PASS' if has_reject_method else 'NOT IMPLEMENTED'}")
    print(f"8. HTTP API Exposes Interactive Gate Controls: {'PASS' if has_http_resume_endpoint else 'NOT EXPOSED (Only 1-shot pause returned)'}")

if __name__ == "__main__":
    main()
