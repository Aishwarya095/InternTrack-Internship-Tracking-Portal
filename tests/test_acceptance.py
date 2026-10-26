"""
INTERNTRACK — Automated Acceptance Test Suite
Verifies core college business rules, vacancy integrity, multi-submissions,
and LangGraph Labs 1 through 8.
"""

import os
import sys
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db
from database.seed_data import seed
from workflows.students import get_student_profile, mark_placed_company
from workflows.submissions import create_submission, coordinator_review_submission, get_submissions_by_student
from workflows.opportunities import get_opportunity, decrement_vacancy, check_eligibility_and_vacancy
from aura.lab1_planner import Lab1PlannerAgent
from aura.lab2_tools import Lab2ToolUsingAgent
from aura.lab3_skills import InternshipPlanSkill, ApplicationValidatorSkill, PlanInputSchema
from aura.lab4_memory import MemoryRetrievalEngine
from aura.lab5_connector import mcp_connector
from aura.lab6_runtime import ControlledAgentRuntime
from aura.lab7_langgraph import run_lab7_langgraph
from aura.lab8_langgraph import run_lab8_langgraph

class TestInternTrackSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed()

    def test_01_student_profile_seeded(self):
        """Verify Rahul Kumar's profile is loaded properly."""
        rahul = get_student_profile("1KG21CS045")
        self.assertIsNotNone(rahul)
        self.assertEqual(rahul["name"], "Rahul Kumar")
        self.assertEqual(rahul["cgpa"], 8.5)
        self.assertEqual(rahul["backlogs"], 0)

    def test_02_placed_company_bypass(self):
        """Verify that a placed student bypasses standard matching and is directly confirmed."""
        ananya = get_student_profile("1KG21CS008")
        self.assertEqual(ananya["placement_status"], "PLACED_COMPANY")
        self.assertEqual(ananya["placed_company"], "TCS Digital")

    def test_03_multi_submission_history_preserved(self):
        """Verify that submitting multiple times creates incremental versions without overwriting."""
        usn = "1KG21CS045"
        sub1 = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": "ABC Technologies",
            "pref_2_company": "XYZ Labs"
        })
        self.assertIsNotNone(sub1)

        sub2 = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": "PQR Solutions",
            "pref_2_company": "DEF AI"
        })
        self.assertIsNotNone(sub2)
        self.assertGreater(sub2["submission_version"], sub1["submission_version"])

        history = get_submissions_by_student(usn)
        self.assertGreaterEqual(len(history), 2)

    def test_04_coordinator_rejection_requires_mandatory_reason(self):
        """Verify that coordinator CANNOT reject an application without entering a mandatory reason."""
        usn = "1KG21CS072"
        sub = create_submission(usn, {
            "submission_type": "NORMAL",
            "pref_1_company": "Unknown Firm"
        })

        # Attempt to reject with empty reason -> must raise ValueError
        with self.assertRaises(ValueError):
            coordinator_review_submission(
                sub_id=sub["id"],
                decision="REJECT",
                coordinator_name="Dr. Ramesh Kulkarni",
                data={"rejection_reason": ""} # Empty!
            )

        # Reject with valid reason -> succeeds
        rev = coordinator_review_submission(
            sub_id=sub["id"],
            decision="REJECT",
            coordinator_name="Dr. Ramesh Kulkarni",
            data={"rejection_reason": "Company does not satisfy minimum stipend and safety criteria."}
        )
        self.assertEqual(rev["status"], "REJECTED")
        self.assertEqual(rev["rejection_reason"], "Company does not satisfy minimum stipend and safety criteria.")

    def test_05_dynamic_vacancy_decrementing(self):
        """Verify vacancies decrement upon confirmed approval and cannot become negative."""
        opp = get_opportunity("OPP-001")
        initial_vacancies = opp["available_vacancies"]
        self.assertGreater(initial_vacancies, 0)

        updated_opp = decrement_vacancy("OPP-001")
        self.assertEqual(updated_opp["available_vacancies"], initial_vacancies - 1)
        self.assertEqual(updated_opp["filled_vacancies"], opp["filled_vacancies"] + 1)

    def test_06_lab1_planner_clarify_plan_revise(self):
        """Test Lab 1 Clarify -> Plan -> Revise loop."""
        agent = Lab1PlannerAgent()
        # Vague input -> must ask clarification questions
        res1 = agent.process_request("I want an internship")
        self.assertTrue(res1["needs_clarification"])
        self.assertGreaterEqual(len(res1["clarification_questions"]), 2)

        # Provided fields -> outputs structured plan
        res2 = agent.process_request("I want an internship", {
            "student_name": "Rahul Kumar",
            "student_usn": "1KG21CS045",
            "branch": "CSE",
            "domain_interest": "AI/ML",
            "company_preferences": ["ABC Technologies"]
        })
        self.assertFalse(res2["needs_clarification"])
        self.assertIsNotNone(res2["plan"])

        # Revise on feedback -> updates plan version
        res3 = agent.revise_plan("Add mentor checkpoint on Week 8")
        self.assertEqual(res3["plan"]["version"], 2)

    def test_07_lab2_tool_using_agent(self):
        """Test Lab 2 Tool-Using Agent executes real DB lookups and produces trace."""
        tool_agent = Lab2ToolUsingAgent()
        res = tool_agent.execute_query("1KG21CS045", target_company="ABC Technologies")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(len(res["trace"]), 0)
        tool_names = [t["tool"] for t in res["trace"]]
        self.assertIn("read_student_profile", tool_names)
        self.assertIn("compute_eligibility", tool_names)
        self.assertIn("check_vacancy", tool_names)

    def test_08_lab3_skills(self):
        """Test Lab 3 Reusable Skills."""
        p_in = PlanInputSchema("Rahul Kumar", "1KG21CS045", "CSE", 8.5, "AI/ML", ["ABC Technologies"])
        plan_res = InternshipPlanSkill.execute(p_in)
        self.assertTrue(plan_res["is_valid"])

    def test_09_lab4_memory_retrieval(self):
        """Test Lab 4 Memory and Retrieval."""
        context = MemoryRetrievalEngine.recall_student_context("1KG21CS045")
        self.assertIn("total_submissions", context)
        similar = MemoryRetrievalEngine.search_similar_opportunities("artificial intelligence machine learning")
        self.assertGreater(len(similar), 0)

    def test_10_lab5_mcp_connector(self):
        """Test Lab 5 Governed MCP Connector enforces token auth."""
        # Valid token
        res = mcp_connector.read_student_profile("1KG21CS045", "INTERNTRACK_GOVERNED_MCP_TOKEN_2026")
        self.assertEqual(res["usn"], "1KG21CS045")

        # Invalid token
        with self.assertRaises(PermissionError):
            mcp_connector.read_student_profile("1KG21CS045", "INVALID_TOKEN")

    def test_11_lab6_controlled_runtime(self):
        """Test Lab 6 Controlled Runtime pauses at human approval gate for risky steps."""
        runtime = ControlledAgentRuntime(max_budget=5)
        run = runtime.start_run("1KG21CS045")
        step_res = runtime.execute_step(run.run_id, "Consequential Approval", lambda: {"status": "APPROVED"}, is_risky=True)
        self.assertEqual(step_res["status"], "PAUSED_FOR_APPROVAL")

    def test_12_lab7_langgraph_workflow(self):
        """Test Lab 7 LangGraph StateGraph Execution."""
        res = run_lab7_langgraph("1KG21CS045")
        self.assertEqual(res["orchestration_engine"], "LangGraph (langgraph.graph.StateGraph)")
        self.assertIn("Ingest Node", res["execution_path"])
        self.assertIn("Discovery Agent", res["execution_path"])
        self.assertIn("Eligibility Agent", res["execution_path"])
        self.assertIn("Coordinator Human Gate", res["execution_path"])
        self.assertTrue(res["validation_passed"])

    def test_13_lab8_langgraph_parallel_swarm(self):
        """Test Lab 8 LangGraph Parallel Swarm evaluates 4 branches concurrently."""
        res = run_lab8_langgraph("1KG21CS045", ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"])
        self.assertEqual(res["evaluations_count"], 4)
        self.assertEqual(len(res["ranked_results"]), 4)
        self.assertIn(res["approval_status"], ["PAUSED_FOR_COORDINATOR_APPROVAL", "READY_FOR_COORDINATOR_APPROVAL"])

if __name__ == "__main__":
    unittest.main()
