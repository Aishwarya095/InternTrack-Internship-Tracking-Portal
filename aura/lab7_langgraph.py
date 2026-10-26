"""
INTERNTRACK — Lab 7: LangGraph Agentic Workflow
Official LangGraph Implementation of Chapter 10 Worklet 10 Multi-Agent Pipeline

Graph Architecture:
START -> Ingest Node -> Planner Node -> Discovery Agent -> Eligibility Agent
      -> Application Agent -> Validation Node
          |-- FAIL (retry_count <= max_retries) -> Retry Node -> Discovery Agent (bounded retry)
          |-- FAIL (retry_count > max_retries) -> Escalation Node -> END
          |-- PASS -> Coordinator Human Gate (INTERRUPT / PAUSE) -> Publish Node -> END
"""

import time
import uuid
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities, check_eligibility_and_vacancy
from workflows.submissions import coordinator_review_submission, create_submission, get_submission_by_id
from database.db import query_one
from core.audit import log_event

class InternshipGraphState(TypedDict):
    student_id: str
    request: str
    preferences: List[str]
    student_profile: Optional[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]
    eligibility_results: List[Dict[str, Any]]
    selected_opportunities: List[Dict[str, Any]]
    application_data: Optional[Dict[str, Any]]
    validation_passed: bool
    validation_errors: List[str]
    retry_count: int
    max_retries: int
    approval_status: str
    tool_trace: List[Dict[str, Any]]
    audit_context: List[Dict[str, Any]]
    execution_path: List[str]
    run_id: Optional[str]
    submission_id: Optional[str]
    coordinator_name: Optional[str]
    rejection_reason: Optional[str]
    consequential_result: Optional[Dict[str, Any]]

# ---- LangGraph Node Implementations ----

def ingest_node(state: InternshipGraphState) -> Dict[str, Any]:
    student_usn = state["student_id"]
    profile = get_student_profile(student_usn)
    path = list(state.get("execution_path", [])) + ["Ingest Node"]
    trace = list(state.get("tool_trace", [])) + [{
        "node": "Ingest Node",
        "action": "read_student_profile",
        "usn": student_usn,
        "name": profile.get("name") if profile else "Unknown"
    }]
    return {
        "student_profile": profile,
        "execution_path": path,
        "tool_trace": trace
    }

def planner_node(state: InternshipGraphState) -> Dict[str, Any]:
    path = list(state["execution_path"]) + ["Planner Node"]
    trace = list(state["tool_trace"]) + [{
        "node": "Planner Node",
        "action": "lock_plan_schema",
        "criteria": "CGPA >= 7.0, Backlogs == 0, Credits >= 100"
    }]
    return {
        "execution_path": path,
        "tool_trace": trace
    }

def discovery_agent_node(state: InternshipGraphState) -> Dict[str, Any]:
    prefs = state.get("preferences", [])
    all_opps = list_opportunities(status="PUBLISHED")
    matched = [o for o in all_opps if any(p.lower() in o["company"].lower() for p in prefs)]
    if not matched and len(all_opps) > 0:
        matched = all_opps[:2]

    path = list(state["execution_path"]) + ["Discovery Agent"]
    trace = list(state["tool_trace"]) + [{
        "node": "Discovery Agent",
        "action": "read_opportunities",
        "matched_count": len(matched),
        "companies": [m["company"] for m in matched]
    }]
    return {
        "opportunities": matched,
        "execution_path": path,
        "tool_trace": trace
    }

def eligibility_agent_node(state: InternshipGraphState) -> Dict[str, Any]:
    usn = state["student_id"]
    opps = state.get("opportunities", [])
    results = []
    for o in opps:
        ev = check_eligibility_and_vacancy(usn, o["id"])
        results.append(ev)

    path = list(state["execution_path"]) + ["Eligibility Agent"]
    trace = list(state["tool_trace"]) + [{
        "node": "Eligibility Agent",
        "action": "compute_eligibility",
        "evaluated_count": len(results),
        "eligible_companies": [r["company"] for r in results if r["is_eligible"]]
    }]
    return {
        "eligibility_results": results,
        "execution_path": path,
        "tool_trace": trace
    }

