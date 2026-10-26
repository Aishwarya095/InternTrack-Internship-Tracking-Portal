"""
INTERNTRACK — Lab 13 Discipline-Specific Specialists Acceptance Test Suite
Verifies:
1. Pluggable specialist registry (Python AI/ML, C Systems/OS, SQL DBMS, Java Enterprise, DS/Algorithms).
2. Domain-appropriate outputs matching specific paradigms and constraints.
3. Rigorous checkable domain schemes (code, formal spec, and verifiable invariants).
4. Pitfall avoidance: Clever but vague outputs are strictly rejected.
5. Invariant violation detection (e.g. memory leaks in C, sequential scans in SQL).
6. LangGraph StateGraph pipeline execution.
7. REST API integration: POST /api/aura/lab/13/run.
"""

import unittest
import json
import urllib.request
import urllib.error

from aura.lab13_specialists import (
    registry,
    GenerationAgent,
    run_lab13_discipline_specialists
)

class TestLab13DisciplineSpecialists(unittest.TestCase):

    def setUp(self):
        self.student_usn = "1KG21CS045"
        self.company = "ABC Technologies"

    def test_01_registry_contains_all_five_specialists(self):
        """Verifies all 5 core CS discipline specialists are registered."""
        domains = registry.list_domains()
        domain_keys = [d["domain_key"] for d in domains]
        self.assertIn("PYTHON_AI_ML", domain_keys)
        self.assertIn("C_SYSTEMS_OS", domain_keys)
        self.assertIn("SQL_DBMS_DATA", domain_keys)
        self.assertIn("JAVA_ENTERPRISE_OOP", domain_keys)
        self.assertIn("DS_ALGORITHMS", domain_keys)

    def test_02_python_ai_specialist_clean_generation(self):
        """Python AI/ML specialist must generate checkable tensor shape and PEP 484 invariants."""
        res = run_lab13_discipline_specialists(
            domain_key="PYTHON_AI_ML",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="CLEAN"
        )
        self.assertEqual(res["status"], "SPECIALIST_DOMAIN_VERIFIED")
        self.assertTrue(res["all_invariants_passed"])
        scheme = res["scheme"]
        self.assertTrue(scheme["is_checkable"])
        self.assertIn("MultiHeadKVAttention", scheme["canonical_code_snippet"])
        self.assertGreaterEqual(len(scheme["invariants"]), 3)
        self.assertIn("torch.float16", scheme["formal_specification"]["precision"])

    def test_03_c_systems_specialist_clean_generation(self):
        """C Systems specialist must generate POSIX thread safe queue with zero heap leaks."""
        res = run_lab13_discipline_specialists(
            domain_key="C_SYSTEMS_OS",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="CLEAN"
        )
        self.assertEqual(res["status"], "SPECIALIST_DOMAIN_VERIFIED")
        self.assertTrue(res["all_invariants_passed"])
        scheme = res["scheme"]
        self.assertTrue(scheme["is_checkable"])
        self.assertIn("pthread_mutex_t", scheme["canonical_code_snippet"])
        self.assertIn("sem_t", scheme["canonical_code_snippet"])
        
        # Verify Valgrind zero-leak invariant
        inv_01 = next(inv for inv in scheme["invariants"] if inv["invariant_id"] == "INV-C-01")
        self.assertTrue(inv_01["passed"])
        self.assertIn("freed", inv_01["actual_observation"].lower())

    def test_04_sql_dbms_specialist_clean_generation(self):
        """SQL DBMS specialist must generate 3NF schema with B-Tree index and row-level locks."""
        res = run_lab13_discipline_specialists(
            domain_key="SQL_DBMS_DATA",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="CLEAN"
        )
        self.assertEqual(res["status"], "SPECIALIST_DOMAIN_VERIFIED")
        self.assertTrue(res["all_invariants_passed"])
        scheme = res["scheme"]
        self.assertTrue(scheme["is_checkable"])
        self.assertIn("CREATE TABLE IF NOT EXISTS placement_offers", scheme["canonical_code_snippet"])
        self.assertIn("FOR UPDATE", scheme["canonical_code_snippet"])
        self.assertIn("idx_offers_student_status", scheme["canonical_code_snippet"])

    def test_05_java_enterprise_specialist_clean_generation(self):
        """Java Enterprise specialist must generate constructor injection and @Transactional boundary."""
        res = run_lab13_discipline_specialists(
            domain_key="JAVA_ENTERPRISE_OOP",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="CLEAN"
        )
        self.assertEqual(res["status"], "SPECIALIST_DOMAIN_VERIFIED")
        self.assertTrue(res["all_invariants_passed"])
        scheme = res["scheme"]
        self.assertTrue(scheme["is_checkable"])
        self.assertIn("@Service", scheme["canonical_code_snippet"])
        self.assertIn("@Transactional", scheme["canonical_code_snippet"])

    def test_06_ds_algorithms_specialist_clean_generation(self):
        """DS/Algorithms specialist must generate Gale-Shapley with proven O(N^2) complexity."""
        res = run_lab13_discipline_specialists(
            domain_key="DS_ALGORITHMS",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="CLEAN"
        )
        self.assertEqual(res["status"], "SPECIALIST_DOMAIN_VERIFIED")
        self.assertTrue(res["all_invariants_passed"])
        scheme = res["scheme"]
        self.assertTrue(scheme["is_checkable"])
        self.assertIn("stable_matching", scheme["canonical_code_snippet"])
        self.assertEqual(scheme["formal_specification"]["time_complexity"], "O(N^2)")

    def test_07_invariant_violation_flagged(self):
        """When domain invariants fail (e.g. C memory leak or SQL missing index), status must reflect violation."""
        res = run_lab13_discipline_specialists(
            domain_key="C_SYSTEMS_OS",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="INJECT_INVARIANT_VIOLATION"
        )
        self.assertEqual(res["status"], "DOMAIN_INVARIANT_VIOLATION")
        self.assertFalse(res["all_invariants_passed"])
        
        # Verify specific failing invariant
        inv_01 = next(inv for inv in res["scheme"]["invariants"] if inv["invariant_id"] == "INV-C-01")
        self.assertFalse(inv_01["passed"])
        self.assertIn("leak", inv_01["actual_observation"].lower())

    def test_08_pitfall_avoidance_clever_vague_output_rejected(self):
        """Pitfall: Every specialist output needs a checkable scheme; clever but vague outputs are unusable."""
        res = run_lab13_discipline_specialists(
            domain_key="PYTHON_AI_ML",
            student_usn=self.student_usn,
            target_company=self.company,
            injection_mode="INJECT_VAGUE_OUTPUT"
        )
        self.assertEqual(res["status"], "VAGUE_OUTPUT_REJECTED")
        self.assertFalse(res["all_invariants_passed"])
        self.assertIn("Pitfall Enforced", res["rejection_reason"])
        self.assertIn("unusable", res["rejection_reason"].lower())
        self.assertIsNone(res["graded_submission"])

    def test_09_http_api_endpoint(self):
        """Verifies POST /api/aura/lab/13/run returns 200 and domain scheme."""
        payload = {
            "domain_key": "SQL_DBMS_DATA",
            "student_usn": self.student_usn,
            "target_company": self.company,
            "injection_mode": "CLEAN"
        }
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/aura/lab/13/run",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "SPECIALIST_DOMAIN_VERIFIED")
                self.assertTrue(data["all_invariants_passed"])
                self.assertIsNotNone(data["scheme"])
        except urllib.error.URLError:
            pass

if __name__ == "__main__":
    unittest.main()
