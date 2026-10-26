"""
INTERNTRACK — Lab 8: LangGraph Parallel Swarm
Official LangGraph Implementation of Chapter 10 Worklet 10 Parallel Fan-out / Fan-in

Graph Topology:
START -> Preference Split Node
      |-- Branch 1 -> Worker Agent 1 (Preference 1)  --|
      |-- Branch 2 -> Worker Agent 2 (Preference 2)  --|--> Fan-In Node -> Human Approval Gate (PAUSE / CHECKPOINT) -> Consequential Commit -> END
      |-- Branch 3 -> Worker Agent 3 (Preference 3)  --|
      |-- Branch 4 -> Worker Agent 4 (Preference 4)  --|
"""

import time
import uuid
import operator
from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities, check_eligibility_and_vacancy
from workflows.submissions import coordinator_review_submission, create_submission, get_submission_by_id
from database.db import query_one
from core.audit import log_event

class SwarmGraphState(TypedDict):
    student_id: str
    preferences: List[str]
    student_profile: Dict[str, Any]
    evaluations: Annotated[List[Dict[str, Any]], operator.add]
    ranked_results: List[Dict[str, Any]]
    execution_trace: Annotated[List[Dict[str, Any]], operator.add]
    approval_status: str
    run_id: Optional[str]
    submission_id: Optional[str]
    coordinator_name: Optional[str]
    rejection_reason: Optional[str]
    consequential_result: Optional[Dict[str, Any]]

# ---- Preference Resolution Helper ----

def resolve_student_preferences(student_usn: str, preferences: Optional[List[str]] = None) -> List[str]:
    """
    Dynamically resolves 4 preferences for the student:
    1. If preferences explicitly provided and has entries, use them.
    2. Else, query student_submissions for student's latest active submission and extract
       [pref_1_company, pref_2_company, pref_3_company, pref_4_company].
    3. If student has no stored submission preferences, fallback to published catalog companies.
    """
    if preferences and len(preferences) > 0:
        return preferences

    # Query latest submission in student_submissions for this USN
    sub = query_one("""
        SELECT pref_1_company, pref_2_company, pref_3_company, pref_4_company
        FROM student_submissions
        WHERE student_usn = ?
        ORDER BY submission_version DESC, submitted_at DESC
        LIMIT 1
    """, (student_usn,))

    if sub:
        stored = [
            sub["pref_1_company"],
            sub["pref_2_company"],
            sub["pref_3_company"],
            sub["pref_4_company"]
        ]
        valid_stored = [p.strip() for p in stored if p and str(p).strip()]
        if len(valid_stored) >= 4:
            return valid_stored[:4]
        elif len(valid_stored) > 0:
            # Pad from catalog if student provided fewer than 4
            catalog = [o["company"] for o in list_opportunities(status="PUBLISHED")]
            for comp in catalog:
                if comp not in valid_stored:
                    valid_stored.append(comp)
                if len(valid_stored) == 4:
                    break
            return valid_stored

    # Fallback to catalog opportunities if genuinely no submission found
    catalog_opps = list_opportunities(status="PUBLISHED")
    catalog_names = [o["company"] for o in catalog_opps]
    default_fallbacks = ["PQR Solutions", "XYZ Labs", "GlobalTech Systems", "DEF AI", "ABC Technologies"]
    for d in default_fallbacks:
        if d not in catalog_names:
            catalog_names.append(d)
        if len(catalog_names) >= 4:
            break
    return catalog_names[:4]

# ---- LangGraph Nodes ----

def split_node(state: SwarmGraphState) -> Dict[str, Any]:
    student_usn = state["student_id"]
    profile = get_student_profile(student_usn)
    prefs = state.get("preferences", [])
    trace = [{
        "node": "Preference Split Node",
        "action": "fan_out_start",
        "message": f"Splitting 4 student company preferences into parallel LangGraph worker branches.",
        "preferences": prefs
    }]
    return {
        "student_profile": profile,
        "execution_trace": trace
    }

