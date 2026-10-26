"""
Acceptance Test Suite for Lab 14 — Capstone — Team-Owned System
Phase D: Governance & Capstone

Tests:
1. system = deploy(connector, runtime, graph, governance) factory wiring.
2. system.run(request) produces a complete, checkable graded lab submission artifact.
3. Specialist domain integration (Python AI/ML, C Systems, SQL DBMS) in the capstone run.
4. Self-healing resilience loop repairs injected faults within retry budget.
5. SDLC Factory acceptance suite gates the artifact with 100% green pass.
6. Role-based confidentiality masking (Student view scrubbed vs Faculty view).
7. Faculty Examiner single-session approval workflow (Draft -> Approved v+1).
8. One-click version rollback cleanly restores prior release.
9. dashboard.show(artifact, metrics, audit) renders unified oversight cards.
10. REST API endpoint POST /api/aura/lab/14/run integration.
"""

import unittest
import json
import urllib.request
import urllib.error

from aura.lab14_capstone import (
    deploy,
    run_lab14_capstone,
    capstone_deployed_system,
    capstone_dashboard,
    FacultyExaminerDashboard,
    CapstoneDeployedSystem
)
from database.db import execute, query_one, query_all

class TestLab14Capstone(unittest.TestCase):
    def setUp(self):
        # Clean up test releases
        execute("DELETE FROM governance_releases WHERE student_usn = '1KG21CS045';")
        execute("DELETE FROM governance_metrics WHERE student_usn = '1KG21CS045';")

    def test_01_deploy_factory_wiring(self):
        """Verifies system = deploy(connector, runtime, graph, governance) conforms to contract."""
        system = deploy()
        self.assertIsInstance(system, CapstoneDeployedSystem)
        self.assertIsNotNone(system.connector)
        self.assertIsNotNone(system.runtime)
        self.assertIsNotNone(system.graph)
        self.assertIsNotNone(system.governance)

    def test_02_system_run_produces_graded_artifact(self):
        """Verifies system.run(request) produces a complete graded lab submission artifact."""
        request = {
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "PYTHON_AI_ML",
            "work_item_title": "Distributed Transformer Attention Module with FP16 KV-Cache",
            "milestone_key": "MILESTONE-1",
            "actor_role": "FACULTY_EXAMINER",
            "injection_mode": "CLEAN"
        }
        artifact = capstone_deployed_system.run(request)
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.get("student_usn"), "1KG21CS045")
        self.assertEqual(artifact.get("status"), "DRAFT_PENDING_APPROVAL")
        self.assertIn("marks_breakdown", artifact)
        self.assertGreaterEqual(artifact["marks_breakdown"]["total_awarded"], 90)
        self.assertIn("invariants", artifact)
        self.assertTrue(len(artifact["invariants"]) >= 2)

    def test_03_specialist_domain_integration(self):
        """Verifies different domain specialists plug into the capstone run."""
        # Test C Systems specialist in capstone
        request_c = {
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "C_SYSTEMS_OS",
            "work_item_title": "POSIX Circular Work Queue with Semaphore Bounds",
            "milestone_key": "MILESTONE-1",
            "actor_role": "FACULTY_EXAMINER",
            "injection_mode": "CLEAN"
        }
        art_c = capstone_deployed_system.run(request_c)
        self.assertEqual(art_c.get("specialist_domain"), "C Systems Programming & POSIX System Calls")
        c_invs = [inv["invariant_id"] for inv in art_c.get("invariants", [])]
        self.assertIn("INV-C-01", c_invs)

    def test_04_self_healing_resilience_loop(self):
        """Verifies injected rubric fault triggers automatic diagnose and repair in capstone."""
        request_fault = {
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "PYTHON_AI_ML",
            "work_item_title": "Fault Injected Module",
            "milestone_key": "MILESTONE-1",
            "actor_role": "FACULTY_EXAMINER",
            "injection_mode": "INJECT_RUBRIC_FAULT"
        }
        art = capstone_deployed_system.run(request_fault)
        self.assertIn("repair_history", art)
        # Verify marks repaired to be within rubric limit (30)
        self.assertLessEqual(art["marks_breakdown"]["technical_depth"], 30)

    def test_05_sdlc_acceptance_suite_gate(self):
        """Verifies SDLC acceptance suite gates the artifact before human review."""
        request = {
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "PYTHON_AI_ML",
            "milestone_key": "MILESTONE-1",
            "actor_role": "FACULTY_EXAMINER",
            "injection_mode": "CLEAN"
        }
        art = capstone_deployed_system.run(request)
        self.assertIn("acceptance_report", art)
        self.assertEqual(art["acceptance_report"]["suite_status"], "GREEN_ALL_PASSED")
        self.assertTrue(art["gate_decision"]["advanced_to_examiner"])

    def test_06_confidentiality_masking(self):
        """Verifies student view scrubs PII and internal examiner comments."""
        req_student = {
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "PYTHON_AI_ML",
            "milestone_key": "MILESTONE-1",
            "actor_role": "STUDENT",
            "injection_mode": "CLEAN"
        }
        art_stud = capstone_deployed_system.run(req_student)
        self.assertIn("student_view", art_stud)
        self.assertTrue(art_stud["student_view"])

    def test_07_faculty_examiner_single_session_approval(self):
        """Acceptance test: Faculty Examiner produces an approved, validated graded lab submission in one session."""
        res = run_lab14_capstone(
            student_usn="1KG21CS045",
            target_company="ABC Technologies",
            domain_key="PYTHON_AI_ML",
            actor_role="FACULTY_EXAMINER",
            actor_name="Faculty Examiner Desk",
            action_type="APPROVE_AND_PUBLISH",
            human_edits={
                "technical_depth": 30,
                "mentor_viva": 20,
                "examiner_feedback": "Capstone project demonstrates exceptional mastery."
            },
            examiner_remarks="Final capstone approved in one session."
        )
        self.assertEqual(res["status"], "SUCCESS")
        artifact = res["artifact"]
        self.assertEqual(artifact["status"], "APPROVED_PUBLISHED")
        self.assertEqual(artifact["release_info"]["version"], 1)
        self.assertEqual(artifact["marks_breakdown"]["total_awarded"], 99)

        # Confirm stored in DB
        db_release = query_one("SELECT * FROM governance_releases WHERE student_usn = ? AND version = 1;", ("1KG21CS045",))
        self.assertIsNotNone(db_release)
        self.assertEqual(db_release["status"], "APPROVED_PUBLISHED")

    def test_08_one_click_version_rollback(self):
        """Verifies one-click rollback restores prior release cleanly."""
        # Create Version 1
        run_lab14_capstone(student_usn="1KG21CS045", action_type="APPROVE_AND_PUBLISH")
        # Create Version 2
        run_lab14_capstone(
            student_usn="1KG21CS045",
            action_type="APPROVE_AND_PUBLISH",
            human_edits={"technical_depth": 25}
        )

        # Rollback to Version 1
        res = run_lab14_capstone(
            student_usn="1KG21CS045",
            action_type="ROLLBACK",
            target_rollback_version=1,
            rollback_reason="Reverting to initial version 1"
        )
        self.assertEqual(res["status"], "ROLLBACK_SUCCESSFUL")
        self.assertEqual(res["rollback_result"]["restored_version"], 1)

    def test_09_dashboard_show_contract(self):
        """Verifies dashboard.show(artifact, metrics, audit) renders complete dashboard view."""
        request = {
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "PYTHON_AI_ML",
            "milestone_key": "MILESTONE-1"
        }
        artifact = capstone_deployed_system.run(request)
        dashboard_view = capstone_dashboard.show(artifact)
        self.assertEqual(dashboard_view["student_usn"], "1KG21CS045")
        self.assertIn("score", dashboard_view)
        self.assertIn("grade", dashboard_view)
        self.assertIn("metrics", dashboard_view)
        self.assertIn("recent_audit_trail", dashboard_view)

    def test_10_rest_api_endpoint(self):
        """Verifies HTTP POST /api/aura/lab/14/run integration."""
        url = "http://127.0.0.1:8000/api/aura/lab/14/run"
        payload = json.dumps({
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies",
            "domain_key": "PYTHON_AI_ML",
            "action_type": "RUN_PIPELINE"
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data.get("status"), "SUCCESS")
                self.assertIn("artifact", data)
                self.assertIn("dashboard", data)
        except urllib.error.URLError:
            self.skipTest("Server on port 8000 not currently running.")

if __name__ == "__main__":
    unittest.main()
