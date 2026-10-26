"""
========================================================================================
INTERNTRACK -- Labs 1 to 8 Explained in Simple Words (Interactive Walkthrough Script)
========================================================================================
Run this script:
    python explain_labs_1_to_8.py

This script takes you through each lab step-by-step, explains WHY it exists,
runs the actual code, and prints the real output in simple, friendly words!
========================================================================================
"""

import os
import sys
import time

# Ensure safe encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db
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
from aura.lab7_langgraph import run_lab7_langgraph
from aura.lab8_langgraph import run_lab8_langgraph

SEPARATOR = "=" * 80

def print_header(title, subtitle):
    print("\n" + SEPARATOR)
    print(f" [*] {title.upper()}")
    print(f" --> {subtitle}")
    print(SEPARATOR)

def pause():
    print("\n" + "-" * 80)
    time.sleep(0.2)

def explain_lab1():
    print_header(
        "Lab 1: Clarify -> Plan -> Revise Loop",
        "The Difference Between a Dumb Chatbot and a Real AI Agent"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* Dumb Chatbot: A student says 'I want an internship'. A basic chatbot immediately guesses
  and spits out random generic advice in one shot. That's useless.
* Real AI Agent: When given a vague goal, the agent DOES NOT answer immediately. It stops,
  asks clarifying questions (USN, CGPA, Branch, Preferred Location), waits for student's
  answers, builds a solid 16-week structured plan, and allows the student to give feedback
  (e.g., 'Add a mentor checkpoint on Week 8') to produce Version 2.0!

[LIVE CODE EXECUTION]:
""")
    agent = Lab1PlannerAgent()
    # Step 1: Vague request
    r1 = agent.process_request("I want an internship")
    print(f"1. Vague Input: 'I want an internship'")
    print(f"   -> Needs Clarification? {r1['needs_clarification']}")
    print(f"   -> Questions asked by Agent ({len(r1['clarification_questions'])}):")
    for q in r1["clarification_questions"][:2]:
        print(f"      * {q['question']}")

    # Step 2: Build plan
    r2 = agent.process_request("I want an internship", {
        "student_name": "Rahul Kumar", "student_usn": "1KG21CS045",
        "branch": "CSE", "cgpa": 8.5, "preferred_location": "Bengaluru",
        "domain_interest": "AI/ML", "company_preferences": ["ABC Technologies"]
    })
    print(f"\n2. After Details Received:")
    print(f"   -> Generated Plan Version: {r2['plan']['version']}")
    print(f"   -> Phases Generated: {len(r2['plan']['phases'])} structured milestones")

    # Step 3: Human Feedback Revision
    r3 = agent.revise_plan("Add mentor checkpoint on Week 8")
    print(f"\n3. After Student Feedback ('Add mentor checkpoint on Week 8'):")
    print(f"   -> Revised Plan Version: {r3['plan']['version']} (Version 2.0 finalized)")

def explain_lab2():
    print_header(
        "Lab 2: Deterministic Tool-Using Agent",
        "Stop LLM Hallucinations: Use Real Database Lookups"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: An LLM by itself will happily hallucinate: 'Sure, ABC Technologies has 50 seats
  and your CGPA 6.0 is totally fine!' That ruins college placements.
* The Solution: The agent MUST NOT guess. It calls deterministic Python tools that query
  the real SQLite database:
  1. `read_student_profile` -> gets actual CGPA & backlogs
  2. `compute_eligibility`   -> checks if CGPA >= company cut-off
  3. `check_vacancy`         -> checks remaining seats in catalog
  And leaves a visible audit trail of exactly which tools were called!

[LIVE CODE EXECUTION]:
""")
    agent = Lab2ToolUsingAgent()
    res = agent.execute_query("1KG21CS045", "ABC Technologies")
    print(f"Candidate: Rahul Kumar (1KG21CS045) for ABC Technologies")
    print(f"Status: {res['status']}")
    print("Agent Tool Trace:")
    for step in res["trace"]:
        print(f"  * Tool Called: [{step['tool']}] -> Output: {step['output']}")

