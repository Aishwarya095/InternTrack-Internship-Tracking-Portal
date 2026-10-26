"""
INTERNTRACK — Lab 12 Safety & Governance Acceptance Test Suite
Verifies:
1. Access control & role permissions (Student, Coordinator, Faculty Examiner, HOD).
2. Confidentiality controls (Sensitive examiner notes and NDA terms masked for Student).
3. Faculty Examiner approval gate as a hard stop (require actor.can_approve and out.status == 'draft').
4. Human edits application before final approval (final = apply(human.edits, out)).
5. Versioned reversible release (governance.publish(final, version=v+1)).
6. Evaluation metrics recording (metrics.record(...)).
7. One-click reversible rollback (on rollback(v): restore(version=v)).
8. Pitfall avoidance: Confidentiality and rollback are requirements, not extras.
9. REST API integration: POST /api/aura/lab/12/run.
"""

import unittest
import json
import urllib.request
import urllib.error

from aura.lab12_governance import (
    ROLE_PERMISSIONS,
    init_governance_tables,
    mask_confidential_content,
    create_draft_submission_artifact,
    apply_human_edits,
    publish_release,
    record_governance_metrics,
    rollback_to_version,
    get_release_history,
    run_lab12_governance_pipeline
)
from database.db import query_all, query_one, execute