def application_agent_node(state: InternshipGraphState) -> Dict[str, Any]:
    eligible = [r for r in state.get("eligibility_results", []) if r["is_eligible"]]
    app_data = {
        "student_usn": state["student_id"],
        "student_name": state["student_profile"].get("name") if state.get("student_profile") else "Student",
        "primary_choice": eligible[0]["company"] if eligible else None,
        "eligible_options": eligible,
        "packet_status": "DRAFT_COMPILED"
    }
    path = list(state["execution_path"]) + ["Application Agent"]
    trace = list(state["tool_trace"]) + [{
        "node": "Application Agent",
        "action": "compile_dossier",
        "primary_choice": app_data["primary_choice"]
    }]
    return {
        "application_data": app_data,
        "selected_opportunities": eligible,
        "execution_path": path,
        "tool_trace": trace
    }

def validation_node(state: InternshipGraphState) -> Dict[str, Any]:
    eligible = state.get("selected_opportunities", [])
    errors = []
    if not eligible:
        errors.append("No eligible company matches student criteria or open vacancies.")
    
    passed = len(errors) == 0
    path = list(state["execution_path"]) + ["Validation Node"]
    trace = list(state["tool_trace"]) + [{
        "node": "Validation Node",
        "validation_passed": passed,
        "errors": errors
    }]
    return {
        "validation_passed": passed,
        "validation_errors": errors,
        "execution_path": path,
        "tool_trace": trace
    }

def retry_node(state: InternshipGraphState) -> Dict[str, Any]:
    new_retry = state.get("retry_count", 0) + 1
    # On retry, expand preferences to broader catalog
    fallback_prefs = ["PQR Solutions", "GlobalTech Systems"]
    path = list(state["execution_path"]) + [f"Retry Node (Attempt {new_retry})"]
    trace = list(state["tool_trace"]) + [{
        "node": "Retry Node",
        "action": "expand_preferences",
        "new_preferences": fallback_prefs,
        "retry_attempt": new_retry
    }]
    return {
        "retry_count": new_retry,
        "preferences": fallback_prefs,
        "execution_path": path,
        "tool_trace": trace
    }

def human_gate_node(state: InternshipGraphState) -> Dict[str, Any]:
    """LangGraph Human-in-the-loop Gate: Consequential signoff step."""
    path = list(state["execution_path"]) + ["Coordinator Human Gate"]
    trace = list(state["tool_trace"]) + [{
        "node": "Coordinator Human Gate",
        "action": "pause_for_human_approval",
        "target": state["application_data"].get("primary_choice") if state.get("application_data") else None
    }]
    run_id = state.get("run_id") or f"RUN-{state['student_id']}"
    log_event(
        actor="LANGGRAPH_ORCHESTRATOR",
        actor_role="SYSTEM_AGENT",
        action="HUMAN_APPROVAL_GATE_TRIGGERED",
        record_id=run_id,
        comments=f"LangGraph execution reached Coordinator Human Gate for {state['student_id']}. Consequential publish paused awaiting human confirmation."
    )
    return {
        "approval_status": "PAUSED_FOR_COORDINATOR_APPROVAL",
        "execution_path": path,
        "tool_trace": trace
    }

