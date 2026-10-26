"""
INTERNTRACK -- Complete Labs 1 to 9 Verification for Student 'Anam' Joining TCS
================================================================================
Student: Anam (USN: 1KG21CS050)
Target Company: Tata Consultancy Services (TCS) (OPP-007)
Domain: Research & Innovation Intern

Verifies all 9 Labs sequentially for student Anam:
- Lab 1: Planner Agent (Clarify -> Plan -> Revise Loop)
- Lab 2: Deterministic Tool-Using Agent (Real DB lookup, no hallucination)
- Lab 3: Reusable Schema-Typed Skills (Matching, Validation, Plan, Docs)
- Lab 4: Multi-Tiered Memory (Working memory session + Semantic retrieval)
- Lab 5: Governed MCP-Style Connector (Role-based access token gate)
- Lab 6: Controlled Agent Runtime (Step budget & Human Coordinator Gate)
- Lab 7: Official LangGraph StateGraph Pipeline (Conditional retry & Human Checkpoint)
- Lab 8: LangGraph Parallel Swarm (Fan-out / Fan-in with failure isolation)
- Lab 9: Deep Research & Evidence Grounding (Cited Faculty Rubric, Evidence Table)
================================================================================
"""

import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db, query_one
from database.seed_data import seed
from aura.lab1_planner import Lab1PlannerAgent
from aura.lab2_tools import Lab2ToolUsingAgent
from aura.lab3_skills import (
    InternshipPlanSkill, ApplicationValidatorSkill, 
    OpportunityMatchingSkill, DocumentFormatterSkill,
    PlanInputSchema, ApplicationValidationInput,
    OpportunityMatchingInput, DocumentFormatterInput
)
from aura.lab4_memory import SessionState, MemoryRetrievalEngine
from aura.lab5_connector import mcp_connector
from aura.lab6_runtime import ControlledAgentRuntime
from aura.lab7_langgraph import run_lab7_langgraph, approve_lab7_langgraph
from aura.lab8_langgraph import run_lab8_langgraph, approve_lab8_langgraph
from aura.lab9_grounding import run_lab9_deep_research

SEPARATOR = "=" * 80