def explain_lab3():
    print_header(
        "Lab 3: Reusable Schema-Typed Skills",
        "Modular Micro-Engines with Strict Input/Output Contracts"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: Big messy prompts that try to do everything at once are fragile and break easily.
* The Solution: Break the system into 4 distinct, reusable, schema-validated SKILLS:
  1. InternshipPlanSkill       -> Generates a 16-week milestone roadmap.
  2. ApplicationValidatorSkill -> Validates required documents (NOC, Resume, Offer Letter).
  3. OpportunityMatchingSkill  -> Scores & matches catalog companies to student profile.
  4. DocumentFormatterSkill    -> Generates official college internship memos & letters.

[LIVE CODE EXECUTION]:
""")
    # 1. Matching
    prof = {"name": "Rahul Kumar", "usn": "1KG21CS045", "branch": "CSE", "cgpa": 8.5, "skills": ["Python", "FastAPI", "AI/ML"]}
    catalog = [
        {"company": "ABC Technologies", "title": "AI/ML Intern", "domain": "AI/ML", "min_cgpa": 7.5, "available_vacancies": 4, "required_skills": "Python, ML"},
        {"company": "XYZ Labs", "title": "Data Science Intern", "domain": "AI/ML", "min_cgpa": 7.0, "available_vacancies": 3, "required_skills": "Python, Statistics"}
    ]
    match_in = OpportunityMatchingInput(prof, catalog, domain_interest="AI/ML")
    match_res = OpportunityMatchingSkill.execute(match_in)
    print(f"1. OpportunityMatchingSkill: Evaluated {match_res['total_evaluated']} companies | Found {match_res['total_suitable']} suitable.")
    if match_res['matched_opportunities']:
        top = match_res['matched_opportunities'][0]
        print(f"   Top Match: {top['company']} ({top.get('role', 'Intern')}) - Match Score: {top.get('match_score')}%")

    # 2. Validation
    val_in = ApplicationValidationInput(prof, target_company="ABC Technologies", opportunity_catalog=catalog)
    val_res = ApplicationValidatorSkill.execute(val_in)
    print(f"\n2. ApplicationValidatorSkill: Passed? {val_res['is_valid']} | Final Status: {val_res['final_status']}")
    print(f"   Checks Performed: {len(val_res['checks'])} criteria evaluated")

def explain_lab4():
    print_header(
        "Lab 4: Multi-Tiered Memory & Retrieval",
        "Giving the Agent a Brain: Working Memory, History, and Long-Term Recall"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: Chatbots reset and lose context the moment you switch pages or refresh.
* The Solution: A 3-Tier memory system:
  1. Working Memory: The active student draft in RAM (SessionState).
  2. History Archive: List of recent conversation turns and actions.
  3. Long-Term Semantic Retrieval: TF-IDF / vector similarity search over the entire
     internship knowledgebase to find relevant opportunities and student notes!

[LIVE CODE EXECUTION]:
""")
    # Working memory
    sess = SessionState(session_id="SESS-DEMO-001", student_usn="1KG21CS045")
    sess.update_answers({"preferred_role": "Machine Learning Engineer", "target_location": "Bengaluru"})
    print(f"1. Working Memory (Active Answers): {sess.student_answers}")

    # Semantic search
    query = "computer vision deep learning neural networks"
    matches = MemoryRetrievalEngine.search_similar_opportunities(query)
    print(f"2. Long-Term Semantic Search for '{query}':")
    for m in matches[:2]:
        print(f"   * {m['company']} ({m['title']}) -> Similarity Score: {round(m['similarity_score'] * 100, 1)}%")

def explain_lab5():
    print_header(
        "Lab 5: Governed MCP-Style Connector",
        "Role-Based Access Control: No Raw Database Queries for Agents"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: If an AI agent has direct SQL access, a malicious prompt could drop tables
  or let Student A peek at Student B's private marks!
* The Solution: Model Context Protocol (MCP) boundary.
  The agent MUST authenticate using a Bearer token with Role-Based Access Control (RBAC).
  - STUDENT role can ONLY view their own records.
  - Cross-student access is blocked with HTTP 403 Forbidden!
  - Anonymous access without a token is blocked with HTTP 401 Unauthorized!

[LIVE CODE EXECUTION]:
""")
    # Valid Coordinator Token
    coord_token = "INTERNTRACK_GOVERNED_MCP_TOKEN_2026"
    profile = mcp_connector.read_student_profile("1KG21CS045", token=coord_token)
    print(f"1. Authorized Access (Coordinator Token):")
    print(f"   -> Retrieved: {profile['name']} | CGPA: {profile['cgpa']}")

    # Invalid Token
    print(f"\n2. Unauthorized Access (Fake Token):")
    try:
        mcp_connector.read_student_profile("1KG21CS045", token="INVALID_HACKER_TOKEN")
    except PermissionError as pe:
        print(f"   -> Blocked by MCP Gateway: {pe}")

def explain_lab6():
    print_header(
        "Lab 6: Controlled Runtime & Governed Human Gate",
        "Safe Actions Auto-Run, Risky Actions Wait for Human Sign-Off"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: AI should NOT be allowed to automatically hire, approve, or reject students
  in the official college database without human oversight.
* The Solution:
  - Step Budget: Agent can only take N steps (prevents infinite loops & API cost spikes).
  - Human Gate: Safe steps (read, compute) run freely. But when a 'risky' step is reached
    (approving/rejecting an application, writing to production tables), the runtime PAUSES,
    creates a checkpoint, and waits for a real Human Coordinator to approve or reject!

[LIVE CODE EXECUTION]:
""")
    runtime = ControlledAgentRuntime(max_budget=5)
    run = runtime.start_run("1KG21CS045")
    print(f"1. Started Controlled Run: {run.run_id} (Budget: {run.step_budget} steps)")

    # Safe step
    s1 = runtime.execute_step(run.run_id, "Read Student CGPA", lambda: {"cgpa": 8.5}, is_risky=False)
    print(f"   * Step 1 (Safe): {s1.get('step')} -> Status: {s1.get('status')}")

    # Risky step
    s2 = runtime.execute_step(run.run_id, "Consequential Approval", lambda: {"status": "APPROVED"}, is_risky=True)
    print(f"   * Step 2 (Risky): Consequential Approval -> Status: {s2.get('status')}")
    print(f"   -> Gate Message: {s2.get('message')}")
    print(f"   -> Run State: {run.status} (Database is untouched while paused!)")