def publish_node(state: InternshipGraphState) -> Dict[str, Any]:
    path = list(state["execution_path"]) + ["Publish Node"]
    trace = list(state["tool_trace"]) + [{
        "node": "Publish Node",
        "action": "publish_verified_draft",
        "status": "PUBLISHED_TO_COORDINATOR_QUEUE"
    }]

    usn = state["student_id"]
    app_data = state.get("application_data") or {}
    primary_choice = app_data.get("primary_choice")
    if not primary_choice:
        eligible = state.get("selected_opportunities", [])
        if eligible:
            primary_choice = eligible[0].get("company")
    target_company = primary_choice or "ABC Technologies"
    target_role = "AI/ML Intern"
    coord_name = state.get("coordinator_name") or "Dr. Ramesh Kulkarni"

    # Connect to canonical coordinator_review_submission workflow
    sub_id = state.get("submission_id")
    sub = None
    if sub_id:
        sub = get_submission_by_id(sub_id)
    if not sub or sub.get("status") != "SUBMITTED":
        sub = query_one(
            "SELECT * FROM student_submissions WHERE student_usn = ? AND status = 'SUBMITTED' ORDER BY submission_version DESC LIMIT 1",
            (usn,)
        )
    if not sub:
        # Create canonical submission in SUBMITTED state to commit approval upon
        sub = create_submission(
            usn,
            {
                "submission_type": "NORMAL",
                "pref_1_company": target_company,
                "pref_1_role": target_role,
                "pref_1_location": "Bangalore",
                "pref_1_remarks": "Generated via AURA Lab 7 LangGraph Pipeline."
            }
        )

    consequential_res = coordinator_review_submission(
        sub_id=sub["id"],
        decision="APPROVE",
        coordinator_name=coord_name,
        data={
            "approved_company": target_company,
            "approved_role": target_role,
            "approved_duration": "4 Months",
            "coordinator_comments": f"Approved via AURA Lab 7 LangGraph Governed Human Gate for {usn}."
        }
    )

    log_event(
        actor=coord_name,
        actor_role="COORDINATOR",
        action="HUMAN_APPROVAL_GRANTED",
        record_id=state.get("run_id") or sub["id"],
        comments=f"Coordinator approved Lab 7 LangGraph execution for {usn}. Submission {sub['id']} transitioned to COORDINATOR_APPROVED."
    )

    return {
        "approval_status": "COMPLETED",
        "execution_path": path,
        "tool_trace": trace,
        "submission_id": sub["id"],
        "consequential_result": consequential_res
    }

# ---- Conditional Routing Functions ----

def validation_condition(state: InternshipGraphState) -> str:
    if state["validation_passed"]:
        return "pass"
    if state["retry_count"] < state["max_retries"]:
        return "retry"
    return "escalate"

# ---- Build & Compile the LangGraph StateGraph with Checkpointer & Interrupt ----

lab7_checkpointer = MemorySaver()
lab7_active_runs: Dict[str, Dict[str, Any]] = {}

def build_lab7_graph(checkpointer=None):
    workflow = StateGraph(InternshipGraphState)

    # Add Nodes
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("discovery", discovery_agent_node)
    workflow.add_node("eligibility", eligibility_agent_node)
    workflow.add_node("application", application_agent_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("retry", retry_node)
    workflow.add_node("human_gate", human_gate_node)
    workflow.add_node("publish", publish_node)

    # Define Linear Edges
    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "planner")
    workflow.add_edge("planner", "discovery")
    workflow.add_edge("discovery", "eligibility")
    workflow.add_edge("eligibility", "application")
    workflow.add_edge("application", "validation")

    # Define Conditional Edge for Validation with Bounded Retry Back-Edge
    workflow.add_conditional_edges(
        "validation",
        validation_condition,
        {
            "pass": "human_gate",
            "retry": "retry",
            "escalate": END
        }
    )

    # Back-edge from retry back to discovery
    workflow.add_edge("retry", "discovery")

    # From Human Gate to Publish to END
    workflow.add_edge("human_gate", "publish")
    workflow.add_edge("publish", END)

    cp = checkpointer if checkpointer is not None else lab7_checkpointer
    compiled = workflow.compile(checkpointer=cp, interrupt_before=["publish"])

    # Safe invoke wrapper to ensure invocation without explicit config works seamlessly
    orig_invoke = compiled.invoke
    def safe_invoke(input, config=None, **kwargs):
        if config is None:
            config = {"configurable": {"thread_id": f"auto-{uuid.uuid4().hex[:8]}"}}
        elif "configurable" not in config:
            config["configurable"] = {"thread_id": f"auto-{uuid.uuid4().hex[:8]}"}
        elif "thread_id" not in config["configurable"]:
            config["configurable"]["thread_id"] = f"auto-{uuid.uuid4().hex[:8]}"
        return orig_invoke(input, config=config, **kwargs)

    compiled.invoke = safe_invoke
    return compiled

# Global compiled graph
lab7_compiled_graph = build_lab7_graph()

