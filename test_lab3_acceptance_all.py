import urllib.request
import json
import unittest

def call_lab3_api(payload):
    req = urllib.request.Request(
        "http://localhost:8000/api/aura/lab/3/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

class TestLab3DistinctSkills(unittest.TestCase):
    """
    Acceptance test suite for Lab 3 Reusable Schema-Typed Skills.
    Verifies that each of the four skills has a distinct contract,
    distinct validation/logic, distinct typed output, and works across multiple students.
    """

    def test_01_skill1_internship_plan_skill(self):
        """Skill 1: Generates structured 5-phase roadmap blueprint."""
        res = call_lab3_api({
            "skill": "InternshipPlanSkill",
            "student_usn": "1KG21CS045"
        })
        self.assertEqual(res["skill"], "InternshipPlanSkill")
        self.assertTrue(res["is_valid"])
        self.assertIn("roadmap", res)
        self.assertEqual(len(res["roadmap"]), 5)
        self.assertEqual(res["roadmap"][0]["phase_id"], "Phase 1")
        self.assertEqual(res["roadmap"][0]["title"], "Eligibility Verification")
        self.assertEqual(res["roadmap"][0]["owner"], "Coordinator")
        self.assertEqual(res["roadmap"][4]["phase_id"], "Phase 5")
        self.assertIn("internship_goal", res)
        self.assertIn("validation_checks", res)

    def test_02_skill1_reusability_student_b(self):
        """Skill 1 Reusability: Successfully creates distinct roadmap for Student B."""
        res = call_lab3_api({
            "skill": "InternshipPlanSkill",
            "student_usn": "1KG21IS099" # Pooja Hegde, ISE
        })
        self.assertEqual(res["candidate"]["name"], "Pooja Hegde")
        self.assertEqual(res["candidate"]["branch"], "ISE")
        self.assertEqual(res["candidate"]["usn"], "1KG21IS099")
        self.assertTrue(res["is_valid"])

    def test_03_skill2_application_validator_success(self):
        """Skill 2: Validates application constraints against company rules (PASS case)."""
        res = call_lab3_api({
            "skill": "ApplicationValidatorSkill",
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies"
        })
        self.assertEqual(res["skill"], "ApplicationValidatorSkill")
        self.assertEqual(res["final_status"], "VALID — READY FOR COORDINATOR REVIEW")
        self.assertTrue(res["is_valid"])
        self.assertIn("checks", res)
        self.assertGreaterEqual(len(res["checks"]), 6)
        # Ensure NO roadmap is returned
        self.assertNotIn("roadmap", res)

    def test_04_skill2_application_validator_real_failure(self):
        """Skill 2: Performs REAL validation; fails student below company CGPA cutoff."""
        # Rohan Verma (1KG21CS072) has CGPA 7.20. ABC Technologies requires min CGPA 7.50.
        res = call_lab3_api({
            "skill": "ApplicationValidatorSkill",
            "student_usn": "1KG21CS072",
            "target_company": "ABC Technologies"
        })
        self.assertEqual(res["skill"], "ApplicationValidatorSkill")
        self.assertEqual(res["final_status"], "INVALID — CORRECTION REQUIRED")
        self.assertFalse(res["is_valid"])
        self.assertGreater(len(res["issues"]), 0)
        self.assertTrue(any("below company cutoff" in iss for iss in res["issues"]))

    def test_05_skill3_opportunity_matching(self):
        """Skill 3: Evaluates active catalog listings and computes matching reasons."""
        res = call_lab3_api({
            "skill": "OpportunityMatchingSkill",
            "student_usn": "1KG21CS045"
        })
        self.assertEqual(res["skill"], "OpportunityMatchingSkill")
        self.assertIn("matched_opportunities", res)
        self.assertGreater(len(res["matched_opportunities"]), 0)
        top = res["matched_opportunities"][0]
        self.assertIn("matching_reasons", top)
        self.assertGreater(len(top["matching_reasons"]), 0)
        self.assertIn("match_score", top)
        self.assertIn("total_suitable", res)
        # Ensure NO roadmap and NO validator mimicry
        self.assertNotIn("roadmap", res)

    def test_06_skill4_document_formatter(self):
        """Skill 4: Compiles standardized application dossier."""
        res = call_lab3_api({
            "skill": "DocumentFormatterSkill",
            "student_usn": "1KG21CS045",
            "target_company": "ABC Technologies"
        })
        self.assertEqual(res["skill"], "DocumentFormatterSkill")
        self.assertIn("content", res)
        self.assertIn("OFFICIAL INTERNSHIP APPLICATION DOSSIER", res["content"])
        self.assertIn("CANDIDATE IDENTIFICATION", res["content"])
        self.assertIn("ALLOTTED INTERNSHIP PARTICULARS", res["content"])
        self.assertIn("PREFERENCE ROSTER (RANKED)", res["content"])
        self.assertIn("ACADEMIC & STATUTORY CLEARANCE", res["content"])
        self.assertIn("validation_checks", res)
        # Ensure NO roadmap or opportunity matching
        self.assertNotIn("roadmap", res)
        self.assertNotIn("matched_opportunities", res)

    def test_07_all_skills_have_distinct_outputs(self):
        """Verify that all 4 skills produce fundamentally distinct keys and contracts."""
        r1 = call_lab3_api({"skill": "InternshipPlanSkill", "student_usn": "1KG21CS045"})
        r2 = call_lab3_api({"skill": "ApplicationValidatorSkill", "student_usn": "1KG21CS045"})
        r3 = call_lab3_api({"skill": "OpportunityMatchingSkill", "student_usn": "1KG21CS045"})
        r4 = call_lab3_api({"skill": "DocumentFormatterSkill", "student_usn": "1KG21CS045"})

        # Skill 1 has roadmap phases
        self.assertIn("roadmap", r1)
        self.assertNotIn("roadmap", r2)
        self.assertNotIn("roadmap", r3)
        self.assertNotIn("roadmap", r4)

        # Skill 2 has checks and final_status
        self.assertIn("checks", r2)
        self.assertIn("final_status", r2)
        self.assertNotIn("checks", r1)
        self.assertNotIn("checks", r3)

        # Skill 3 has matched_opportunities with reasons
        self.assertIn("matched_opportunities", r3)
        self.assertNotIn("matched_opportunities", r1)
        self.assertNotIn("matched_opportunities", r2)
        self.assertNotIn("matched_opportunities", r4)

        # Skill 4 has formatted dossier content
        self.assertIn("content", r4)
        self.assertIn("internship", r4)
        self.assertNotIn("content", r1)
        self.assertNotIn("content", r2)
        self.assertNotIn("content", r3)

if __name__ == "__main__":
    unittest.main()
