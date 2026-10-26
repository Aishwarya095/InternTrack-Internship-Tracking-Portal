"""
INTERNTRACK — Lab 6: Controlled Runtime & Audit Environment
Chapter 10: Worklet 10 — Internship Application & Tracking Portal

Binds skills + tools + memory inside a governed execution controller:
- Step budgets (Token/Call bounds preventing infinite execution)
- Human approval gates (Hard stop: Consequential actions cannot commit autonomously)
- Checkpoint / Resume (Saves execution snapshots; can resume from crash)
- Tamper-evident Audit logging for every step
"""

import time
import uuid
import copy
from core.audit import log_event

class RuntimeExecutionState:
    def __init__(self, run_id, student_usn, max_budget=10):
        self.run_id = run_id
        self.student_usn = student_usn
        self.step_budget = max_budget
        self.steps_executed = 0
        self.status = "INITIALIZED" # INITIALIZED, RUNNING, PAUSED_FOR_APPROVAL, COMPLETED, BUDGET_EXCEEDED
        self.checkpoints = []
        self.logs = []
        self.pending_approval_action = None
        self.context = {}

class ControlledAgentRuntime:
    """
    Hardened execution container for AURA agent workflows.
    Enforces governance, budget caps, and checkpointing.
    """
    def __init__(self, max_budget=10):
        self.max_budget = max_budget
        self.active_runs = {}

    def start_run(self, student_usn, initial_intent="DISCOVER_AND_VERIFY"):
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        state = RuntimeExecutionState(run_id, student_usn, self.max_budget)
        state.context["intent"] = initial_intent
        state.status = "RUNNING"
        self.active_runs[run_id] = state

        log_event(
            actor="AURA_RUNTIME",
            actor_role="SYSTEM_AGENT",
            action="AGENT_RUN_STARTED",
            record_id=run_id,
            comments=f"Agent run started for {student_usn} with budget {self.max_budget}."
        )
        return state

    def execute_step(self, run_id, step_name, action_fn, is_risky=False, **kwargs):
        """
        Executes a discrete agent step within runtime constraints.
        If is_risky=True, pauses execution and checkpoints before proceeding.
        """
        state = self.active_runs.get(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found in runtime.")

        # Hard stop: A run paused at the Human Approval Gate cannot execute any further steps
        if state.status == "PAUSED_FOR_APPROVAL":
            step_desc = state.pending_approval_action.get("step_name", "consequential step") if state.pending_approval_action else "consequential step"
            raise RuntimeError(
                f"RUN_PAUSED_FOR_HUMAN_APPROVAL: Run {run_id} is currently paused at the Human Approval Gate for '{step_desc}'. "
                f"Bypassing with execute_step() is blocked. Explicit Coordinator approval or rejection is required."
            )

        if state.status in ["COMPLETED", "REJECTED_BY_COORDINATOR"]:
            raise RuntimeError(f"Run {run_id} has already concluded with status '{state.status}'. Cannot execute further steps.")

        if state.steps_executed >= state.step_budget:
            state.status = "BUDGET_EXCEEDED"
            raise RuntimeError(f"Step budget ({state.step_budget}) exhausted for run {run_id}. Execution halted.")

        # Checkpoint before executing step
        self._create_checkpoint(state, step_name)

        if is_risky:
            state.status = "PAUSED_FOR_APPROVAL"
            state.pending_approval_action = {
                "step_name": step_name,
                "action_fn": action_fn,
                "kwargs": kwargs
            }
            log_event(
                actor="AURA_RUNTIME",
                actor_role="SYSTEM_AGENT",
                action="HUMAN_APPROVAL_GATE_TRIGGERED",
                record_id=run_id,
                comments=f"Risky step '{step_name}' paused at Coordinator Gate. Awaiting human confirmation."
            )
            return {
                "run_id": run_id,
                "status": "PAUSED_FOR_APPROVAL",
                "message": f"Action '{step_name}' is consequential and requires Coordinator approval before commitment."
            }

        # Safe execution
        t0 = time.time()
        result = action_fn(**kwargs)
        duration_ms = round((time.time() - t0) * 1000, 2)

        state.steps_executed += 1
        state.logs.append({
            "step": state.steps_executed,
            "step_name": step_name,
            "duration_ms": duration_ms,
            "status": "COMPLETED",
            "result_summary": str(result)[:100]
        })

        return {
            "run_id": run_id,
            "status": "STEP_COMPLETED",
            "step": state.steps_executed,
            "result": result
        }

    def resume_with_human_approval(self, run_id, coordinator_name, action_fn=None):
        """Resumes a paused run once the human coordinator approves."""
        state = self.active_runs.get(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found in runtime.")
        if state.status != "PAUSED_FOR_APPROVAL":
            raise ValueError(f"Run {run_id} is not paused for approval (current status: '{state.status}').")

        pending = state.pending_approval_action or {}
        fn_to_call = action_fn or pending.get("action_fn")
        if not fn_to_call:
            raise ValueError("No action function available to execute upon approval.")

        log_event(
            actor=coordinator_name,
            actor_role="COORDINATOR",
            action="HUMAN_APPROVAL_GRANTED",
            record_id=run_id,
            comments=f"Coordinator approved execution of '{pending.get('step_name', 'Consequential Step')}'."
        )

        state.status = "RUNNING"
        t0 = time.time()
        res = fn_to_call(**pending.get("kwargs", {}))
        duration_ms = round((time.time() - t0) * 1000, 2)

        state.steps_executed += 1
        state.logs.append({
            "step": state.steps_executed,
            "step_name": f"{pending.get('step_name')} [APPROVED]",
            "duration_ms": duration_ms,
            "status": "COMPLETED",
            "result_summary": str(res)[:100]
        })
        self._create_checkpoint(state, f"{pending.get('step_name')} (APPROVED)")
        state.pending_approval_action = None
        state.status = "COMPLETED"

        return {
            "run_id": run_id,
            "status": "COMPLETED",
            "approval_signoff": coordinator_name,
            "result": res
        }

    def resume_with_human_rejection(self, run_id, coordinator_name, rejection_reason, rejection_fn=None):
        """Rejects a paused run with a mandatory reason from the human coordinator."""
        state = self.active_runs.get(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found in runtime.")
        if state.status != "PAUSED_FOR_APPROVAL":
            raise ValueError(f"Run {run_id} is not paused for approval (current status: '{state.status}').")

        if not rejection_reason or not str(rejection_reason).strip():
            raise ValueError("A mandatory rejection reason must be provided by the Coordinator.")

        pending = state.pending_approval_action or {}
        rejection_reason_clean = str(rejection_reason).strip()

        log_event(
            actor=coordinator_name,
            actor_role="COORDINATOR",
            action="HUMAN_APPROVAL_REJECTED",
            record_id=run_id,
            comments=f"Coordinator rejected execution of '{pending.get('step_name', 'Consequential Step')}'. Reason: {rejection_reason_clean}"
        )

        state.status = "RUNNING"
        res = None
        if rejection_fn:
            res = rejection_fn(rejection_reason=rejection_reason_clean, **pending.get("kwargs", {}))

        state.steps_executed += 1
        state.logs.append({
            "step": state.steps_executed,
            "step_name": f"{pending.get('step_name')} [REJECTED]",
            "status": "REJECTED_BY_COORDINATOR",
            "rejection_reason": rejection_reason_clean,
            "result_summary": str(res)[:100] if res else "Rejected by Coordinator"
        })
        self._create_checkpoint(state, f"{pending.get('step_name')} (REJECTED)")
        state.pending_approval_action = None
        state.status = "REJECTED_BY_COORDINATOR"

        return {
            "run_id": run_id,
            "status": "REJECTED_BY_COORDINATOR",
            "rejection_signoff": coordinator_name,
            "rejection_reason": rejection_reason_clean,
            "result": res
        }

    def _create_checkpoint(self, state, checkpoint_name):
        snapshot = {
            "checkpoint_name": checkpoint_name,
            "steps_executed": state.steps_executed,
            "context": copy.deepcopy(state.context),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        state.checkpoints.append(snapshot)