def run_lab7_langgraph(student_usn="1KG21CS045", preferences=None, run_id=None, submission_id=None):
    """
    Executes the compiled LangGraph pipeline for Lab 7 with genuine checkpointing & pause.
    """
    active_run_id = run_id or f"RUN-L7-{uuid.uuid4().hex[:8].upper()}"

    # Bypass enforcement: Paused run cannot be directly re-invoked
    if active_run_id in lab7_active_runs:
        current_status = lab7_active_runs[active_run_id].get("status")
        if current_status == "PAUSED_FOR_COORDINATOR_APPROVAL":
            raise RuntimeError(
                f"RUN_PAUSED_FOR_HUMAN_APPROVAL: Run '{active_run_id}' is currently paused at the Coordinator Human Gate. "
                f"Direct invocation bypass is blocked. Explicit Coordinator approval or rejection is required."
            )

    if not submission_id:
        sub = query_one(
            "SELECT id FROM student_submissions WHERE student_usn = ? AND status = 'SUBMITTED' ORDER BY submission_version DESC LIMIT 1",
            (student_usn,)
        )
        if sub:
            submission_id = sub["id"]

    initial_state: InternshipGraphState = {
        "student_id": student_usn,
        "request": "I want an 8th-semester internship.",
        "preferences": preferences or ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"],
        "student_profile": None,
        "opportunities": [],
        "eligibility_results": [],
        "selected_opportunities": [],
        "application_data": None,
        "validation_passed": False,
        "validation_errors": [],
        "retry_count": 0,
        "max_retries": 2,
        "approval_status": "INITIALIZED",
        "tool_trace": [],
        "audit_context": [],
        "execution_path": [],
        "run_id": active_run_id,
        "submission_id": submission_id,
        "coordinator_name": None,
        "rejection_reason": None,
        "consequential_result": None
    }

    log_event(
        actor="AURA_LANGGRAPH",
        actor_role="SYSTEM_AGENT",
        action="AGENT_RUN_STARTED",
        record_id=active_run_id,
        comments=f"Lab 7 LangGraph agent run started for {student_usn}."
    )

    t0 = time.time()
    config = {"configurable": {"thread_id": active_run_id}}
    final_output = lab7_compiled_graph.invoke(initial_state, config=config)
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    # Check whether the StateGraph paused before publish
    graph_state = lab7_compiled_graph.get_state(config)
    is_paused = graph_state.next == ("publish",)
    status_str = "PAUSED_FOR_COORDINATOR_APPROVAL" if is_paused else final_output.get("approval_status", "COMPLETED")

    lab7_active_runs[active_run_id] = {
        "run_id": active_run_id,
        "student_usn": student_usn,
        "submission_id": submission_id,
        "status": status_str,
        "created_at": time.time(),
        "preferences": preferences,
        "execution_path": final_output["execution_path"],
        "validation_passed": final_output["validation_passed"],
        "application_data": final_output["application_data"]
    }

    return {
        "lab": "Lab 7: LangGraph Agentic Workflow",
        "orchestration_engine": "LangGraph (langgraph.graph.StateGraph)",
        "status": status_str,
        "run_id": active_run_id,
        "student_id": student_usn,
        "student_usn": student_usn,
        "submission_id": submission_id,
        "execution_path": final_output["execution_path"],
        "validation_passed": final_output["validation_passed"],
        "approval_status": status_str,
        "application_data": final_output["application_data"],
        "tool_trace": final_output["tool_trace"],
        "duration_ms": elapsed_ms,
        "next_step": "Coordinator Approval Required before Publish Node" if is_paused else "Execution Complete"
    }

