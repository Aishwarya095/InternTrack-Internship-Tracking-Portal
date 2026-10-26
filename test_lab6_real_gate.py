"""
Comprehensive Acceptance Tests for Lab 6 Governed Human Coordinator Gate
Tests all 13 criteria:
1. Safe eligibility step -> PASS
2. Risky action -> PAUSED_FOR_APPROVAL
3. Database unchanged before approval
4. execute_step() bypass attempt while paused -> REJECTED
5. Student tries to approve -> 403
6. Invalid run -> rejected (404)
7. Coordinator approval -> accepted
8. Real database status changes only after approval
9. Coordinator rejection -> accepted
10. Rejection reason is persisted
11. Duplicate approval -> rejected
12. Audit events recorded
13. Existing Labs 1-5 remain passing
"""

import json
import urllib.request
import urllib.error
import sqlite3
import os
import sys

BASE_URL = "http://localhost:8000"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "interntrack.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def post_json(endpoint, payload, headers=None):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers
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

def get_token(actor_id, role):
    status, res = post_json("/api/aura/lab/5/token", {"actor_id": actor_id, "role": role})
    return res["token"]

def main():
    print("=" * 65)
    print("LAB 6 GOVERNED HUMAN COORDINATOR GATE ACCEPTANCE SUITE")
    print("=" * 65)

    test_usn = "1KG21CS045"

    # Step A: Create a clean submission in 'SUBMITTED' state for testing approval
    conn = get_db()
    c = conn.cursor()
    # Create test submission
    import uuid
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sub1_id = f"SUB-TEST-APPROVAL-{uuid.uuid4().hex[:6].upper()}"
    c.execute("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        pref_1_company, pref_1_role, pref_1_location, pref_1_remarks,
        status, coordinator_decision, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sub1_id, test_usn, 90, "NORMAL", "ABC Technologies", "AI/ML Intern", "Bangalore", "Lab 6 Test Approval", "SUBMITTED", None, now))
    conn.commit()
    conn.close()

    # 1. Safe eligibility step -> PASS
    # 2. Risky action -> PAUSED_FOR_APPROVAL
    print("\n[TEST 1 & 2] Initiating Lab 6 Execution Run...")
    code, run_res = post_json("/api/aura/lab/6/run", {
        "student_usn": test_usn,
        "submission_id": sub1_id
    })
    assert code == 200, f"Expected 200, got {code}: {run_res}"
    assert run_res.get("status") == "PAUSED_FOR_APPROVAL", f"Expected PAUSED_FOR_APPROVAL, got {run_res.get('status')}"
    run_id = run_res["run_id"]
    latest_step = run_res["latest_step"]
    assert latest_step["status"] == "PAUSED_FOR_APPROVAL"
    assert "Coordinator approval" in latest_step["message"]
    assert run_res.get("steps_executed") == 1
    elig = run_res.get("eligibility", {})
    assert elig.get("is_eligible") is True
    print(f"[PASS] Criteria 1: Safe eligibility step executed autonomously (Eligible={elig.get('is_eligible')})")
    print(f"[PASS] Criteria 2: Consequential step intercepted -> Status: PAUSED_FOR_APPROVAL (Run: {run_id})")

    # 3. Database unchanged before approval
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision FROM student_submissions WHERE id = ?", (sub1_id,))
    sub_before = dict(c.fetchone())
    conn.close()
    assert sub_before["status"] == "SUBMITTED", f"DB mutated prematurely! Status: {sub_before['status']}"
    assert sub_before["coordinator_decision"] is None
    print(f"[PASS] Criteria 3: Database UNCHANGED while paused (Status: {sub_before['status']}, Decision: {sub_before['coordinator_decision']})")

    # 4. execute_step() bypass attempt while paused -> REJECTED
    from aura.coordinator import runtime_engine
    local_run = runtime_engine.start_run(test_usn)
    runtime_engine.execute_step(local_run.run_id, "Risky Step", lambda: None, is_risky=True)
    bypass_caught = False
    try:
        runtime_engine.execute_step(local_run.run_id, "Bypass Attempt", lambda: "Should not run", is_risky=False)
    except RuntimeError as re:
        bypass_caught = True
        assert "RUN_PAUSED_FOR_HUMAN_APPROVAL" in str(re)
        print(f"[PASS] Criteria 4: execute_step() direct bypass blocked while paused ({re})")
    assert bypass_caught, "Failed to block execute_step on paused run!"

    # 5. Student tries to approve -> 403 Forbidden
    code_stu, res_stu = post_json("/api/aura/lab/6/approve", {
        "run_id": run_id,
        "role": "STUDENT",
        "actor_name": "Rahul Kumar (Student)"
    })
    assert code_stu == 403, f"Expected 403 for student approval, got {code_stu}: {res_stu}"
    assert "Role 'STUDENT' is not authorized" in res_stu.get("error", "")
    print(f"[PASS] Criteria 5: Student approval strictly rejected -> HTTP 403 Forbidden ({res_stu.get('error')})")

    # 6. Invalid run -> rejected (404)
    code_inv, res_inv = post_json("/api/aura/lab/6/approve", {
        "run_id": "RUN-INVALID-9999",
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni"
    })
    assert code_inv == 404, f"Expected 404 for invalid run, got {code_inv}: {res_inv}"
    print(f"[PASS] Criteria 6: Invalid run rejected -> HTTP 404 Not Found")

    # 7. Coordinator approval -> accepted (200)
    # 8. Real database status changes only after approval
    code_app, res_app = post_json("/api/aura/lab/6/approve", {
        "run_id": run_id,
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni"
    })
    assert code_app == 200, f"Expected 200 for coordinator approval, got {code_app}: {res_app}"
    assert res_app.get("status") == "HUMAN_APPROVAL_GRANTED"
    assert res_app.get("runtime_state", {}).get("status") == "COMPLETED"
    print(f"[PASS] Criteria 7: Coordinator approval accepted -> HTTP 200 (Status: {res_app.get('status')})")

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision, approved_company, coordinator_id FROM student_submissions WHERE id = ?", (sub1_id,))
    sub_after = dict(c.fetchone())
    conn.close()
    assert sub_after["status"] == "COORDINATOR_APPROVED", f"Expected COORDINATOR_APPROVED, got {sub_after['status']}"
    assert sub_after["coordinator_decision"] == "APPROVED"
    assert sub_after["approved_company"] == "ABC Technologies"
    print(f"[PASS] Criteria 8: Real database transition committed AFTER approval -> Status: {sub_after['status']}, Decision: {sub_after['coordinator_decision']}, Company: {sub_after['approved_company']}")

    # 11. Duplicate approval -> rejected (400)
    code_dup, res_dup = post_json("/api/aura/lab/6/approve", {
        "run_id": run_id,
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni"
    })
    assert code_dup == 400, f"Expected 400 for duplicate approval, got {code_dup}: {res_dup}"
    assert "Duplicate or invalid continuation rejected" in res_dup.get("error", "")
    print(f"[PASS] Criteria 11: Duplicate approval rejected -> HTTP 400 Bad Request")

    # -----------------------------------------------------
    # Test Rejection Path (Criteria 9 & 10)
    # -----------------------------------------------------
    # Create second submission for rejection test
    sub2_id = f"SUB-TEST-REJECT-{uuid.uuid4().hex[:6].upper()}"
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        pref_1_company, pref_1_role, pref_1_location, pref_1_remarks,
        status, coordinator_decision, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sub2_id, test_usn, 91, "NORMAL", "ABC Technologies", "AI/ML Intern", "Bangalore", "Lab 6 Test Rejection", "SUBMITTED", None, now))
    conn.commit()
    conn.close()

    code_rej_run, rej_run_res = post_json("/api/aura/lab/6/run", {
        "student_usn": test_usn,
        "submission_id": sub2_id
    })
    run2_id = rej_run_res["run_id"]

    # 9a. Rejection without mandatory reason -> 422 Unprocessable Entity
    code_empty_rej, res_empty_rej = post_json("/api/aura/lab/6/reject", {
        "run_id": run2_id,
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni",
        "rejection_reason": "" # Empty!
    })
    assert code_empty_rej == 422, f"Expected 422 for empty rejection reason, got {code_empty_rej}: {res_empty_rej}"
    print(f"[PASS] Criteria 9a: Empty rejection reason rejected -> HTTP 422 Validation Error")

    # 9b & 10. Rejection with mandatory reason -> accepted and persisted
    mandatory_reason = "Candidate does not possess required PyTorch GPU optimization experience."
    code_rej, res_rej = post_json("/api/aura/lab/6/reject", {
        "run_id": run2_id,
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni",
        "rejection_reason": mandatory_reason
    })
    assert code_rej == 200, f"Expected 200 for coordinator rejection, got {code_rej}: {res_rej}"
    assert res_rej.get("status") == "HUMAN_APPROVAL_REJECTED"
    assert res_rej.get("runtime_state", {}).get("status") == "REJECTED_BY_COORDINATOR"
    print(f"[PASS] Criteria 9b: Coordinator rejection accepted -> HTTP 200 (Status: {res_rej.get('status')})")

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision, rejection_reason FROM student_submissions WHERE id = ?", (sub2_id,))
    sub_rej = dict(c.fetchone())
    conn.close()
    assert sub_rej["status"] == "REJECTED", f"Expected REJECTED, got {sub_rej['status']}"
    assert sub_rej["coordinator_decision"] in ["REJECT", "REJECTED"]
    assert sub_rej["rejection_reason"] == mandatory_reason
    print(f"[PASS] Criteria 10: Rejection reason persisted in SQLite -> Status: {sub_rej['status']}, Reason: '{sub_rej['rejection_reason']}'")

    # 12. Audit events recorded
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT action, comments FROM audit_logs WHERE record_id = ? ORDER BY id ASC", (run_id,))
    logs_app = [dict(r) for r in c.fetchall()]
    actions_app = [l["action"] for l in logs_app]
    assert "AGENT_RUN_STARTED" in actions_app
    assert "HUMAN_APPROVAL_GATE_TRIGGERED" in actions_app
    assert "HUMAN_APPROVAL_GRANTED" in actions_app

    c.execute("SELECT action, comments FROM audit_logs WHERE record_id = ? ORDER BY id ASC", (run2_id,))
    logs_rej = [dict(r) for r in c.fetchall()]
    actions_rej = [l["action"] for l in logs_rej]
    assert "AGENT_RUN_STARTED" in actions_rej
    assert "HUMAN_APPROVAL_GATE_TRIGGERED" in actions_rej
    assert "HUMAN_APPROVAL_REJECTED" in actions_rej
    conn.close()
    print(f"[PASS] Criteria 12: Audit trail verified: AGENT_RUN_STARTED -> HUMAN_APPROVAL_GATE_TRIGGERED -> HUMAN_APPROVAL_GRANTED / HUMAN_APPROVAL_REJECTED")

    # 13. Existing Labs 1-5 remain passing
    # Test Lab 1 Planner
    code_l1, res_l1 = post_json("/api/aura/lab/1/run", {"message": "I want an internship"})
    assert code_l1 == 200 and res_l1.get("needs_clarification") is True

    # Test Lab 2 Tools
    code_l2, res_l2 = post_json("/api/aura/lab/2/run", {"student_usn": test_usn, "target_company": "ABC Technologies"})
    assert code_l2 == 200 and res_l2.get("status") == "SUCCESS"

    # Test Lab 3 Skills
    code_l3, res_l3 = post_json("/api/aura/lab/3/run", {"skill": "InternshipPlanSkill", "student_usn": test_usn})
    assert code_l3 == 200 and res_l3.get("is_valid") is True

    # Test Lab 4 Memory
    code_l4, res_l4 = post_json("/api/aura/lab/4/run", {"student_usn": test_usn, "action": "RECALL_CONTEXT"})
    assert code_l4 == 200 and "student_context" in res_l4

    # Test Lab 5 Governed MCP Connector
    coord_token = get_token("DR_RAMESH", "COORDINATOR")
    code_l5, res_l5 = post_json("/api/aura/lab/5/run", {"endpoint": "read_student_profile", "usn": test_usn}, headers={"Authorization": f"Bearer {coord_token}"})
    assert code_l5 == 200 and res_l5.get("status") == "SUCCESS"

    print(f"[PASS] Criteria 13: Existing Labs 1 through 5 verified 100% operational!")

    print("\n" + "=" * 65)
    print("ALL 13 LAB 6 ACCEPTANCE CRITERIA VERIFIED AND PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    main()