def _evaluate_preference_worker(worker_id: str, company_name: str, state: SwarmGraphState) -> Dict[str, Any]:
    usn = state["student_id"]
    t0 = time.time()
    try:
        all_opps = list_opportunities(status="PUBLISHED")
        matched = next((o for o in all_opps if company_name.lower() in o["company"].lower()), None)

        if matched:
            eval_res = check_eligibility_and_vacancy(usn, matched["id"])
        else:
            eval_res = {
                "student_usn": usn,
                "opportunity_id": None,
                "company": company_name,
                "is_eligible": False,
                "available_vacancies": 0,
                "status_explanation": "Opportunity not listed in current semester catalog."
            }

        duration_ms = round((time.time() - t0) * 1000, 2)

        eval_record = {
            "worker": worker_id,
            "company": company_name,
            "title": matched["title"] if matched else "Intern",
            "min_cgpa": matched["min_cgpa"] if matched else 7.0,
            "available_vacancies": matched["available_vacancies"] if matched else 0,
            "is_eligible": eval_res.get("is_eligible", False),
            "status": "EVALUATED" if eval_res.get("is_eligible", False) else "INELIGIBLE",
            "status_explanation": eval_res.get("status_explanation", "OK"),
            "duration_ms": duration_ms
        }

        trace_item = {
            "node": f"Worker Agent ({worker_id})",
            "company": company_name,
            "action": "parallel_eval",
            "is_eligible": eval_record["is_eligible"],
            "available_vacancies": eval_record["available_vacancies"],
            "duration_ms": duration_ms
        }

        return {
            "evaluations": [eval_record],
            "execution_trace": [trace_item]
        }

    except Exception as exc:
        duration_ms = round((time.time() - t0) * 1000, 2)
        err_str = str(exc)
        eval_record = {
            "worker": worker_id,
            "company": company_name,
            "title": "Unknown",
            "min_cgpa": 0.0,
            "available_vacancies": 0,
            "is_eligible": False,
            "status": "WORKER_ERROR",
            "error": err_str,
            "status_explanation": f"Worker Evaluation Error: {err_str}",
            "duration_ms": duration_ms
        }
        trace_item = {
            "node": f"Worker Agent ({worker_id})",
            "company": company_name,
            "action": "parallel_eval_error",
            "status": "WORKER_ERROR",
            "error": err_str,
            "is_eligible": False,
            "available_vacancies": 0,
            "duration_ms": duration_ms
        }
        return {
            "evaluations": [eval_record],
            "execution_trace": [trace_item]
        }

# Discrete Worker Nodes for the 4 Branches
def worker_1_agent(state: SwarmGraphState) -> Dict[str, Any]:
    comp = state["preferences"][0] if len(state["preferences"]) > 0 else "ABC Technologies"
    return _evaluate_preference_worker("Worker 1", comp, state)

def worker_2_agent(state: SwarmGraphState) -> Dict[str, Any]:
    comp = state["preferences"][1] if len(state["preferences"]) > 1 else "XYZ Labs"
    return _evaluate_preference_worker("Worker 2", comp, state)

def worker_3_agent(state: SwarmGraphState) -> Dict[str, Any]:
    comp = state["preferences"][2] if len(state["preferences"]) > 2 else "PQR Solutions"
    return _evaluate_preference_worker("Worker 3", comp, state)

def worker_4_agent(state: SwarmGraphState) -> Dict[str, Any]:
    comp = state["preferences"][3] if len(state["preferences"]) > 3 else "DEF AI"
    return _evaluate_preference_worker("Worker 4", comp, state)

def fan_in_node(state: SwarmGraphState) -> Dict[str, Any]:
    """LangGraph Fan-In Node: Merges parallel worker results and ranks by suitability."""
    evals = state.get("evaluations", [])

    # Rank: Eligible first, then by available vacancies descending, worker errors last
    def rank_key(x):
        is_err = x.get("status") == "WORKER_ERROR"
        return (
            0 if is_err else (1 if x.get("is_eligible") else 0),
            x.get("available_vacancies", 0)
        )

    ranked = sorted(evals, key=rank_key, reverse=True)

    trace_item = {
        "node": "Fan-In Node",
        "action": "fan_in_merge",
        "total_evaluated": len(evals),
        "best_ranked_company": ranked[0]["company"] if ranked else None
    }
    return {
        "ranked_results": ranked,
        "execution_trace": [trace_item]
    }

def human_approval_gate_node(state: SwarmGraphState) -> Dict[str, Any]:
    """
    Coordinator Human Gate: Halts consequential action until Coordinator approval.
    """
    best = state["ranked_results"][0] if state.get("ranked_results") else None
    trace_item = {
        "node": "Coordinator Approval Gate",
        "action": "pause_for_signoff",
        "recommended_choice": best["company"] if best else "None",
        "status": "PAUSED_FOR_COORDINATOR_APPROVAL"
    }

    run_id = state.get("run_id") or f"RUN-L8-{state['student_id']}"
    log_event(
        actor="LANGGRAPH_PARALLEL_SWARM",
        actor_role="SYSTEM_AGENT",
        action="HUMAN_APPROVAL_GATE_TRIGGERED",
        record_id=run_id,
        comments=f"Swarm evaluated 4 preferences. Recommended top candidate: {best['company'] if best else 'None'}. Paused awaiting Coordinator signoff."
    )

    return {
        "approval_status": "PAUSED_FOR_COORDINATOR_APPROVAL",
        "execution_trace": [trace_item]
    }