def approve_lab7_langgraph(run_id: str, coordinator_name: str = "Dr. Ramesh Kulkarni") -> Dict[str, Any]:
    """
    Resumes the SAME LangGraph checkpoint from the Coordinator Human Gate into Publish Node.
    """
    run = lab7_active_runs.get(run_id)
    if not run:
        raise ValueError(f"Run '{run_id}' not found in runtime.")

    if run.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
        raise ValueError(
            f"Run '{run_id}' is not awaiting approval (current status: '{run.get('status')}'). "
            f"Duplicate or invalid continuation rejected."
        )

    config = {"configurable": {"thread_id": run_id}}
    state_before = lab7_compiled_graph.get_state(config)
    if state_before.next != ("publish",):
        raise ValueError(f"Graph checkpoint for run '{run_id}' is not pending Publish step (next: {state_before.next}).")

    # Update state with coordinator signoff
    lab7_compiled_graph.update_state(config, {"coordinator_name": coordinator_name}, as_node="human_gate")

    # Resume the SAME LangGraph execution across the interrupted edge to publish_node
    final_output = lab7_compiled_graph.invoke(None, config=config)

    run["status"] = "COMPLETED"
    run["execution_path"] = final_output["execution_path"]
    run["coordinator_signoff"] = coordinator_name

    return {
        "status": "HUMAN_APPROVAL_GRANTED",
        "runtime_status": "COMPLETED",
        "run_id": run_id,
        "student_id": run["student_usn"],
        "student_usn": run["student_usn"],
        "coordinator_signoff": coordinator_name,
        "consequential_action": "COORDINATOR_APPROVED_SUBMISSION",
        "approval_status": "COMPLETED",
        "execution_path": final_output["execution_path"],
        "application_data": final_output.get("application_data"),
        "consequential_result": final_output.get("consequential_result"),
        "tool_trace": final_output["tool_trace"]
    }

def reject_lab7_langgraph(run_id: str, coordinator_name: str = "Dr. Ramesh Kulkarni", rejection_reason: str = None) -> Dict[str, Any]:
    """
    Terminates the paused LangGraph execution without executing Publish Node, persisting mandatory rejection reason.
    """
    run = lab7_active_runs.get(run_id)
    if not run:
        raise ValueError(f"Run '{run_id}' not found in runtime.")

    if run.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
        raise ValueError(
            f"Run '{run_id}' is not awaiting approval (current status: '{run.get('status')}'). "
            f"Duplicate or invalid continuation rejected."
        )

    if not rejection_reason or not str(rejection_reason).strip():
        raise ValueError("A mandatory rejection reason must be provided when rejecting an application.")

    reason_clean = str(rejection_reason).strip()
    config = {"configurable": {"thread_id": run_id}}

    # Terminate the graph checkpoint cleanly without executing publish_node
    lab7_compiled_graph.update_state(
        config,
        {
            "approval_status": "REJECTED_BY_COORDINATOR",
            "rejection_reason": reason_clean
        },
        as_node="publish"
    )

    # If a submission was attached, commit canonical rejection to database
    sub_id = run.get("submission_id")
    sub_rej = None
    if sub_id:
        try:
            sub_rej = coordinator_review_submission(
                sub_id=sub_id,
                decision="REJECT",
                coordinator_name=coordinator_name,
                data={"rejection_reason": reason_clean}
            )
        except Exception as e:
            print(f"Warning: submission rejection commit: {e}")

    log_event(
        actor=coordinator_name,
        actor_role="COORDINATOR",
        action="HUMAN_APPROVAL_REJECTED",
        record_id=run_id,
        comments=f"Coordinator rejected Lab 7 LangGraph execution for {run['student_usn']}. Reason: {reason_clean}"
    )

    run["status"] = "REJECTED_BY_COORDINATOR"
    run["rejection_reason"] = reason_clean
    run["coordinator_signoff"] = coordinator_name

    final_state = lab7_compiled_graph.get_state(config)

    return {
        "status": "HUMAN_APPROVAL_REJECTED",
        "runtime_status": "REJECTED_BY_COORDINATOR",
        "run_id": run_id,
        "student_id": run["student_usn"],
        "student_usn": run["student_usn"],
        "coordinator_signoff": coordinator_name,
        "rejection_reason": reason_clean,
        "consequential_action": "COORDINATOR_REJECTED_SUBMISSION",
        "approval_status": "REJECTED_BY_COORDINATOR",
        "execution_path": final_state.values.get("execution_path", []),
        "submission": sub_rej,
        "tool_trace": final_state.values.get("tool_trace", [])
    }