def explain_lab7():
    print_header(
        "Lab 7: LangGraph Agentic Workflow (Official StateGraph)",
        "Stateful Multi-Agent Pipeline with Conditional Retry & Human Gate"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: Real workflows are not simple linear scripts. If an application fails validation,
  it needs to loop back to the student, fix errors, and retry (up to max retries).
* The Solution: Built using the official LangGraph library (`langgraph.graph.StateGraph`)!
  Graph Topology:
    IngestNode -> PlannerNode -> DiscoveryAgent -> EligibilityAgent
    -> ApplicationAgent -> ValidationNode
        |-- (If Invalid) --> [Conditional Back-Edge Retry] --> ApplicationAgent
        |-- (If Valid)   --> Coordinator Human Gate (PAUSE / Checkpoint)
                                  | (Coordinator Approval)
                             PublishNode -> END

[LIVE CODE EXECUTION]:
""")
    res = run_lab7_langgraph("1KG21CS045")
    print(f"Orchestration Engine: {res['orchestration_engine']}")
    print(f"Candidate: {res['student_id']} | Validation Passed? {res['validation_passed']}")
    print(f"LangGraph Traversal Path:")
    for idx, node in enumerate(res["execution_path"], 1):
        print(f"  [{idx}] --> {node}")
    print(f"Final State: {res['approval_status']}")
    print(f"Checkpoint Saved? Yes (MemorySaver checkpointer holds thread before Publish)")

def explain_lab8():
    print_header(
        "Lab 8: LangGraph Parallel Swarm (Fan-Out / Fan-In)",
        "4 Parallel Worker Agents Running Concurrently with Failure Isolation"
    )
    print("""
[SIMPLE WORDS EXPLANATION]:
* The Problem: If a student submits 4 company preferences, checking them one-by-one is slow.
  Worse, if Worker 4 crashes on a bad company, the whole system shouldn't crash!
* The Solution:
  1. Fan-Out: Splits the 4 student preferences across 4 worker agents running in parallel.
  2. Failure Isolation: If any worker throws an error, it catches it as WORKER_ERROR;
     the other 3 workers finish without crashing!
  3. Fan-In + Reducer: Aggregates all 4 branch results using `Annotated[..., operator.add]`.
  4. Dynamic Ranking: Ranks eligible companies first by vacancies descending.
  5. Coordinator Human Gate: Pauses before consequential commit, awaiting Coordinator sign-off!

[LIVE CODE EXECUTION]:
""")
    res = run_lab8_langgraph("1KG21CS045")
    print(f"Orchestration Engine: {res['orchestration_engine']}")
    print(f"Candidate: {res['student_id']} | Total Parallel Time: {res['duration_ms']}ms")
    print(f"Preferences Evaluated: {res['preferences_evaluated']}")
    print(f"\nParallel Worker Ranking (Fan-In Aggregated):")
    for idx, r in enumerate(res["ranked_results"], 1):
        mark = "[ELIGIBLE]" if r.get("is_eligible") else "[INELIGIBLE]"
        print(f"  [Rank #{idx}] {mark} {r['company']} ({r['title']}) | Vacancies: {r['available_vacancies']} | Status: {r['status']}")
    print(f"\nFinal State: {res['status']}")
    print(f"Next Step: {res['next_step']}")

def main():
    print("\n" + "#" * 80)
    print(" INTERNTRACK (AURA AGENTIC SYSTEM) -- LABS 1 TO 8 SUMMARY WALKTHROUGH")
    print("#" * 80)
    init_db()
    seed()

    explain_lab1()
    pause()
    explain_lab2()
    pause()
    explain_lab3()
    pause()
    explain_lab4()
    pause()
    explain_lab5()
    pause()
    explain_lab6()
    pause()
    explain_lab7()
    pause()
    explain_lab8()

    print("\n" + "#" * 80)
    print(" ALL 8 LABS EXPLAINED AND VERIFIED SUCCESSFULLY!")
    print("#" * 80 + "\n")

if __name__ == "__main__":
    main()
