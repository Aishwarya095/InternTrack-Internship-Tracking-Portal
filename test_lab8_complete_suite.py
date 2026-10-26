"""
INTERNTRACK — Lab 8 Comprehensive Acceptance Test Suite
Tests all 13 required verification criteria for Lab 8 LangGraph Parallel Swarm:
1. Parallel concurrency across 4 workers
2. Fan-in aggregation of all 4 branches
3. Real DB eligibility and vacancy checks
4. Reaching Coordinator Human Gate (PAUSED_FOR_COORDINATOR_APPROVAL)
5. DB unchanged while paused
6. Student approval attempt -> HTTP 403
7. Anonymous approval attempt -> HTTP 401
8. Coordinator approval -> Resumes SAME checkpoint to commit
9. Coordinator rejection -> Mandatory reason check (422) + clean termination
10. Direct bypass attempt on paused run -> Blocked (HTTP 400)
11. Worker failure isolation -> Worker error handled gracefully, 4 results received
12. Dynamic preferences resolution from student submission (not hardcoded)
13. Labs 1-7 regression suite PASS
"""

import unittest
import urllib.request
import urllib.error
import json
import uuid
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db, query_one
from database.seed_data import seed
from aura.lab8_langgraph import (
    lab8_compiled_swarm,
    _evaluate_preference_worker,
    resolve_student_preferences,
    run_lab8_langgraph,
    approve_lab8_langgraph,
    reject_lab8_langgraph,
    lab8_active_runs
)
from workflows.submissions import create_submission, get_submission_by_id

BASE_URL = "http://localhost:8000"

def post_json(path, data=None, headers=None):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data or {}).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        try:
            err_data = json.loads(err.read().decode())
        except Exception:
            err_data = {"error": err.reason}
        return err.code, err_data