def test_anam_all_labs():
    print("\n" + SEPARATOR)
    print(" [START] TESTING ALL LABS (1 TO 9) FOR STUDENT 'ANAM' JOINING 'TCS'")
    print(SEPARATOR)

    # 0. Ensure DB has Anam and TCS
    init_db()
    seed()

    anam_profile = query_one("SELECT * FROM student_profiles WHERE usn = '1KG21CS050'")
    tcs_opp = query_one("SELECT * FROM opportunities WHERE id = 'OPP-007'")

    assert anam_profile is not None, "Error: Anam profile not found in database!"
    assert tcs_opp is not None, "Error: TCS opportunity not found in database!"

    print(f"\n[STUDENT VERIFIED IN DATABASE]:")
    print(f"  Name: {anam_profile['name']} | USN: {anam_profile['usn']}")
    print(f"  Branch: {anam_profile['branch']} | Semester: {anam_profile['semester']}")
    print(f"  CGPA: {anam_profile['cgpa']} | Backlogs: {anam_profile['backlogs']}")
    print(f"  Skills: {anam_profile['skills']}")

    print(f"\n[TARGET COMPANY VERIFIED IN DATABASE]:")
    print(f"  Company: {tcs_opp['company']} ({tcs_opp['id']})")
    print(f"  Role: {tcs_opp['title']}")
    print(f"  Min CGPA Cutoff: {tcs_opp['min_cgpa']} | Available Seats: {tcs_opp['available_vacancies']}")
    print(f"  Monthly Stipend: Rs. {tcs_opp['stipend_monthly']:,.2f}")

    # ---------------------------------------------------------
    # LAB 1: Clarify -> Plan -> Revise
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 1] Clarify -> Plan -> Revise Loop for Anam")
    print("-" * 80)
    agent1 = Lab1PlannerAgent()
    vague_res = agent1.process_request("I want to do an internship at TCS")
    print(f"1. Vague Input: Needs Clarification? {vague_res['needs_clarification']}")
    print(f"   Agent asked {len(vague_res['clarification_questions'])} questions (e.g. '{vague_res['clarification_questions'][0]['question']}')")

    anam_inputs = {
        "student_name": anam_profile["name"],
        "student_usn": anam_profile["usn"],
        "branch": anam_profile["branch"],
        "cgpa": anam_profile["cgpa"],
        "preferred_location": "Bengaluru",
        "domain_interest": "Research & Innovation",
        "company_preferences": ["Tata Consultancy Services (TCS)"]
    }
    plan_res = agent1.process_request("Internship application", anam_inputs)
    print(f"2. After Clarification: Generated Plan Version {plan_res['plan']['version']} with {len(plan_res['plan']['phases'])} phases")

    revised_res = agent1.revise_plan("Include a checkpoint for TCS research paper draft on Week 12")
    print(f"3. After Feedback: Plan Revised to Version {revised_res['plan']['version']} (Finalized)")
    assert str(revised_res["plan"]["version"]).startswith("2"), "Lab 1 failed to bump version"
    print(" [PASS] Lab 1 Passed!")

    # ---------------------------------------------------------
    # LAB 2: Deterministic Tool-Using Agent
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 2] Deterministic Tool-Using Agent for Anam & TCS")
    print("-" * 80)
    agent2 = Lab2ToolUsingAgent()
    res2 = agent2.execute_query(
        anam_profile["usn"],
        query_type="CHECK_ELIGIBILITY",
        target_company="Tata Consultancy Services (TCS)"
    )
    print(f"Status: {res2['status']}")
    print(f"Answer: {res2['answer']}")
    print("Deterministic Tool Trace:")
    for step in res2["trace"]:
        print(f"  * Tool: {step['tool']} -> Output: {step['output']}")
    assert "IS ELIGIBLE" in res2["answer"], "Lab 2 Anam should be eligible for TCS"
    print(" [PASS] Lab 2 Passed!")

    # ---------------------------------------------------------
    # LAB 3: Reusable Schema-Typed Skills
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 3] Reusable Schema-Typed Skills")
    print("-" * 80)
    prof_dict = {
        "name": anam_profile["name"],
        "usn": anam_profile["usn"],
        "branch": anam_profile["branch"],
        "cgpa": anam_profile["cgpa"],
        "backlogs": anam_profile["backlogs"],
        "skills": json.loads(anam_profile["skills"])
    }
    catalog_list = [dict(tcs_opp)]
    
    # 1. Matching Skill
    m_in = OpportunityMatchingInput(prof_dict, catalog_list, domain_interest="Research & Innovation")
    m_out = OpportunityMatchingSkill.execute(m_in)
    print(f"1. OpportunityMatchingSkill: Evaluated {m_out['total_evaluated']} opps | Suitable: {m_out['total_suitable']}")
    top_match = m_out["matched_opportunities"][0]
    print(f"   Top Match: {top_match['company']} - Match Score: {top_match['match_score']}%")

    # 2. Validation Skill
    v_in = ApplicationValidationInput(prof_dict, target_company="Tata Consultancy Services (TCS)", opportunity_catalog=catalog_list)
    v_out = ApplicationValidatorSkill.execute(v_in)
    print(f"2. ApplicationValidatorSkill: Passed? {v_out['is_valid']} | Status: {v_out['final_status']}")

    # 3. Document Formatter Skill
    doc_in = DocumentFormatterInput(
        student_profile=prof_dict,
        selected_opportunity=dict(tcs_opp),
        preferences=["Tata Consultancy Services (TCS)"],
        submission_info={
            "submission_version": 1,
            "coordinator_id": "Dr. Ramesh Kulkarni",
            "hod_status": "APPROVED",
            "created_at": "2026-10-26"
        }
    )
    doc_out = DocumentFormatterSkill.execute(doc_in)
    print(f"3. DocumentFormatterSkill: Generated Official Letter ({len(doc_out.get('content', ''))} chars)")
    assert v_out["is_valid"] is True, "Lab 3 validation failed"
    print(" [PASS] Lab 3 Passed!")

    # ---------------------------------------------------------
    # LAB 4: Multi-Tiered Memory & Retrieval
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 4] Multi-Tiered Memory & Semantic Retrieval")
    print("-" * 80)
    sess = SessionState(session_id="SESS-ANAM-001", student_usn=anam_profile["usn"])
    sess.update_answers({"target_company": "Tata Consultancy Services (TCS)", "domain": "Research & Innovation"})
    print(f"1. Working Memory: {sess.student_answers}")

    query = "Tata Consultancy Services research innovation systems machine learning"
    sem_matches = MemoryRetrievalEngine.search_similar_opportunities(query)
    print(f"2. Semantic Retrieval for '{query}':")
    for m in sem_matches[:3]:
        print(f"   * {m['company']} ({m['title']}) -> Similarity: {round(m['similarity_score'] * 100, 1)}%")
    assert len(sem_matches) > 0, "Lab 4 semantic search returned empty"
    print(" [PASS] Lab 4 Passed!")

    # ---------------------------------------------------------
    # LAB 5: Governed MCP Connector
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 5] Governed MCP Connector (RBAC & Security Gate)")
    print("-" * 80)
    coord_token = "INTERNTRACK_GOVERNED_MCP_TOKEN_2026"
    mcp_prof = mcp_connector.read_student_profile(anam_profile["usn"], token=coord_token)
    print(f"1. Authorized Access (Coordinator Token): Retrieved {mcp_prof['name']} (CGPA {mcp_prof['cgpa']})")

    try:
        mcp_connector.read_student_profile(anam_profile["usn"], token="BAD_UNAUTHORIZED_TOKEN")
        assert False, "Unauthorized token should fail"
    except PermissionError as pe:
        print(f"2. Security Gate Check: Blocked unauthorized token successfully ({pe})")
    print(" [PASS] Lab 5 Passed!")

    # ---------------------------------------------------------
    # LAB 6: Controlled Runtime & Human Gate
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 6] Controlled Runtime & Human Coordinator Gate")
    print("-" * 80)
    runtime = ControlledAgentRuntime(max_budget=5)
    run = runtime.start_run(anam_profile["usn"])
    print(f"1. Run Started: {run.run_id} (Budget: {run.step_budget})")

    # Safe step
    s1 = runtime.execute_step(run.run_id, "Check Eligibility", lambda: {"cgpa": 8.8, "eligible": True}, is_risky=False)
    print(f"2. Safe Step Status: {s1['status']}")

    # Risky step
    s2 = runtime.execute_step(run.run_id, "Allot TCS Internship", lambda: {"status": "ALLOTTED"}, is_risky=True)
    print(f"3. Risky Step: Paused at Gate? {s2['status'] == 'PAUSED_FOR_APPROVAL'}")
    print(f"   Message: {s2.get('message')}")
    assert s2["status"] == "PAUSED_FOR_APPROVAL", "Lab 6 risky step did not pause"
    print(" [PASS] Lab 6 Passed!")

    # ---------------------------------------------------------
    # LAB 7: Official LangGraph StateGraph Pipeline
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 7] LangGraph StateGraph Workflow Pipeline")
    print("-" * 80)
    l7_res = run_lab7_langgraph(
        student_usn=anam_profile["usn"],
        preferences=["Tata Consultancy Services (TCS)"]
    )
    print(f"Orchestration Engine: {l7_res['orchestration_engine']}")
    print(f"Run ID: {l7_res['run_id']}")
    print(f"Validation Passed: {l7_res.get('validation_passed')}")
    print(f"Paused for Coordinator Approval: {l7_res['approval_status']}")
    print("Execution Path Traversed:")
    for idx, node in enumerate(l7_res["execution_path"], 1):
        print(f"  [{idx}] -> {node}")
    
    # Coordinator approves the run
    l7_approved = approve_lab7_langgraph(l7_res["run_id"], coordinator_name="Dr. Ramesh Kulkarni")
    print(f"Coordinator Decision: {l7_approved['status']} -> Final Approval Status: {l7_approved['approval_status']}")
    assert l7_approved["status"] == "HUMAN_APPROVAL_GRANTED", "Lab 7 approval commit failed"
    print(" [PASS] Lab 7 Passed!")

    # ---------------------------------------------------------
    # LAB 8: LangGraph Parallel Swarm (Fan-Out / Fan-In)
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 8] LangGraph Parallel Swarm (4 Parallel Worker Agents)")
    print("-" * 80)
    l8_res = run_lab8_langgraph(
        student_usn=anam_profile["usn"],
        preferences=[
            "Tata Consultancy Services (TCS)",
            "Infosys Limited",
            "Google India",
            "Bosch Global Software Technologies"
        ]
    )
    print(f"Orchestration Engine: {l8_res['orchestration_engine']}")
    print(f"Preferences Evaluated: {l8_res['preferences_evaluated']} in {l8_res['duration_ms']}ms")
    print("Parallel Worker Ranking (Fan-In Aggregated):")
    for idx, r in enumerate(l8_res["ranked_results"], 1):
        mark = "[ELIGIBLE]" if r.get("is_eligible") else "[INELIGIBLE]"
        print(f"  [Rank #{idx}] {mark} {r['company']} ({r['title']}) | Vacancies: {r['available_vacancies']}")

    # Coordinator commits allotment
    l8_approved = approve_lab8_langgraph(l8_res["run_id"], coordinator_name="Dr. Ramesh Kulkarni")
    print(f"Coordinator Decision: {l8_approved['status']} -> Final Status: {l8_approved['approval_status']}")
    assert l8_approved["status"] == "HUMAN_APPROVAL_GRANTED", "Lab 8 approval commit failed"
    print(" [PASS] Lab 8 Passed!")

    # ---------------------------------------------------------
    # LAB 9: Deep Research & Evidence Grounding
    # ---------------------------------------------------------
    print("\n" + "-" * 80)
    print(">>> [LAB 9] Deep Research & Evidence Grounding (Cited Faculty Rubric)")
    print("-" * 80)
    l9_res = run_lab9_deep_research(
        student_usn=anam_profile["usn"],
        candidates=["Tata Consultancy Services (TCS)"]
    )
    print(f"Total Evaluated: {l9_res['total_evaluated']}")
    print(f"Grounding Status: {l9_res['status']}")
    print(f"Accepted Candidates Count: {l9_res['accepted_count']}")
    print(f"Rejected Candidates Count: {l9_res['rejected_count']}")
    print(f"Pitfall Avoided: {l9_res['pitfall_avoided']}")
    
    table = l9_res["evidence_table"]
    print(f"\nEvidence Table (Overall Verdict: {table.get('overall_verdict')} | Grounding Rate: {table.get('grounding_rate_pct')}%):")
    for r in table.get("records", []):
        print(f"  * Unit: {r['unit_id']} | Candidate: {r['candidate_name']} | Status: {r['verification_status']}")
        print(f"    Source: {r['source_title']} (Rule: {r['rubric_rule_cited']})")
        print(f"    Citation: {r['source_citation']}")
        print(f"    Evidence: {r['evidence_text']}")

    assert l9_res["accepted_count"] >= 1, "Lab 9 Anam should be accepted for TCS"
    assert table.get("overall_verdict") in ["ALL_GROUNDED", "GROUNDED_COMPLIANT"], "Lab 9 overall verdict not compliant"
    print(" [PASS] Lab 9 Passed!")

    print("\n" + SEPARATOR)
    print(" [SUCCESS] ALL LABS (1 TO 9) FULLY PASSED AND VERIFIED FOR ANAM JOINING TCS!")
    print(SEPARATOR + "\n")

if __name__ == "__main__":
    test_anam_all_labs()
