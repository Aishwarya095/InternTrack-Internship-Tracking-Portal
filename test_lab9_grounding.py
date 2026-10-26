"""
INTERNTRACK — Lab 9 Deep Research & Grounding Acceptance Test Suite
Verifies:
1. Grounding every output in cited, in-scope faculty evidence.
2. Production of Unit-Level EvidenceRecord and Application-Level EvidenceTable.
3. Strict rejection of plausible-sounding but ungrounded candidates.
4. LangGraph StateGraph pipeline execution (Generation -> Grounding -> Validation).
5. REST API integration: POST /api/aura/lab/9/run.
"""

import unittest
import json
import urllib.request
from aura.lab9_grounding import (
    FACULTY_RUBRIC,
    FACULTY_BENCHMARK_TEST_CASES,
    CandidateUnit,
    EvidenceRecord,
    EvidenceTable,
    research_candidate_grounding,
    build_lab9_grounding_graph,
    run_lab9_deep_research
)
from database.db import query_all, query_one

class TestLab9Grounding(unittest.TestCase):

    def setUp(self):
        self.valid_student = "1KG21CS045"   # Rahul Kumar (CGPA 8.5, 0 backlogs)
        self.ineligible_student = "1KG21CS099" # Sneha Patil (CGPA 6.8, 1 backlog)
        self.unknown_student = "UNKNOWN_USN_999"

    def test_01_faculty_rubric_and_benchmark_integrity(self):
        """Verifies faculty rubric sections and benchmark test cases exist."""
        self.assertIn("rubric_id", FACULTY_RUBRIC)
        self.assertIn("rules", FACULTY_RUBRIC)
        self.assertIn("SEC-1.1", FACULTY_RUBRIC["rules"])
        self.assertIn("SEC-1.2", FACULTY_RUBRIC["rules"])
        self.assertIn("SEC-1.3", FACULTY_RUBRIC["rules"])
        self.assertIn("SEC-2.1", FACULTY_RUBRIC["rules"])
        self.assertGreaterEqual(len(FACULTY_BENCHMARK_TEST_CASES), 6)

    def test_02_unit_evidence_record_structure(self):
        """Verifies EvidenceRecord contains required audit fields, citations, and hashes."""
        rec = EvidenceRecord(
            unit_id="UNIT-TEST01",
            candidate_name="ABC Technologies",
            claim="Eligible for AI/ML Intern",
            source_title="Faculty Rubric SEC-2.1",
            source_citation="KLE Tech Catalog 2026",
            source_type="OFFICIAL_OPPORTUNITY_CATALOG",
            evidence_text="Verified in official catalog.",
            in_scope=True,
            verification_status="VERIFIED_GROUNDED",
            confidence_score=1.0,
            rubric_rule_cited="SEC-2.1"
        )
        self.assertEqual(rec["unit_id"], "UNIT-TEST01")
        self.assertTrue(rec["in_scope"])
        self.assertEqual(rec["verification_status"], "VERIFIED_GROUNDED")
        self.assertIn("evidence_hash", rec)
        self.assertIn("timestamp", rec)

    def test_03_in_scope_catalog_candidate_acceptance(self):
        """Candidate matching registered opportunity is accepted with grounded citation."""
        cand = CandidateUnit(company_name="ABC Technologies")
        ev = research_candidate_grounding(cand, self.valid_student)

        self.assertTrue(ev["in_scope"])
        self.assertEqual(ev["verification_status"], "VERIFIED_GROUNDED")
        self.assertIn("ABC Technologies", ev["candidate_name"])
        self.assertIn("Grounded in Catalog Record", ev["evidence_text"])
        self.assertIn("Cutoff", ev["evidence_text"])
        self.assertIsNone(ev["rejection_reason"])

    def test_04_adversarial_hallucination_strict_rejection(self):
        """Plausible-sounding entity not in catalog must be marked out of scope and rejected."""
        cand = CandidateUnit(company_name="Quantum Apex AI")
        ev = research_candidate_grounding(cand, self.valid_student)

        self.assertFalse(ev["in_scope"])
        self.assertEqual(ev["verification_status"], "UNGROUNDED_REJECTED")
        self.assertEqual(ev["confidence_score"], 0.0)
        self.assertEqual(ev["rubric_rule_cited"], "SEC-2.1")
        self.assertIn("plausible-sounding but ungrounded", ev["evidence_text"].lower())
        self.assertIsNotNone(ev["rejection_reason"])

    def test_05_in_scope_but_academically_ineligible_flagged(self):
        """Candidate with CGPA below cutoff is in-scope but marked ineligible with rubric citation."""
        # Sneha Patil has CGPA 6.8. DEF AI requires 8.5.
        cand = CandidateUnit(company_name="DEF AI")
        ev = research_candidate_grounding(cand, self.ineligible_student)

        self.assertTrue(ev["in_scope"])
        self.assertEqual(ev["verification_status"], "IN_SCOPE_INELIGIBLE")
        self.assertIn("SEC-1.2", ev["rubric_rule_cited"])
        self.assertIn("BELOW_CUTOFF", ev["evidence_text"])

    def test_06_langgraph_pipeline_execution(self):
        """Executes full StateGraph and verifies generation, grounding, and validation nodes."""
        graph = build_lab9_grounding_graph()
        initial_state = {
            "student_usn": self.valid_student,
            "raw_candidates": ["ABC Technologies", "XYZ Labs", "Quantum Apex AI"],
            "candidate_units": [],
            "evidence_records": [],
            "evidence_table": {},
            "accepted_candidates": [],
            "rejected_candidates": [],
            "execution_trace": [],
            "overall_status": "STARTING"
        }
        res = graph.invoke(initial_state)

        self.assertEqual(res["overall_status"], "VALIDATION_PASSED_GROUNDED")
        self.assertEqual(len(res["accepted_candidates"]), 2)
        self.assertEqual(len(res["rejected_candidates"]), 1)
        self.assertEqual(res["rejected_candidates"][0]["company"], "Quantum Apex AI")

        # Verify evidence attached to candidate
        for c in res["accepted_candidates"]:
            self.assertIsNotNone(c["evidence"])
            self.assertTrue(c["evidence"]["in_scope"])

        # Verify evidence table
        tbl = res["evidence_table"]
        self.assertEqual(tbl["total_units_evaluated"], 3)
        self.assertEqual(tbl["in_scope_units"], 2)
        self.assertEqual(tbl["ungrounded_units"], 1)
        self.assertEqual(tbl["grounding_rate_pct"], 66.7)

    def test_07_rest_api_endpoint_standard_and_adversarial(self):
        """Tests POST /api/aura/lab/9/run with standard and adversarial injection."""
        url = "http://127.0.0.1:8000/api/aura/lab/9/run"
        payload = {
            "student_usn": self.valid_student,
            "inject_adversarial": True
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))

        self.assertIn("Lab 9", data["lab"])
        self.assertEqual(data["status"], "VALIDATION_PASSED_GROUNDED")
        self.assertGreaterEqual(data["accepted_count"], 2)
        self.assertGreaterEqual(data["rejected_count"], 2) # Quantum Apex AI & CyberPhantom Blockchain Labs rejected

        # Verify no ungrounded items in accepted
        for acc in data["accepted_candidates"]:
            self.assertTrue(acc["evidence"]["in_scope"])
            self.assertNotIn("Quantum", acc["company"])
            self.assertNotIn("CyberPhantom", acc["company"])

    def test_08_core_build_book_algorithm_fidelity(self):
        """
        Directly checks fidelity of the Build Book algorithm:
        for c in candidates:
            ev = research(c, source='the faculty-provided test cases and rubric')
            if not ev.in_scope: reject(c)
            c.evidence = ev
        """
        candidates = [
            CandidateUnit("ABC Technologies"),
            CandidateUnit("PQR Solutions"),
            CandidateUnit("Fraudulent Non-MoU Startup")
        ]
        accepted = []
        rejected = []

        for c in candidates:
            ev = research_candidate_grounding(c, self.valid_student)
            c.evidence = ev
            if not ev["in_scope"]:
                rejected.append(c)
            else:
                accepted.append(c)

        self.assertEqual(len(accepted), 2)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].company_name, "Fraudulent Non-MoU Startup")
        self.assertFalse(rejected[0].evidence["in_scope"])
        self.assertEqual(rejected[0].evidence["rubric_rule_cited"], "SEC-2.1")

    def test_09_live_external_research_grounding(self):
        """Verifies live external job research attaches real active URLs and evaluates rubric compliance."""
        res = run_lab9_deep_research(
            student_usn=self.valid_student,
            use_live_search=True,
            search_query="software intern",
            search_location="Bangalore"
        )
        self.assertEqual(res["status"], "VALIDATION_PASSED_GROUNDED")
        self.assertGreater(res["total_evaluated"], 0)
        self.assertEqual(res["accepted_count"], res["total_evaluated"])

        # Verify live URLs and citations attached to each unit
        for acc in res["accepted_candidates"]:
            ev = acc["evidence"]
            self.assertTrue(ev["in_scope"])
            self.assertEqual(ev["verification_status"], "EXTERNAL_VERIFIED_PENDING_MOU")
            self.assertTrue(ev["source_citation"].startswith("Live Verified URL: http"))
            self.assertIn("Grounded via Live Job Search", ev["evidence_text"])
            self.assertEqual(ev["rubric_rule_cited"], "SEC-2.1")

if __name__ == "__main__":
    unittest.main()