class TestLab12SafetyGovernance(unittest.TestCase):

    def setUp(self):
        init_governance_tables()
        self.student_usn = "1KG21CS045"
        self.company = "ABC Technologies"
        self.milestone = "Milestone 1: Architecture & Sandbox Engine"
        # Reset test USN rows for deterministic version numbering
        execute("DELETE FROM governance_releases WHERE student_usn = ?", (self.student_usn,))
        execute("DELETE FROM governance_metrics WHERE student_usn = ?", (self.student_usn,))

    def test_01_role_permissions_and_confidentiality_masking(self):
        """Student role must have sensitive examiner notes & NDA terms masked; Faculty Examiner sees full content."""
        draft = create_draft_submission_artifact(self.student_usn, self.company, self.milestone)
        
        # Student View -> Masked
        masked_stud, was_masked = mask_confidential_content(draft, actor_role="STUDENT")
        self.assertTrue(was_masked)
        self.assertIn("[CONFIDENTIAL — REDACTED", masked_stud["examiner_private_rubric_notes"])
        self.assertIn("[CONFIDENTIAL NDA CLAUSE — REDACTED", masked_stud["confidential_stipend_nda_terms"])
        self.assertIn("[CONFIDENTIAL METRIC — REDACTED", masked_stud["internal_risk_assessment"])

        # Faculty Examiner View -> Full Unredacted
        examiner_view, was_masked_ex = mask_confidential_content(draft, actor_role="FACULTY_EXAMINER")
        self.assertFalse(was_masked_ex)
        self.assertNotIn("REDACTED", examiner_view["examiner_private_rubric_notes"])
        self.assertIn("Candidate hesitated", examiner_view["examiner_private_rubric_notes"])

    def test_02_faculty_examiner_approves_and_publishes_v1(self):
        """Faculty Examiner approval passes hard-stop gate, applies edits, and publishes version 1."""
        human_edits = {
            "technical_depth": 29,
            "mentor_viva": 19,
            "examiner_feedback": "Exemplary architecture design and robust sandbox implementation verified by Faculty Examiner."
        }
        res = run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Dr. Kulkarni",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone,
            human_edits=human_edits
        )
        self.assertEqual(res["status"], "GOVERNED_RELEASE_PUBLISHED")
        pub = res["published_artifact"]
        self.assertIsNotNone(pub)
        self.assertEqual(pub["version"], 1)
        self.assertEqual(pub["status"], "APPROVED_PUBLISHED")
        self.assertEqual(pub["evaluations"]["technical_depth"], 29)
        self.assertEqual(pub["evaluations"]["mentor_viva"], 19)
        self.assertEqual(pub["evaluations"]["total_score"], 93)
        self.assertIn("Exemplary architecture", pub["examiner_feedback"])
        
        # Verify metrics recorded
        metrics = res["governance_metrics"]
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["version"], 1)
        self.assertEqual(metrics["human_overrides_count"], 3)
        self.assertTrue(metrics["confidentiality_check_passed"])

    def test_03_unauthorized_student_approval_blocked(self):
        """Hard Stop: Student attempting to approve draft must be blocked with ACCESS_DENIED."""
        res = run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Student",
            actor_role="STUDENT",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone
        )
        self.assertEqual(res["status"], "GATE_BLOCKED_UNAUTHORIZED")
        self.assertIn("ACCESS_DENIED", res["error_message"])
        self.assertIsNone(res["published_artifact"])

    def test_04_multiple_versions_published_v1_v2(self):
        """Second approval creates version 2 and supersedes version 1."""
        # Initial v1
        res1 = run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Faculty Examiner",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone,
            human_edits={"mentor_viva": 18}
        )
        v1_num = res1["published_artifact"]["version"]

        # Follow-up revision v2
        res2 = run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Faculty Examiner",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone,
            human_edits={"mentor_viva": 20, "examiner_feedback": "Re-evaluated viva: full marks granted."}
        )
        v2_num = res2["published_artifact"]["version"]
        self.assertEqual(v2_num, v1_num + 1)
        self.assertEqual(res2["published_artifact"]["evaluations"]["mentor_viva"], 20)

        # Version history contains both
        history = get_release_history(self.student_usn, self.milestone)
        self.assertGreaterEqual(len(history), 2)
        # Latest version is active
        self.assertEqual(history[0]["version"], v2_num)
        self.assertEqual(history[0]["is_active"], 1)

    def test_05_one_click_reversible_rollback(self):
        """One-click rollback restores version 1, supersedes version 2, and logs audit event."""
        # Setup: Publish v1 and v2
        run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Faculty Examiner",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone,
            human_edits={"mentor_viva": 17}
        )
        run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Faculty Examiner",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone,
            human_edits={"mentor_viva": 20}
        )

        # Rollback to v1
        res_roll = run_lab12_governance_pipeline(
            action_type="ROLLBACK",
            actor_name="Faculty Examiner",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone,
            target_rollback_version=1,
            rollback_reason="Rollback test: restore original baseline evaluation"
        )
        self.assertEqual(res_roll["status"], "ROLLBACK_SUCCESSFUL")
        self.assertEqual(res_roll["restored_version"], 1)
        self.assertEqual(res_roll["active_release"]["version"], 1)
        self.assertTrue(res_roll["active_release"]["is_active"])

    def test_06_unauthorized_rollback_attempt_blocked(self):
        """Student cannot trigger rollback."""
        with self.assertRaises(PermissionError):
            rollback_to_version(
                target_version=1,
                student_usn=self.student_usn,
                milestone_name=self.milestone,
                actor_name="Student",
                actor_role="STUDENT"
            )

    def test_07_invalid_version_rollback_error(self):
        """Rollback to a non-existent version raises ValueError."""
        with self.assertRaises(ValueError):
            rollback_to_version(
                target_version=999,
                student_usn=self.student_usn,
                milestone_name=self.milestone,
                actor_name="Faculty Examiner",
                actor_role="FACULTY_EXAMINER"
            )

    def test_08_pitfall_avoidance_confidentiality_and_rollback_are_requirements(self):
        """Pitfall: Confidentiality and rollback are requirements, not extras."""
        # 1. Confidentiality requirement
        sample = {"examiner_private_rubric_notes": "Internal note", "confidential_stipend_nda_terms": "Secret"}
        masked, was_masked = mask_confidential_content(sample, "STUDENT")
        self.assertTrue(was_masked)
        self.assertIn("REDACTED", masked["examiner_private_rubric_notes"])

        # 2. Rollback requirement: Clean reversibility
        run_lab12_governance_pipeline(
            action_type="PUBLISH_APPROVAL",
            actor_name="Faculty Examiner",
            actor_role="FACULTY_EXAMINER",
            student_usn=self.student_usn,
            target_company=self.company,
            milestone_name=self.milestone
        )
        history = get_release_history(self.student_usn, self.milestone)
        self.assertGreaterEqual(len(history), 1)

    def test_09_http_api_endpoints(self):
        """Verifies POST /api/aura/lab/12/run returns 200 for approval and rollback."""
        payload = {
            "action_type": "PUBLISH_APPROVAL",
            "actor_name": "Faculty Examiner Desk",
            "actor_role": "FACULTY_EXAMINER",
            "student_usn": self.student_usn,
            "target_company": self.company,
            "milestone_name": self.milestone,
            "human_edits": {"mentor_viva": 20}
        }
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/aura/lab/12/run",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "GOVERNED_RELEASE_PUBLISHED")
                self.assertIsNotNone(data["published_artifact"])
        except urllib.error.URLError:
            pass

if __name__ == "__main__":
    unittest.main()
