"""
INTERNTRACK — Central AURA Coordinator Orchestrator
Coordinates Labs 1-8 capabilities, chat interface, and LangGraph pipelines.
"""

from aura.lab1_planner import Lab1PlannerAgent
from aura.lab2_tools import Lab2ToolUsingAgent
from aura.lab3_skills import InternshipPlanSkill, ApplicationValidatorSkill, OpportunityMatchingSkill, DocumentFormatterSkill, PlanInputSchema
from aura.lab4_memory import SessionState, MemoryRetrievalEngine
from aura.lab5_connector import mcp_connector
from aura.lab6_runtime import ControlledAgentRuntime
from aura.lab7_langgraph import run_lab7_langgraph
from aura.lab8_langgraph import run_lab8_langgraph
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities

planner_agent = Lab1PlannerAgent()
tool_agent = Lab2ToolUsingAgent()
runtime_engine = ControlledAgentRuntime(max_budget=10)

def handle_aura_chat(message: str, student_usn: str = "1KG21CS045"):
    """
    Main conversational endpoint for AURA Assistant.
    Seamlessly combines Lab 1 (Planning loop) and Lab 2 (Tool lookups with visible trace).
    """
    msg_lower = message.lower()

    # If asking for factual lookups or eligibility -> Tool-Using Agent (Lab 2)
    if any(k in msg_lower for k in ["eligible", "vacancy", "vacancies", "check", "status", "opportunity"]):
        target_company = "ABC Technologies"
        for comp in ["abc technologies", "xyz labs", "pqr solutions", "def ai", "globaltech"]:
            if comp in msg_lower:
                target_company = comp.title()
                break
        res = tool_agent.execute_query(student_usn, query_type="CHECK_ELIGIBILITY", target_company=target_company)
        return {
            "mode": "TOOL_AGENT",
            "reply": res["answer"],
            "tool_trace": res["trace"],
            "execution_time_ms": res["total_execution_time_ms"]
        }

    # If expressing generic internship intent -> Goal-Driven Planner Loop (Lab 1)
    if any(k in msg_lower for k in ["want an internship", "need an internship", "internship plan", "roadmap", "help me"]):
        res = planner_agent.process_request(message, student_usn=student_usn)
        if res.get("needs_clarification"):
            q_list = "\n".join([f"• {q['question']}" for q in res["clarification_questions"]])
            reply = f"{res['message']}\n{q_list}\n\n{res.get('instruction', '')}"
        else:
            reply = f"{res['message']}\nPlan Version: {res['plan'].get('version', 1)}"
        return {
            "mode": "PLANNER",
            "reply": reply,
            "phase": res["phase"],
            "plan": res.get("plan"),
            "clarification_questions": res.get("clarification_questions"),
            "memory_badge": res.get("memory_badge")
        }

    # If providing feedback on plan
    if "feedback" in msg_lower or "add" in msg_lower or "revise" in msg_lower or "week 8" in msg_lower:
        try:
            rev_res = planner_agent.revise_plan(message, student_usn=student_usn)
            return {
                "mode": "PLANNER_REVISED",
                "reply": f"{rev_res['message']}\nMilestone added to Week 8.",
                "phase": rev_res["phase"],
                "plan": rev_res["plan"],
                "memory_badge": rev_res.get("memory_badge")
            }
        except Exception:
            pass

    # Default informative answer with student profile tool lookup
    p = get_student_profile(student_usn)
    opps = list_opportunities(status="PUBLISHED")
    return {
        "mode": "GENERAL",
        "reply": f"Hello {p['name'] if p else 'Student'}! I am AURA, your 8th-semester internship intelligence assistant. There are currently {len(opps)} active opportunities in the catalog. You can ask me to evaluate your eligibility (e.g. 'Am I eligible for ABC Technologies?'), plan your 16-week semester journey, or run the LangGraph parallel evaluation swarm.",
        "tool_trace": []
    }