def commit_node(state: SwarmGraphState) -> Dict[str, Any]:
    """
    Consequential Commit Node: Executes ONLY after Coordinator explicit approval.
    """
    best = state["ranked_results"][0] if state.get("ranked_results") else None
    target_company = best["company"] if best else "ABC Technologies"
    target_role = best.get("title", "AI/ML Intern")
    usn = state["student_id"]
    coord_name = state.get("coordinator_name") or "Dr. Ramesh Kulkarni"

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
        sub = create_submission(
            usn,
            {
                "submission_type": "NORMAL",
                "pref_1_company": target_company,
                "pref_1_role": target_role,
                "pref_1_location": "Bangalore",
                "pref_1_remarks": "Generated via AURA Lab 8 Parallel Swarm."
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
            "coordinator_comments": f"Approved via AURA Lab 8 Parallel Swarm Human Gate for {usn}."
        }
    )

    trace_item = {
        "node": "Consequential Commit Node",
        "action": "commit_coordinator_approval",
        "approved_company": target_company,
        "submission_id": sub["id"],
        "status": "APPROVED"
    }

    log_event(
        actor=coord_name,
        actor_role="COORDINATOR",
        action="HUMAN_APPROVAL_GRANTED",
        record_id=state.get("run_id") or sub["id"],
        comments=f"Coordinator approved Lab 8 swarm recommendation for {usn}. Submission {sub['id']} transitioned to COORDINATOR_APPROVED."
    )

    return {
        "approval_status": "COMPLETED",
        "consequential_result": consequential_res,
        "execution_trace": [trace_item]
    }

# ---- Build & Compile the LangGraph Swarm Graph with Checkpointer & Interrupt ----

lab8_checkpointer = MemorySaver()
lab8_active_runs: Dict[str, Dict[str, Any]] = {}

def build_lab8_swarm_graph(checkpointer=None):
    builder = StateGraph(SwarmGraphState)

    # Add Nodes
    builder.add_node("split", split_node)
    builder.add_node("worker_1", worker_1_agent)
    builder.add_node("worker_2", worker_2_agent)
    builder.add_node("worker_3", worker_3_agent)
    builder.add_node("worker_4", worker_4_agent)
    builder.add_node("fan_in", fan_in_node)
    builder.add_node("human_gate", human_approval_gate_node)
    builder.add_node("commit", commit_node)

    # Edge from START to Split
    builder.add_edge(START, "split")

    # Fan-out: Edges from split to 4 parallel workers
    builder.add_edge("split", "worker_1")
    builder.add_edge("split", "worker_2")
    builder.add_edge("split", "worker_3")
    builder.add_edge("split", "worker_4")

    # Fan-in: Edges from all 4 workers to fan_in
    builder.add_edge("worker_1", "fan_in")
    builder.add_edge("worker_2", "fan_in")
    builder.add_edge("worker_3", "fan_in")
    builder.add_edge("worker_4", "fan_in")

    # Edge from fan_in to human_gate, then commit, then END
    builder.add_edge("fan_in", "human_gate")
    builder.add_edge("human_gate", "commit")
    builder.add_edge("commit", END)

    cp = checkpointer if checkpointer is not None else lab8_checkpointer
    compiled = builder.compile(checkpointer=cp, interrupt_before=["commit"])

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

# Global compiled swarm graph
lab8_compiled_swarm = build_lab8_swarm_graph()

