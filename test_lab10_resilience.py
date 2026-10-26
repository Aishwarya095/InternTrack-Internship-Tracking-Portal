"""
INTERNTRACK — Lab 10 Ops Resilience Acceptance Test Suite
Verifies:
1. Faculty rubric validation & sandbox execution containment.
2. Fault injection detection (marks ceiling, credit ceiling, sandbox enforcement).
3. Targeted diagnosis and failure pinpointing.
4. Targeted repair preserving untouched components (Pitfall avoidance).
5. Self-healing loop completion within budget.
6. Escalation to human coordinator upon budget exhaustion.
7. REST API integration: POST /api/aura/lab/10/run.
"""

import unittest
import json
import urllib.request
import urllib.error

from aura.lab10_resilience import (
    OPS_RESILIENCE_RUBRIC,
    validate_pipeline_output,
    diagnose_failures,
    regenerate_offending_parts,
    escalate_to_human,
    run_lab10_ops_resilience,
    generate_candidate_evaluation_output
)

class TestLab10OpsResilience(unittest.TestCase):

    def test_01_rubric_and_sandbox_constraints(self):
        """Verifies rubric rules, marks limits, and sandbox requirements exist."""
        self.assertIn("max_marks", OPS_RESILIENCE_RUBRIC)
        self.assertEqual(OPS_RESILIENCE_RUBRIC["max_marks"]["technical_depth"], 30)
        self.assertEqual(OPS_RESILIENCE_RUBRIC["max_marks"]["system_design"], 30)
        self.assertEqual(OPS_RESILIENCE_RUBRIC["max_marks"]["journal_logs"], 20)
        self.assertEqual(OPS_RESILIENCE_RUBRIC["max_marks"]["mentor_viva"], 20)
        self.assertEqual(OPS_RESILIENCE_RUBRIC["credit_ceiling"], 16)
        self.assertIn("DOCKER_SECCOMP", OPS_RESILIENCE_RUBRIC["required_sandbox_isolation"])

    def test_02_clean_evaluation_passes_first_attempt(self):
        """Clean evaluation output must pass validation without needing regeneration."""
        clean_out = generate_candidate_evaluation_output(injection_type="NONE")
        report = validate_pipeline_output(clean_out)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.failing), 0)

        # Full runner test
        res = run_lab10_ops_resilience(injection_type="NONE")
        self.assertEqual(res["status"], "SELF_HEALED_PASS")
        self.assertEqual(res["attempts_used"], 0)

    def test_03_detect_and_fix_max_marks_exceeded(self):
        """Awarded marks exceeding faculty maximum must be diagnosed and repaired."""
        res = run_lab10_ops_resilience(injection_type="MAX_MARKS_EXCEEDED")
        self.assertEqual(res["status"], "SELF_HEALED_PASS")
        self.assertGreaterEqual(res["attempts_used"], 1)
        self.assertLessEqual(res["attempts_used"], res["max_budget"])
        
        # Check initial had fault
        self.assertGreater(res["initial_output"]["evaluations"]["technical_depth"], 30)
        # Check repaired is compliant
        repaired_tech = res["repaired_output"]["evaluations"]["technical_depth"]
        self.assertLessEqual(repaired_tech, 30)
        self.assertTrue(res["final_report"]["passed"])

    def test_04_pitfall_avoidance_targeted_regeneration(self):
        """Regenerate ONLY the failing part — unaffected components must remain strictly untouched."""
        faulty = generate_candidate_evaluation_output(injection_type="MAX_MARKS_EXCEEDED")
        original_student_usn = faulty["student_usn"]
        original_company = faulty["target_company"]
        original_system_design = faulty["evaluations"]["system_design"]
        original_journal_logs = faulty["evaluations"]["journal_logs"]
        original_mentor_viva = faulty["evaluations"]["mentor_viva"]

        report = validate_pipeline_output(faulty)
        self.assertFalse(report.passed)
        self.assertEqual(report.failing[0].component_path, "evaluations.technical_depth")

        repaired, modified_fields = regenerate_offending_parts(report.failing, faulty)

        # Targeted fields must ONLY include technical_depth
        self.assertEqual(modified_fields, ["evaluations.technical_depth"])
        # All untouched components must be preserved 100%
        self.assertEqual(repaired["student_usn"], original_student_usn)
        self.assertEqual(repaired["target_company"], original_company)
        self.assertEqual(repaired["evaluations"]["system_design"], original_system_design)
        self.assertEqual(repaired["evaluations"]["journal_logs"], original_journal_logs)
        self.assertEqual(repaired["evaluations"]["mentor_viva"], original_mentor_viva)

    def test_05_detect_and_fix_unsandboxed_test_cases(self):
        """Every test case must run inside the sandbox. Unsandboxed runs must be contained."""
        res = run_lab10_ops_resilience(injection_type="UNSANDBOXED_EXECUTION")
        self.assertEqual(res["status"], "SELF_HEALED_PASS")
        self.assertFalse(res["initial_output"]["sandbox_environment"]["sandbox_contained"])
        self.assertTrue(res["repaired_output"]["sandbox_environment"]["sandbox_contained"])
        self.assertIn(res["repaired_output"]["sandbox_environment"]["isolation_type"], 
                      OPS_RESILIENCE_RUBRIC["required_sandbox_isolation"])
        self.assertTrue(res["final_report"]["passed"])

    def test_06_detect_and_fix_credit_ceiling_exceeded(self):
        """Credits exceeding 16 must be brought down to university standard."""
        res = run_lab10_ops_resilience(injection_type="CREDIT_CEILING_EXCEEDED")
        self.assertEqual(res["status"], "SELF_HEALED_PASS")
        self.assertGreater(res["initial_output"]["credits_allotted"], 16)
        self.assertEqual(res["repaired_output"]["credits_allotted"], 16)
        self.assertTrue(res["final_report"]["passed"])

    def test_07_compound_faults_multi_step_healing(self):
        """Multiple simultaneous faults (marks + credits + sandbox) are all diagnosed and repaired."""
        res = run_lab10_ops_resilience(injection_type="COMPOUND_FAULTS")
        self.assertEqual(res["status"], "SELF_HEALED_PASS")
        self.assertTrue(res["final_report"]["passed"])
        self.assertLessEqual(res["repaired_output"]["evaluations"]["technical_depth"], 30)
        self.assertLessEqual(res["repaired_output"]["credits_allotted"], 16)
        self.assertTrue(res["repaired_output"]["sandbox_environment"]["sandbox_contained"])
        self.assertGreaterEqual(res["repaired_output"]["stipend_monthly"], 15000)

    def test_08_budget_exhaustion_escalates_to_human(self):
        """If attempts >= BUDGET and report still fails, must escalate to Human Coordinator Desk."""
        res = run_lab10_ops_resilience(injection_type="FATAL_UNRECOVERABLE", custom_budget=2)
        self.assertEqual(res["status"], "ESCALATED_TO_HUMAN")
        self.assertIsNotNone(res["escalation"])
        self.assertEqual(res["escalation"]["escalated_to"], "Coordinator")
        self.assertIn("ESC-", res["escalation"]["escalation_id"])
        self.assertEqual(res["attempts_used"], 2)


    def test_09_http_api_endpoint(self):
        """Verifies POST /api/aura/lab/10/run returns 200 and repaired output."""
        payload = {"injection_type": "MAX_MARKS_EXCEEDED", "budget": 3}
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/aura/lab/10/run",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "SELF_HEALED_PASS")
            self.assertEqual(data["attempts_used"], 1)
            self.assertTrue(data["final_report"]["passed"])
            self.assertIn("evaluations.technical_depth", data["repaired_fields_history"][0])


if __name__ == "__main__":
    unittest.main()
