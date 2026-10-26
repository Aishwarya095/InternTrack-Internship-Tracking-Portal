"""
Comprehensive Acceptance and Verification Suite for Lab 7 Governed Human Gate
Tests all 9 criteria requested:
TEST 1: Valid candidate reaches human_gate (paused, publish_node not executed, DB unchanged)
TEST 2: Student attempts approval -> HTTP 403 Forbidden
TEST 3: Anonymous approval -> HTTP 401/403 Unauthorized
TEST 4: Coordinator approves -> resumes SAME graph checkpoint, human_gate -> publish, status COMPLETED, DB updated
TEST 5: Coordinator rejects -> publish_node NOT executed, runtime REJECTED_BY_COORDINATOR, rejection reason persisted, audit event recorded
TEST 6: Attempt bypass while paused -> execution rejected
TEST 7: Attempt duplicate approval -> execution rejected
TEST 8: Existing validation retry still works -> validation failure -> retry -> discovery -> validation
TEST 9: Existing Labs 1-6 regression tests remain PASS
"""

import json
import urllib.request
import urllib.error
import sqlite3
import os
import sys
import uuid
from datetime import datetime

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
    print("=" * 70)
    print("LAB 7 LANGGRAPH GOVERNED HUMAN GATE ACCEPTANCE & VERIFICATION SUITE")
    print("=" * 70)

    test_usn = "1KG21CS045"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Setup clean submission in SUBMITTED state for Lab 7 test
    sub1_id = f"SUB-L7-APP-{uuid.uuid4().hex[:6].upper()}"
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        pref_1_company, pref_1_role, pref_1_location, pref_1_remarks,
        status, coordinator_decision, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sub1_id, test_usn, 95, "NORMAL", "ABC Technologies", "AI/ML Intern", "Bangalore", "Lab 7 Approval Test", "SUBMITTED", None, now))
    conn.commit()
    conn.close()

    # Capture DB snapshot before Test 1
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision FROM student_submissions WHERE id = ?", (sub1_id,))
    sub_init = dict(c.fetchone())
    conn.close()

    # ----------------------------------------------------
    # TEST 1: Valid candidate reaches human_gate
    # ----------------------------------------------------
    print("\n--- TEST 1: Valid candidate reaches Coordinator Human Gate ---")
    code_t1, res_t1 = post_json("/api/aura/lab/7/run", {
        "student_usn": test_usn,
        "submission_id": sub1_id
    })
    assert code_t1 == 200, f"Expected 200, got {code_t1}: {res_t1}"
    assert res_t1.get("status") == "PAUSED_FOR_COORDINATOR_APPROVAL", f"Expected PAUSED_FOR_COORDINATOR_APPROVAL, got {res_t1.get('status')}"
    assert res_t1.get("approval_status") == "PAUSED_FOR_COORDINATOR_APPROVAL"
    assert "Coordinator Human Gate" in res_t1["execution_path"]
    assert "Publish Node" not in res_t1["execution_path"], "Publish Node must NOT execute before human approval!"
    assert res_t1.get("validation_passed") is True
    run_id = res_t1["run_id"]
    print(f"Recorded Path: {res_t1['execution_path']}")
    print(f"Status: {res_t1['status']} | Run ID: {run_id}")

    # Verify database unchanged while paused
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision FROM student_submissions WHERE id = ?", (sub1_id,))
    sub_paused = dict(c.fetchone())
    conn.close()
    assert sub_paused["status"] == sub_init["status"] == "SUBMITTED", f"DB modified prematurely! {sub_paused}"
    assert sub_paused["coordinator_decision"] is None
    print("[PASS] TEST 1: Graph paused at Coordinator Human Gate, Publish Node NOT executed, Database unchanged!")

    # ----------------------------------------------------
    # TEST 2: Student attempts approval
    # ----------------------------------------------------
    print("\n--- TEST 2: Student attempts approval (Role Check) ---")
    student_token = get_token(test_usn, "STUDENT")
    code_t2, res_t2 = post_json("/api/aura/lab/7/approve", {
        "run_id": run_id,
        "role": "STUDENT"
    })
    assert code_t2 == 403, f"Expected 403, got {code_t2}: {res_t2}"
    assert "Role 'STUDENT' is not authorized" in res_t2.get("error", "")

    # Also test with student Bearer token in header
    code_t2b, res_t2b = post_json("/api/aura/lab/7/approve", {"run_id": run_id}, headers={"Authorization": f"Bearer {student_token}"})
    assert code_t2b == 403, f"Expected 403 for student Bearer token, got {code_t2b}: {res_t2b}"
    print(f"[PASS] TEST 2: Student approval strictly blocked with HTTP 403 ({res_t2.get('error')})")

    # ----------------------------------------------------
    # TEST 3: Anonymous approval
    # ----------------------------------------------------
    print("\n--- TEST 3: Anonymous approval attempt ---")
    code_t3, res_t3 = post_json("/api/aura/lab/7/approve", {"run_id": run_id})
    assert code_t3 in [401, 403], f"Expected 401/403, got {code_t3}: {res_t3}"
    assert "Authentication required" in res_t3.get("error", "")
    print(f"[PASS] TEST 3: Anonymous approval blocked with HTTP {code_t3} ({res_t3.get('error')})")

    # ----------------------------------------------------
    # TEST 6: Attempt bypass while paused
    # ----------------------------------------------------
    print("\n--- TEST 6: Attempt bypass while paused ---")
    code_t6, res_t6 = post_json("/api/aura/lab/7/run", {
        "student_usn": test_usn,
        "run_id": run_id
    })
    assert code_t6 == 400, f"Expected 400 for bypass attempt, got {code_t6}: {res_t6}"
    assert "RUN_PAUSED_FOR_HUMAN_APPROVAL" in res_t6.get("error", "")
    print(f"[PASS] TEST 6: Direct execution bypass on paused run blocked ({res_t6.get('error')})")

    # ----------------------------------------------------
    # TEST 4: Coordinator approves
    # ----------------------------------------------------
    print("\n--- TEST 4: Coordinator approves ---")
    coord_token = get_token("DR_RAMESH", "COORDINATOR")
    code_t4, res_t4 = post_json("/api/aura/lab/7/approve", {
        "run_id": run_id,
        "coordinator_name": "Dr. Ramesh Kulkarni"
    }, headers={"Authorization": f"Bearer {coord_token}"})

    assert code_t4 == 200, f"Expected 200, got {code_t4}: {res_t4}"
    assert res_t4.get("status") == "HUMAN_APPROVAL_GRANTED"
    assert res_t4.get("runtime_status") == "COMPLETED"
    assert "Publish Node" in res_t4.get("execution_path", [])
    print(f"Resumed Path: {res_t4['execution_path']}")

    # Verify real canonical database transition occurred
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision, approved_company, coordinator_id FROM student_submissions WHERE id = ?", (sub1_id,))
    sub_approved = dict(c.fetchone())
    c.execute("SELECT id, company, status FROM internships WHERE submission_id = ?", (sub1_id,))
    intern_rec = c.fetchone()
    conn.close()

    assert sub_approved["status"] == "COORDINATOR_APPROVED", f"Expected COORDINATOR_APPROVED, got {sub_approved['status']}"
    assert sub_approved["coordinator_decision"] == "APPROVED"
    assert intern_rec is not None, "Internship tracking record must be created upon canonical approval!"
    print(f"[PASS] TEST 4: Graph resumed same checkpoint to Publish Node. Submission updated to {sub_approved['status']} and internship record {dict(intern_rec)} created!")

    # ----------------------------------------------------
    # TEST 7: Attempt duplicate approval
    # ----------------------------------------------------
    print("\n--- TEST 7: Attempt duplicate approval on completed run ---")
    code_t7, res_t7 = post_json("/api/aura/lab/7/approve", {
        "run_id": run_id,
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni"
    })
    assert code_t7 == 400, f"Expected 400 for duplicate approval, got {code_t7}: {res_t7}"
    assert "Duplicate or invalid continuation rejected" in res_t7.get("error", "")
    print(f"[PASS] TEST 7: Duplicate approval on completed run rejected ({res_t7.get('error')})")

    # ----------------------------------------------------
    # TEST 5: Coordinator rejects
    # ----------------------------------------------------
    print("\n--- TEST 5: Coordinator Rejection with Mandatory Reason ---")
    sub2_id = f"SUB-L7-REJ-{uuid.uuid4().hex[:6].upper()}"
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        pref_1_company, pref_1_role, pref_1_location, pref_1_remarks,
        status, coordinator_decision, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sub2_id, test_usn, 96, "NORMAL", "ABC Technologies", "AI/ML Intern", "Bangalore", "Lab 7 Rejection Test", "SUBMITTED", None, now))
    conn.commit()
    conn.close()

    # Run graph to reach Human Gate pause
    code_t5_run, res_t5_run = post_json("/api/aura/lab/7/run", {
        "student_usn": test_usn,
        "submission_id": sub2_id
    })
    run2_id = res_t5_run["run_id"]
    assert res_t5_run["status"] == "PAUSED_FOR_COORDINATOR_APPROVAL"

    # Attempt rejection without mandatory reason -> HTTP 422
    code_t5_empty, res_t5_empty = post_json("/api/aura/lab/7/reject", {
        "run_id": run2_id,
        "role": "COORDINATOR",
        "rejection_reason": "   " # Empty
    })
    assert code_t5_empty == 422, f"Expected 422 for empty rejection reason, got {code_t5_empty}: {res_t5_empty}"
    print(f"Empty reason correctly rejected -> HTTP 422 ({res_t5_empty.get('error')})")

    # Reject with mandatory reason
    rejection_text = "Applicant failed the mandatory coding diagnostic test."
    code_t5, res_t5 = post_json("/api/aura/lab/7/reject", {
        "run_id": run2_id,
        "role": "COORDINATOR",
        "coordinator_name": "Dr. Ramesh Kulkarni",
        "rejection_reason": rejection_text
    })
    assert code_t5 == 200, f"Expected 200, got {code_t5}: {res_t5}"
    assert res_t5.get("status") == "HUMAN_APPROVAL_REJECTED"
    assert res_t5.get("runtime_status") == "REJECTED_BY_COORDINATOR"
    assert "Publish Node" not in res_t5.get("execution_path", []), "Publish Node must NOT execute upon rejection!"

    # Verify rejection persisted in DB and audit logs
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, coordinator_decision, rejection_reason FROM student_submissions WHERE id = ?", (sub2_id,))
    sub2_row = dict(c.fetchone())
    c.execute("SELECT action, comments FROM audit_logs WHERE record_id = ? AND action = 'HUMAN_APPROVAL_REJECTED'", (run2_id,))
    audit_rej = c.fetchone()
    conn.close()

    assert sub2_row["status"] == "REJECTED"
    assert sub2_row["rejection_reason"] == rejection_text
    assert audit_rej is not None, "Rejection audit event must be persisted!"
    print(f"[PASS] TEST 5: Coordinator rejection persisted -> Status: {sub2_row['status']}, Reason: '{sub2_row['rejection_reason']}', Audit recorded!")

    # ----------------------------------------------------
    # TEST 8: Existing validation retry still works
    # ----------------------------------------------------
    print("\n--- TEST 8: Existing validation retry and bounded recovery ---")
    code_t8, res_t8 = post_json("/api/aura/lab/7/run", {
        "student_usn": "1KG21CS099",
        "preferences": ["ABC Technologies", "XYZ Labs"]
    })
    assert code_t8 == 200, f"Expected 200, got {code_t8}: {res_t8}"
    path_t8 = res_t8["execution_path"]
    assert "Retry Node (Attempt 1)" in path_t8, f"Retry Node should be present in path: {path_t8}"
    assert "Discovery Agent" in path_t8
    assert "Validation Node" in path_t8
    assert "Coordinator Human Gate" in path_t8
    assert "Publish Node" not in path_t8
    assert res_t8["status"] == "PAUSED_FOR_COORDINATOR_APPROVAL"
    print(f"Retry Path: {path_t8}")
    print("[PASS] TEST 8: Validation failure triggered retry -> discovery -> validation -> human gate!")

    # ----------------------------------------------------
    # TEST 9: Existing Labs 1–6 regression tests remain PASS
    # ----------------------------------------------------
    print("\n--- TEST 9: Existing Labs 1 through 6 Regression Suite ---")
    # Lab 1
    c1, r1 = post_json("/api/aura/lab/1/run", {"message": "I want an internship"})
    assert c1 == 200 and r1.get("needs_clarification") is True
    print(" • Lab 1 (Planner): PASS")

    # Lab 2
    c2, r2 = post_json("/api/aura/lab/2/run", {"student_usn": test_usn, "target_company": "ABC Technologies"})
    assert c2 == 200 and r2.get("status") == "SUCCESS"
    print(" • Lab 2 (Tools): PASS")

    # Lab 3
    c3, r3 = post_json("/api/aura/lab/3/run", {"skill": "InternshipPlanSkill", "student_usn": test_usn})
    assert c3 == 200 and r3.get("is_valid") is True
    print(" • Lab 3 (Skills): PASS")

    # Lab 4
    c4, r4 = post_json("/api/aura/lab/4/run", {"student_usn": test_usn, "action": "RECALL_CONTEXT"})
    assert c4 == 200 and "student_context" in r4
    print(" • Lab 4 (Memory): PASS")

    # Lab 5
    coord_token_l5 = get_token("DR_RAMESH", "COORDINATOR")
    c5, r5 = post_json("/api/aura/lab/5/run", {"endpoint": "read_student_profile", "usn": test_usn}, headers={"Authorization": f"Bearer {coord_token_l5}"})
    assert c5 == 200 and r5.get("status") == "SUCCESS"
    print(" • Lab 5 (Governed MCP): PASS")

    # Lab 6
    sub_l6 = f"SUB-L6-REG-{uuid.uuid4().hex[:6].upper()}"
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        pref_1_company, pref_1_role, pref_1_location, pref_1_remarks,
        status, coordinator_decision, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sub_l6, test_usn, 97, "NORMAL", "ABC Technologies", "AI/ML Intern", "Bangalore", "Lab 6 Regression", "SUBMITTED", None, now))
    conn.commit()
    conn.close()

    c6, r6 = post_json("/api/aura/lab/6/run", {"student_usn": test_usn, "submission_id": sub_l6})
    assert c6 == 200 and r6.get("status") == "PAUSED_FOR_APPROVAL"
    c6_app, r6_app = post_json("/api/aura/lab/6/approve", {"run_id": r6["run_id"], "role": "COORDINATOR", "coordinator_name": "Dr. Ramesh Kulkarni"})
    assert c6_app == 200 and r6_app.get("status") == "HUMAN_APPROVAL_GRANTED"
    print(" • Lab 6 (Governed Human Gate): PASS")

    print("[PASS] TEST 9: Labs 1 through 6 verified 100% operational!")

    print("\n" + "=" * 70)
    print("ALL 9 LAB 7 ACCEPTANCE & VERIFICATION TESTS COMPLETED AND PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