def run_lab8_langgraph(student_usn="1KG21CS045", preferences=None, run_id=None, submission_id=None):
    """
    Executes the LangGraph parallel swarm evaluating 4 preferences concurrently.
    Pauses execution at the Coordinator Human Gate awaiting human signoff.
    """
    active_run_id = run_id or f"RUN-L8-{uuid.uuid4().hex[:8].upper()}"

    # Bypass enforcement: Paused run cannot be directly re-invoked
    if active_run_id in lab8_active_runs:
        current_status = lab8_active_runs[active_run_id].get("status")
        if current_status == "PAUSED_FOR_COORDINATOR_APPROVAL":
            raise RuntimeError(
                f"RUN_PAUSED_FOR_HUMAN_APPROVAL: Run '{active_run_id}' is currently paused at the Coordinator Human Gate. "
                f"Direct invocation bypass is blocked. Explicit Coordinator approval or rejection is required."
            )

    # Dynamic Preference Resolution from real database
    prefs = resolve_student_preferences(student_usn, preferences)

    if not submission_id:
        sub = query_one(
            "SELECT id FROM student_submissions WHERE student_usn = ? AND status = 'SUBMITTED' ORDER BY submission_version DESC LIMIT 1",
            (student_usn,)
        )
        if sub:
            submission_id = sub["id"]

    initial_state: SwarmGraphState = {
        "student_id": student_usn,
        "preferences": prefs,
        "student_profile": {},
        "evaluations": [],
        "ranked_results": [],
        "execution_trace": [],
        "approval_status": "STARTING",
        "run_id": active_run_id,
        "submission_id": submission_id,
        "coordinator_name": None,
        "rejection_reason": None,
        "consequential_result": None
    }

    log_event(
        actor="AURA_LANGGRAPH_SWARM",
        actor_role="SYSTEM_AGENT",
        action="AGENT_RUN_STARTED",
        record_id=active_run_id,
        comments=f"Lab 8 LangGraph swarm run started for {student_usn} evaluating {prefs}."
    )

    t0 = time.time()
    config = {"configurable": {"thread_id": active_run_id}}
    final_output = lab8_compiled_swarm.invoke(initial_state, config=config)
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    # Check whether the StateGraph paused before commit
    graph_state = lab8_compiled_swarm.get_state(config)
    is_paused = graph_state.next == ("commit",)
    status_str = "PAUSED_FOR_COORDINATOR_APPROVAL" if is_paused else final_output.get("approval_status", "COMPLETED")

    lab8_active_runs[active_run_id] = {
        "run_id": active_run_id,
        "student_usn": student_usn,
        "submission_id": submission_id,
        "status": status_str,
        "created_at": time.time(),
        "preferences": prefs,
        "evaluations": final_output["evaluations"],
        "ranked_results": final_output["ranked_results"],
        "execution_trace": final_output["execution_trace"]
    }

    return {
        "lab": "Lab 8: LangGraph Parallel Swarm",
        "orchestration_engine": "LangGraph (langgraph.graph.StateGraph with Fan-Out / Fan-In Reducers)",
        "status": status_str,
        "run_id": active_run_id,
        "student_id": student_usn,
        "student_usn": student_usn,
        "submission_id": submission_id,
        "preferences_evaluated": prefs,
        "evaluations_count": len(final_output["evaluations"]),
        "ranked_results": final_output["ranked_results"],
        "execution_trace": final_output["execution_trace"],
        "approval_status": status_str,
        "duration_ms": elapsed_ms,
        "next_step": "Coordinator Approval Required before Consequential Commit" if is_paused else "Execution Complete"
    }

def approve_lab8_langgraph(run_id: str, coordinator_name: str = "Dr. Ramesh Kulkarni") -> Dict[str, Any]:
    """
    Resumes the SAME LangGraph checkpoint from the Coordinator Human Gate into Commit Node.
    """
    run = lab8_active_runs.get(run_id)
    if not run:
        raise ValueError(f"Run '{run_id}' not found in runtime.")

    if run.get("status") != "PAUSED_FOR_COORDINATOR_APPROVAL":
        raise ValueError(
            f"Run '{run_id}' is not awaiting approval (current status: '{run.get('status')}'). "
            f"Duplicate or invalid continuation rejected."
        )

    config = {"configurable": {"thread_id": run_id}}
    state_before = lab8_compiled_swarm.get_state(config)
    if state_before.next != ("commit",):
        raise ValueError(f"Graph checkpoint for run '{run_id}' is not pending Commit step (next: {state_before.next}).")

    # Update state with coordinator signoff
    lab8_compiled_swarm.update_state(config, {"coordinator_name": coordinator_name}, as_node="human_gate")

    # Resume the SAME LangGraph execution across the interrupted edge to commit_node
    final_output = lab8_compiled_swarm.invoke(None, config=config)

    run["status"] = "COMPLETED"
    run["execution_trace"] = final_output["execution_trace"]
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
        "ranked_results": final_output.get("ranked_results", []),
        "consequential_result": final_output.get("consequential_result"),
        "execution_trace": final_output["execution_trace"]
    }

def reject_lab8_langgraph(run_id: str, coordinator_name: str = "Dr. Ramesh Kulkarni", rejection_reason: str = None) -> Dict[str, Any]:
    """
    Terminates the paused LangGraph execution without executing Commit Node, persisting mandatory rejection reason.
    """
    run = lab8_active_runs.get(run_id)
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

    # Terminate the graph checkpoint cleanly without executing commit_node
    lab8_compiled_swarm.update_state(
        config,
        {
            "approval_status": "REJECTED_BY_COORDINATOR",
            "rejection_reason": reason_clean
        },
        as_node="commit"
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
        comments=f"Coordinator rejected Lab 8 LangGraph swarm execution for {run['student_usn']}. Reason: {reason_clean}"
    )

    run["status"] = "REJECTED_BY_COORDINATOR"
    run["rejection_reason"] = reason_clean
    run["coordinator_signoff"] = coordinator_name

    final_state = lab8_compiled_swarm.get_state(config)

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
        "submission": sub_rej,
        "execution_trace": final_state.values.get("execution_trace", [])
    }