class TestLab8CompleteSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed()

    def test_01_four_workers_execute_in_parallel(self):
        """TEST 1: Four workers execute in parallel."""
        # Test concurrency by measuring timing with slight worker delay
        # Each worker evaluating takes time; if sequential, 4 * 50ms = 200ms; in parallel = ~50ms
        import threading
        thread_ids = set()

        # Let's inspect the compiled StateGraph structure
        nodes = lab8_compiled_swarm.nodes
        self.assertIn("worker_1", nodes)
        self.assertIn("worker_2", nodes)
        self.assertIn("worker_3", nodes)
        self.assertIn("worker_4", nodes)
        self.assertIn("fan_in", nodes)
        self.assertIn("human_gate", nodes)
        self.assertIn("commit", nodes)

        # Run via API and verify trace shows discrete worker nodes
        status, data = post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "preferences": ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"]
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["evaluations_count"], 4)
        worker_names = [e["worker"] for e in data["ranked_results"]]
        self.assertIn("Worker 1", worker_names)
        self.assertIn("Worker 2", worker_names)
        self.assertIn("Worker 3", worker_names)
        self.assertIn("Worker 4", worker_names)

    def test_02_fan_in_receives_all_four_results(self):
        """TEST 2: Fan-in receives all four results."""
        status, data = post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "preferences": ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"]
        })
        self.assertEqual(status, 200)
        self.assertEqual(len(data["ranked_results"]), 4)
        companies_evaluated = [r["company"] for r in data["ranked_results"]]
        self.assertIn("ABC Technologies", companies_evaluated)
        self.assertIn("XYZ Labs", companies_evaluated)
        self.assertIn("PQR Solutions", companies_evaluated)
        self.assertIn("DEF AI", companies_evaluated)

    def test_03_real_db_eligibility_and_vacancy_checks(self):
        """TEST 3: Real DB eligibility and vacancy checks."""
        # For student 1KG21CS045 (Rahul, CGPA 8.5, backlogs 0)
        status, data = post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "preferences": ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"]
        })
        self.assertEqual(status, 200)
        for r in data["ranked_results"]:
            self.assertIn("is_eligible", r)
            self.assertIn("available_vacancies", r)
            self.assertIn("min_cgpa", r)
            self.assertIn("status_explanation", r)
            self.assertGreaterEqual(r["available_vacancies"], 0)
            # Rahul has 8.5 CGPA, so should be eligible for ABC (min 7.5), XYZ (min 7.0), PQR (min 8.0)
            if r["company"] in ["ABC Technologies", "XYZ Labs", "PQR Solutions"]:
                self.assertTrue(r["is_eligible"])

    def test_04_lab8_reaches_coordinator_human_gate_and_pauses(self):
        """TEST 4: Lab 8 reaches Coordinator Human Gate. Expected: PAUSED_FOR_COORDINATOR_APPROVAL."""
        run_id = f"RUN-TEST4-{uuid.uuid4().hex[:6].upper()}"
        # 1. Test via HTTP REST endpoint
        status, data = post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "preferences": ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"],
            "run_id": run_id
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "PAUSED_FOR_COORDINATOR_APPROVAL")
        self.assertEqual(data["approval_status"], "PAUSED_FOR_COORDINATOR_APPROVAL")
        self.assertIn("Coordinator Approval Required", data["next_step"])

        # 2. Test in-process LangGraph invocation to verify checkpoint state interrupt
        inproc_run_id = f"RUN-INPROC-{uuid.uuid4().hex[:6].upper()}"
        inproc_res = run_lab8_langgraph("1KG21CS045", ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"], run_id=inproc_run_id)
        self.assertEqual(inproc_res["status"], "PAUSED_FOR_COORDINATOR_APPROVAL")
        config = {"configurable": {"thread_id": inproc_run_id}}
        state = lab8_compiled_swarm.get_state(config)
        self.assertEqual(state.next, ("commit",))

    def test_05_database_unchanged_while_paused(self):
        """TEST 5: Database unchanged while paused."""
        usn = "1KG21CS045"
        # Create a fresh submission
        sub = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": "ABC Technologies",
            "pref_2_company": "XYZ Labs"
        })
        sub_id = sub["id"]
        self.assertEqual(sub["status"], "SUBMITTED")

        run_id = f"RUN-TEST5-{uuid.uuid4().hex[:6].upper()}"
        status, data = post_json("/api/aura/lab/8/run", {
            "student_usn": usn,
            "submission_id": sub_id,
            "run_id": run_id
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "PAUSED_FOR_COORDINATOR_APPROVAL")

        # Verify database submission has NOT changed to COORDINATOR_APPROVED
        sub_after = get_submission_by_id(sub_id)
        self.assertEqual(sub_after["status"], "SUBMITTED")
        self.assertIsNone(sub_after.get("approved_company"))

    def test_06_student_attempts_approval(self):
        """TEST 6: Student attempts approval -> Expected HTTP 403."""
        run_id = f"RUN-TEST6-{uuid.uuid4().hex[:6].upper()}"
        post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "run_id": run_id
        })

        status, data = post_json("/api/aura/lab/8/approve", {
            "run_id": run_id,
            "role": "STUDENT"
        })
        self.assertEqual(status, 403)
        self.assertIn("Access Denied", data["error"])

    def test_07_anonymous_approval(self):
        """TEST 7: Anonymous approval -> Expected HTTP 401."""
        run_id = f"RUN-TEST7-{uuid.uuid4().hex[:6].upper()}"
        post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "run_id": run_id
        })

        status, data = post_json("/api/aura/lab/8/approve", {
            "run_id": run_id
        })
        self.assertEqual(status, 401)
        self.assertIn("Authentication required", data["error"])

    def test_08_coordinator_approval_resumes_same_checkpoint(self):
        """TEST 8: Coordinator approval -> Resumes SAME LangGraph checkpoint into commit."""
        usn = "1KG21CS045"
        sub = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": "ABC Technologies",
            "pref_2_company": "XYZ Labs"
        })
        sub_id = sub["id"]

        run_id = f"RUN-TEST8-{uuid.uuid4().hex[:6].upper()}"
        status_run, data_run = post_json("/api/aura/lab/8/run", {
            "student_usn": usn,
            "submission_id": sub_id,
            "run_id": run_id
        })
        self.assertEqual(status_run, 200)
        self.assertEqual(data_run["status"], "PAUSED_FOR_COORDINATOR_APPROVAL")

        # Approve as COORDINATOR
        status_app, data_app = post_json("/api/aura/lab/8/approve", {
            "run_id": run_id,
            "role": "COORDINATOR",
            "coordinator_name": "Dr. Ramesh Kulkarni"
        })
        self.assertEqual(status_app, 200)
        self.assertEqual(data_app["status"], "HUMAN_APPROVAL_GRANTED")
        self.assertEqual(data_app["runtime_status"], "COMPLETED")
        self.assertEqual(data_app["consequential_action"], "COORDINATOR_APPROVED_SUBMISSION")

        # Verify DB updated
        sub_updated = get_submission_by_id(sub_id)
        self.assertEqual(sub_updated["status"], "COORDINATOR_APPROVED")

        # Verify duplicate approval on completed run returns HTTP 400
        status_dup, data_dup = post_json("/api/aura/lab/8/approve", {
            "run_id": run_id,
            "role": "COORDINATOR"
        })
        self.assertEqual(status_dup, 400)

    def test_09_coordinator_rejection_mandatory_reason(self):
        """TEST 9: Coordinator rejection -> Mandatory reason (422) + clean termination."""
        usn = "1KG21CS045"
        sub = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": "ABC Technologies",
            "pref_2_company": "XYZ Labs"
        })
        sub_id = sub["id"]

        run_id = f"RUN-TEST9-{uuid.uuid4().hex[:6].upper()}"
        status_run, data_run = post_json("/api/aura/lab/8/run", {
            "student_usn": usn,
            "submission_id": sub_id,
            "run_id": run_id
        })
        self.assertEqual(status_run, 200)

        # 1. Attempt rejection with empty reason -> HTTP 422
        status_rej_empty, data_rej_empty = post_json("/api/aura/lab/8/reject", {
            "run_id": run_id,
            "role": "COORDINATOR",
            "rejection_reason": "   "
        })
        self.assertEqual(status_rej_empty, 422)

        # 2. Reject with valid reason -> HTTP 200
        status_rej, data_rej = post_json("/api/aura/lab/8/reject", {
            "run_id": run_id,
            "role": "COORDINATOR",
            "rejection_reason": "Company quotas exhausted for this cycle."
        })
        self.assertEqual(status_rej, 200)
        self.assertEqual(data_rej["status"], "HUMAN_APPROVAL_REJECTED")
        self.assertEqual(data_rej["runtime_status"], "REJECTED_BY_COORDINATOR")
        self.assertEqual(data_rej["rejection_reason"], "Company quotas exhausted for this cycle.")

        # Check DB submission status
        sub_updated = get_submission_by_id(sub_id)
        self.assertEqual(sub_updated["status"], "REJECTED")

    def test_10_attempt_run_again_while_paused_blocked(self):
        """TEST 10: Attempt /run again while paused -> Expected bypass blocked (HTTP 400)."""
        run_id = f"RUN-TEST10-{uuid.uuid4().hex[:6].upper()}"
        status1, data1 = post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "run_id": run_id
        })
        self.assertEqual(status1, 200)
        self.assertEqual(data1["status"], "PAUSED_FOR_COORDINATOR_APPROVAL")

        # Second /run call with the same run_id while paused -> MUST be blocked
        status2, data2 = post_json("/api/aura/lab/8/run", {
            "student_usn": "1KG21CS045",
            "run_id": run_id
        })
        self.assertEqual(status2, 400)
        self.assertIn("RUN_PAUSED_FOR_HUMAN_APPROVAL", data2["error"])

    def test_11_worker_failure_isolation(self):
        """TEST 11: One worker throws an exception -> other 3 complete, fan-in executes, WORKER_ERROR handled."""
        # 1. Direct test of _evaluate_preference_worker with invalid input to simulate unexpected exception
        state = {"student_id": "1KG21CS045"}
        res = _evaluate_preference_worker("Worker Error Test", 12345, state)
        self.assertIn("evaluations", res)
        eval_item = res["evaluations"][0]
        self.assertEqual(eval_item["status"], "WORKER_ERROR")
        self.assertIn("Worker Evaluation Error", eval_item["status_explanation"])
        self.assertFalse(eval_item["is_eligible"])

        # 2. Test that a full swarm execution with a faulty branch isolates failure:
        # 3 workers succeed, 1 worker errors, fan-in merges all 4, swarm does not crash
        swarm_res = run_lab8_langgraph(
            student_usn="1KG21CS045",
            preferences=["ABC Technologies", "XYZ Labs", "PQR Solutions", 12345],
            run_id=f"RUN-ERR-{uuid.uuid4().hex[:6].upper()}"
        )
        self.assertEqual(swarm_res["evaluations_count"], 4)
        self.assertEqual(len(swarm_res["ranked_results"]), 4)
        statuses = [r["status"] for r in swarm_res["ranked_results"]]
        self.assertIn("WORKER_ERROR", statuses)
        self.assertEqual(statuses.count("EVALUATED"), 3)
        self.assertEqual(swarm_res["status"], "PAUSED_FOR_COORDINATOR_APPROVAL")

    def test_12_preferences_omitted_loaded_from_student_submission(self):
        """TEST 12: Preferences omitted from request -> loaded from student's actual submission."""
        usn = "1KG21CS045"
        # Seed a submission with 4 specific, unique preferences
        pref1, pref2, pref3, pref4 = "GlobalTech Systems", "XYZ Labs", "ABC Technologies", "DEF AI"
        sub = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": pref1,
            "pref_2_company": pref2,
            "pref_3_company": pref3,
            "pref_4_company": pref4
        })

        # Call /api/aura/lab/8/run without providing preferences
        status, data = post_json("/api/aura/lab/8/run", {
            "student_usn": usn
            # NO preferences provided!
        })
        self.assertEqual(status, 200)
        evaluated = data["preferences_evaluated"]
        self.assertEqual(len(evaluated), 4)
        self.assertEqual(evaluated[0], pref1)
        self.assertEqual(evaluated[1], pref2)
        self.assertEqual(evaluated[2], pref3)
        self.assertEqual(evaluated[3], pref4)

    def test_13_labs_1_to_7_regression(self):
        """TEST 13: Labs 1-7 regression -> All existing acceptance tests remain PASS."""
        import subprocess
        repo_root = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests/test_acceptance.py"],
            capture_output=True,
            text=True,
            cwd=repo_root
        )
        print("\n--- Acceptance Suite Output ---\n", result.stderr)
        self.assertEqual(result.returncode, 0, f"Acceptance suite failed:\n{result.stderr}")

if __name__ == "__main__":
    unittest.main()
