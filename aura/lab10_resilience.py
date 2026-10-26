"""
INTERNTRACK — Lab 10: Ops Resilience — Validate, Diagnose, Fix
Phase C: Applied Reliability

Goal: Make the pipeline self-healing when validation fails.
What it adds to this worklet:
When a check fails (awarded marks never exceed the faculty maximum per question;
every test case runs inside the sandbox), the agent diagnoses the exact failing
constraint and regenerates only the offending part.

Inputs:   Validation report; current output.
Outputs:  A repaired, passing output with a diagnosis log.
Nodes:    Validation agent + Coordinator's regenerate loop (StateGraph).
Deliverable & Acceptance:
Failure-injection tests showing automatic diagnosis and targeted repair.
Accept: Injected faults are detected and fixed within the retry budget.
Pitfall to Avoid:
Regenerate only the failing part — rebuilding everything wastes budget and churns good work.

Core Resilience Loop:
    report = validate(output, plan)
    while not report.passed and attempts < BUDGET:
        regenerate(report.failing)
        report = validate(output, plan)
    if not report.passed:
        escalate(report)   # to the human
"""

import time
import json
import uuid
import copy
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict, Tuple

from database.db import query_one, query_all
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities, get_opportunity
from core.audit import log_event
from langgraph.graph import StateGraph, START, END

# ==============================================================================
# 1. FACULTY RUBRIC CONSTRAINTS & SANDBOX POLICIES
# ==============================================================================

OPS_RESILIENCE_RUBRIC = {
    "rubric_id": "RUBRIC-OPS-RESILIENCE-2026",
    "title": "Faculty Academic & Sandbox Execution Compliance Rubric",
    "issuing_authority": "Academic Senate & Cloud Operations Desk",
    "version": "1.0-SELF_HEALING",
    "max_retry_budget": 3,
    "max_marks": {
        "technical_depth": 30,
        "system_design": 30,
        "journal_logs": 20,
        "mentor_viva": 20,
        "total_max": 100
    },
    "credit_ceiling": 16,
    "credit_floor": 12,
    "stipend_floor": 15000,
    "duration_weeks_min": 12,
    "duration_weeks_max": 24,
    "required_sandbox_isolation": ["SECCOMP_CONTAINER", "DOCKER_SECCOMP", "GVISOR_MICROVM"],
    "allowed_file_extensions": [".pdf", ".docx", ".zip", ".md"],
    "prohibited_syscalls": ["ptrace", "reboot", "sys_chroot", "kexec_load", "bpf"]
}

# ==============================================================================
# 2. VALIDATION REPORT & FAILURE DATA STRUCTURES
# ==============================================================================

class ConstraintFailure:
    def __init__(
        self,
        constraint_id: str,
        component_path: str,
        rule_description: str,
        actual_value: Any,
        expected_constraint: str,
        severity: str = "ERROR",
        fix_target: str = "TARGETED_REGENERATE"
    ):
        self.constraint_id = constraint_id
        self.component_path = component_path
        self.rule_description = rule_description
        self.actual_value = actual_value
        self.expected_constraint = expected_constraint
        self.severity = severity
        self.fix_target = fix_target

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "component_path": self.component_path,
            "rule_description": self.rule_description,
            "actual_value": self.actual_value,
            "expected_constraint": self.expected_constraint,
            "severity": self.severity,
            "fix_target": self.fix_target
        }


class ValidationReport:
    def __init__(
        self,
        passed: bool,
        total_checks: int,
        passed_checks: int,
        failing: List[ConstraintFailure],
        summary: str = ""
    ):
        self.passed = passed
        self.total_checks = total_checks
        self.passed_checks = passed_checks
        self.failed_checks = len(failing)
        self.failing = failing
        self.summary = summary
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "failing": [f.to_dict() for f in self.failing],
            "summary": self.summary,
            "timestamp": self.timestamp
        }


# ==============================================================================
# 3. CORE VALIDATION AGENT NODE
# ==============================================================================

def validate_pipeline_output(output: Dict[str, Any], plan: Optional[Dict[str, Any]] = None) -> ValidationReport:
    """
    Validates candidate evaluation dossier and sandbox environment.
    Evaluates:
    1. Awarded marks never exceed faculty rubric ceiling per question/section.
    2. Credits allotted conform to university ceiling (12 - 16 credits).
    3. Stipend satisfies the institutional floor (>= INR 15,000/mo).
    4. Every test case runs inside the sandbox (sandbox_contained = True, approved isolation).
    5. Prohibited dangerous syscalls are blocked.
    6. Duration adheres to semester bounds (12 - 24 weeks).
    """
    failing: List[ConstraintFailure] = []
    checks_run = 0
    passed_count = 0

    rubric = OPS_RESILIENCE_RUBRIC
    evals = output.get("evaluations", {})
    max_marks = rubric["max_marks"]

    # Check 1: Technical Depth Marks
    checks_run += 1
    tech_marks = evals.get("technical_depth", 0)
    if tech_marks > max_marks["technical_depth"]:
        failing.append(ConstraintFailure(
            constraint_id="MAX_MARKS_EXCEEDED_TECHNICAL_DEPTH",
            component_path="evaluations.technical_depth",
            rule_description="Awarded marks must never exceed faculty maximum of 30 for Technical Depth.",
            actual_value=tech_marks,
            expected_constraint=f"<= {max_marks['technical_depth']}",
            fix_target="regrade_technical_depth"
        ))
    elif tech_marks < 0:
        failing.append(ConstraintFailure(
            constraint_id="NEGATIVE_MARKS_TECHNICAL_DEPTH",
            component_path="evaluations.technical_depth",
            rule_description="Awarded marks cannot be negative.",
            actual_value=tech_marks,
            expected_constraint=">= 0",
            fix_target="regrade_technical_depth"
        ))
    else:
        passed_count += 1

    # Check 2: System Design Marks
    checks_run += 1
    sys_marks = evals.get("system_design", 0)
    if sys_marks > max_marks["system_design"]:
        failing.append(ConstraintFailure(
            constraint_id="MAX_MARKS_EXCEEDED_SYSTEM_DESIGN",
            component_path="evaluations.system_design",
            rule_description="Awarded marks must never exceed faculty maximum of 30 for System Design.",
            actual_value=sys_marks,
            expected_constraint=f"<= {max_marks['system_design']}",
            fix_target="regrade_system_design"
        ))
    else:
        passed_count += 1

    # Check 3: Journal Logs Marks
    checks_run += 1
    journal_marks = evals.get("journal_logs", 0)
    if journal_marks > max_marks["journal_logs"]:
        failing.append(ConstraintFailure(
            constraint_id="MAX_MARKS_EXCEEDED_JOURNAL_LOGS",
            component_path="evaluations.journal_logs",
            rule_description="Awarded marks must never exceed faculty maximum of 20 for Weekly Journal Logs.",
            actual_value=journal_marks,
            expected_constraint=f"<= {max_marks['journal_logs']}",
            fix_target="regrade_journal_logs"
        ))
    else:
        passed_count += 1

    # Check 4: Mentor Viva Marks
    checks_run += 1
    viva_marks = evals.get("mentor_viva", 0)
    if viva_marks > max_marks["mentor_viva"]:
        failing.append(ConstraintFailure(
            constraint_id="MAX_MARKS_EXCEEDED_MENTOR_VIVA",
            component_path="evaluations.mentor_viva",
            rule_description="Awarded marks must never exceed faculty maximum of 20 for Industry Mentor Viva.",
            actual_value=viva_marks,
            expected_constraint=f"<= {max_marks['mentor_viva']}",
            fix_target="regrade_mentor_viva"
        ))
    else:
        passed_count += 1

    # Check 5: Academic Credit Ceiling
    checks_run += 1
    credits_allotted = output.get("credits_allotted", 0)
    if credits_allotted > rubric["credit_ceiling"]:
        failing.append(ConstraintFailure(
            constraint_id="CREDIT_CEILING_EXCEEDED",
            component_path="credits_allotted",
            rule_description=f"Internship credits cannot exceed the regulatory ceiling of {rubric['credit_ceiling']}.",
            actual_value=credits_allotted,
            expected_constraint=f"<= {rubric['credit_ceiling']}",
            fix_target="adjust_credit_allotment"
        ))
    elif credits_allotted < rubric["credit_floor"]:
        failing.append(ConstraintFailure(
            constraint_id="CREDIT_FLOOR_DEFICIT",
            component_path="credits_allotted",
            rule_description=f"Internship credits cannot fall below minimum course credits of {rubric['credit_floor']}.",
            actual_value=credits_allotted,
            expected_constraint=f">= {rubric['credit_floor']}",
            fix_target="adjust_credit_allotment"
        ))
    else:
        passed_count += 1

    # Check 6: Monthly Stipend Floor
    checks_run += 1
    stipend = output.get("stipend_monthly", 0)
    if stipend < rubric["stipend_floor"]:
        failing.append(ConstraintFailure(
            constraint_id="STIPEND_FLOOR_VIOLATION",
            component_path="stipend_monthly",
            rule_description=f"Monthly stipend must meet or exceed institutional floor of INR {rubric['stipend_floor']}.",
            actual_value=stipend,
            expected_constraint=f">= {rubric['stipend_floor']}",
            fix_target="repair_stipend_floor"
        ))
    else:
        passed_count += 1

    # Check 7: Sandbox Test Case Containment
    checks_run += 1
    sandbox = output.get("sandbox_environment", {})
    is_contained = sandbox.get("sandbox_contained", False)
    isolation_type = sandbox.get("isolation_type", "")
    if not is_contained or isolation_type not in rubric["required_sandbox_isolation"]:
        failing.append(ConstraintFailure(
            constraint_id="UNSANDBOXED_EXECUTION_VIOLATION",
            component_path="sandbox_environment.sandbox_contained",
            rule_description="Every student evaluation test case and verification suite must run strictly inside an isolated sandbox.",
            actual_value={"contained": is_contained, "isolation": isolation_type},
            expected_constraint=f"sandbox_contained == True & isolation in {rubric['required_sandbox_isolation']}",
            fix_target="enforce_sandbox_container"
        ))
    else:
        passed_count += 1

    # Check 8: Prohibited System Calls in Sandbox
    checks_run += 1
    active_syscalls = sandbox.get("permitted_syscalls", [])
    prohibited_found = [s for s in active_syscalls if s in rubric["prohibited_syscalls"]]
    if prohibited_found:
        failing.append(ConstraintFailure(
            constraint_id="PROHIBITED_SYSCALL_DETECTED",
            component_path="sandbox_environment.permitted_syscalls",
            rule_description=f"Sandbox profile allows unsafe system calls: {prohibited_found}.",
            actual_value=prohibited_found,
            expected_constraint=f"No syscalls in {rubric['prohibited_syscalls']}",
            fix_target="purge_unsafe_syscalls"
        ))
    else:
        passed_count += 1

    # Check 9: Duration Boundaries (12 - 24 Weeks)
    checks_run += 1
    duration = output.get("duration_weeks", 0)
    if duration < rubric["duration_weeks_min"] or duration > rubric["duration_weeks_max"]:
        failing.append(ConstraintFailure(
            constraint_id="INVALID_INTERNSHIP_DURATION",
            component_path="duration_weeks",
            rule_description=f"Internship duration must be between {rubric['duration_weeks_min']} and {rubric['duration_weeks_max']} weeks.",
            actual_value=duration,
            expected_constraint=f"{rubric['duration_weeks_min']} <= duration <= {rubric['duration_weeks_max']}",
            fix_target="normalize_internship_duration"
        ))
    else:
        passed_count += 1

    # Check 10: Fatal Unrecoverable Injection Sentinel (for testing human escalation)
    checks_run += 1
    if output.get("fatal_irreparable_anomaly", False):
        failing.append(ConstraintFailure(
            constraint_id="FATAL_CORRUPTION_IRREPARABLE",
            component_path="security_anomaly",
            rule_description="Irreparable cryptographic state compromise detected. Automated remediation disabled.",
            actual_value="UNRECOVERABLE_PAYLOAD_SIGNATURE",
            expected_constraint="Clean tamper-evident ledger",
            severity="FATAL",
            fix_target="ESCALATE_HUMAN_INTERVENTION"
        ))
    else:
        passed_count += 1

    all_passed = len(failing) == 0
    summary = "Validation PASSED. All 10 constraints satisfied." if all_passed else f"Validation FAILED: {len(failing)} constraint(s) breached."

    return ValidationReport(
        passed=all_passed,
        total_checks=checks_run,
        passed_checks=passed_count,
        failing=failing,
        summary=summary
    )


# ==============================================================================
# 4. DIAGNOSIS AGENT NODE
# ==============================================================================

def diagnose_failures(report: ValidationReport, output: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    """
    Diagnoses exact failing constraints and pinpoints the minimal offending subcomponents.
    Avoids churning good work by isolating solely the failing keys.
    """
    diagnosis_items = []

    for failure in report.failing:
        path = failure.component_path
        actual = failure.actual_value
        cid = failure.constraint_id

        diagnosis_detail = {
            "attempt": attempt,
            "constraint_id": cid,
            "component_path": path,
            "rule": failure.rule_description,
            "observed_fault": actual,
            "remediation_action": failure.fix_target,
            "preservation_guarantee": f"Components outside '{path}' remain untouched and valid."
        }

        if cid.startswith("MAX_MARKS_EXCEEDED"):
            section = path.split(".")[-1]
            ceiling = OPS_RESILIENCE_RUBRIC["max_marks"].get(section, 30)
            overage = actual - ceiling
            diagnosis_detail["root_cause"] = f"Faculty rubric ceiling exceeded by +{overage} marks in section '{section}'."
            diagnosis_detail["targeted_repair_plan"] = f"Clamp section '{section}' to rubric compliant max ({ceiling}) without modifying other evaluation sections."

        elif cid == "CREDIT_CEILING_EXCEEDED":
            overage = actual - OPS_RESILIENCE_RUBRIC["credit_ceiling"]
            diagnosis_detail["root_cause"] = f"Credits allotted ({actual}) exceeds university ceiling ({OPS_RESILIENCE_RUBRIC['credit_ceiling']}) by +{overage} credits."
            diagnosis_detail["targeted_repair_plan"] = f"Reset credits_allotted to {OPS_RESILIENCE_RUBRIC['credit_ceiling']} without disturbing student profile or company."

        elif cid == "STIPEND_FLOOR_VIOLATION":
            floor = OPS_RESILIENCE_RUBRIC["stipend_floor"]
            diagnosis_detail["root_cause"] = f"Stipend ({actual}) violates institutional floor of INR {floor}/mo."
            diagnosis_detail["targeted_repair_plan"] = f"Re-ground monthly stipend to default compliant rate (INR 32,000) for target candidate."

        elif cid == "UNSANDBOXED_EXECUTION_VIOLATION":
            diagnosis_detail["root_cause"] = "Execution container sandbox was either disabled or uncontained."
            diagnosis_detail["targeted_repair_plan"] = "Enforce DOCKER_SECCOMP containerization and enable sandbox_contained flag."

        elif cid == "PROHIBITED_SYSCALL_DETECTED":
            diagnosis_detail["root_cause"] = f"Security sandbox allowed blacklisted syscalls: {actual}."
            diagnosis_detail["targeted_repair_plan"] = "Filter out prohibited syscalls and restrict seccomp profile."

        elif cid == "INVALID_INTERNSHIP_DURATION":
            diagnosis_detail["root_cause"] = f"Duration {actual} weeks is outside allowed [12, 24] weeks range."
            diagnosis_detail["targeted_repair_plan"] = "Adjust duration_weeks to standard 16 weeks (Semester 8 curriculum)."

        elif cid == "FATAL_CORRUPTION_IRREPARABLE":
            diagnosis_detail["root_cause"] = "Unrecoverable security anomaly injected. Exceeds automated agent capability."
            diagnosis_detail["targeted_repair_plan"] = "Escalate to Human Coordinator Desk (Dr. Ramesh Kulkarni) for manual audit."

        diagnosis_items.append(diagnosis_detail)

    return {
        "attempt": attempt,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_failures_diagnosed": len(diagnosis_items),
        "diagnoses": diagnosis_items
    }


# ==============================================================================
# 5. TARGETED REGENERATION NODE (AVOIDS PITFALL)
# ==============================================================================

def regenerate_offending_parts(
    failing_list: List[ConstraintFailure],
    current_output: Dict[str, Any],
    plan: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], List[str]]:
    """
    CRITICAL LAB 10 PITFALL AVOIDANCE:
    "Regenerate only the failing part — rebuilding everything wastes budget and churns good work."

    Preserves 100% of unaffected components (student data, other grade sections,
    company details, timestamps, existing hashes) and mutates solely the offending
    fields pinpointed in failing_list.
    """
    # Clone current output deeply to avoid accidental side effects
    repaired = copy.deepcopy(current_output)
    repaired_fields = []

    for failure in failing_list:
        cid = failure.constraint_id
        path = failure.component_path

        # 1. Targeted repair for Technical Depth
        if cid == "MAX_MARKS_EXCEEDED_TECHNICAL_DEPTH":
            repaired["evaluations"]["technical_depth"] = 28  # Reground to high-compliant score within 30
            repaired_fields.append("evaluations.technical_depth")

        # 2. Targeted repair for System Design
        elif cid == "MAX_MARKS_EXCEEDED_SYSTEM_DESIGN":
            repaired["evaluations"]["system_design"] = 27  # Reground within 30
            repaired_fields.append("evaluations.system_design")

        # 3. Targeted repair for Journal Logs
        elif cid == "MAX_MARKS_EXCEEDED_JOURNAL_LOGS":
            repaired["evaluations"]["journal_logs"] = 19  # Reground within 20
            repaired_fields.append("evaluations.journal_logs")

        # 4. Targeted repair for Mentor Viva
        elif cid == "MAX_MARKS_EXCEEDED_MENTOR_VIVA":
            repaired["evaluations"]["mentor_viva"] = 18  # Reground within 20
            repaired_fields.append("evaluations.mentor_viva")

        # 5. Targeted repair for Credits Allotted
        elif cid in ["CREDIT_CEILING_EXCEEDED", "CREDIT_FLOOR_DEFICIT"]:
            repaired["credits_allotted"] = 16  # Standard Semester 8 ceiling
            repaired_fields.append("credits_allotted")

        # 6. Targeted repair for Stipend Floor
        elif cid == "STIPEND_FLOOR_VIOLATION":
            repaired["stipend_monthly"] = 32000  # Default verified campus tier-1 stipend
            repaired_fields.append("stipend_monthly")

        # 7. Targeted repair for Sandbox Containment
        elif cid == "UNSANDBOXED_EXECUTION_VIOLATION":
            if "sandbox_environment" not in repaired:
                repaired["sandbox_environment"] = {}
            repaired["sandbox_environment"]["sandbox_contained"] = True
            repaired["sandbox_environment"]["isolation_type"] = "DOCKER_SECCOMP"
            repaired["sandbox_environment"]["network_egress_restricted"] = True
            repaired["sandbox_environment"]["container_id"] = f"box-{uuid.uuid4().hex[:8]}"
            repaired_fields.append("sandbox_environment.sandbox_contained")

        # 8. Targeted repair for Prohibited Syscalls
        elif cid == "PROHIBITED_SYSCALL_DETECTED":
            active = repaired.get("sandbox_environment", {}).get("permitted_syscalls", [])
            prohibited = OPS_RESILIENCE_RUBRIC["prohibited_syscalls"]
            cleaned = [s for s in active if s not in prohibited]
            repaired["sandbox_environment"]["permitted_syscalls"] = cleaned
            repaired_fields.append("sandbox_environment.permitted_syscalls")

        # 9. Targeted repair for Duration
        elif cid == "INVALID_INTERNSHIP_DURATION":
            repaired["duration_weeks"] = 16  # Default full semester
            repaired_fields.append("duration_weeks")

        # 10. Fatal anomaly cannot be repaired by automated agent -> remains to trigger escalation
        elif cid == "FATAL_CORRUPTION_IRREPARABLE":
            # Intentionally left unchanged so attempts exhaust and escalation triggers
            pass

    # Recalculate total evaluation marks if evaluations exist
    if "evaluations" in repaired and isinstance(repaired["evaluations"], dict):
        total_eval = sum([
            repaired["evaluations"].get("technical_depth", 0),
            repaired["evaluations"].get("system_design", 0),
            repaired["evaluations"].get("journal_logs", 0),
            repaired["evaluations"].get("mentor_viva", 0)
        ])
        repaired["evaluations"]["total_score"] = total_eval
        repaired["evaluations"]["percentage"] = round((total_eval / OPS_RESILIENCE_RUBRIC["max_marks"]["total_max"]) * 100, 2)

    # Update ledger hash for repaired output
    repaired_str = json.dumps(repaired, sort_keys=True)
    repaired["audit_signature"] = hashlib.sha256(repaired_str.encode("utf-8")).hexdigest()[:16]
    repaired["last_repaired_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return repaired, repaired_fields


# ==============================================================================
# 6. ESCALATION AGENT NODE (HUMAN ESCALATION)
# ==============================================================================

def escalate_to_human(
    report: ValidationReport,
    output: Dict[str, Any],
    attempts: int
) -> Dict[str, Any]:
    """
    Escalates an unresolvable failure report to the Human Coordinator / HOD Approval Desk.
    Triggered when retry budget is exhausted and report is still failing.
    Appends an immutable audit event and assigns human review ticket.
    """
    escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    student_usn = output.get("student_usn", "1KG21CS045")
    company = output.get("target_company", "Tata Consultancy Services (TCS)")

    details = {
        "escalation_id": escalation_id,
        "escalated_to": "Coordinator",
        "human_desk": "COORDINATOR_HUMAN_GATE",
        "student_usn": student_usn,
        "target_company": company,
        "retry_budget_exhausted": attempts,
        "unresolved_failures": [f.to_dict() for f in report.failing],
        "escalation_reason": f"Self-healing pipeline exhausted maximum budget of {attempts} attempts. Immediate human intervention required.",
        "recommended_action": "Coordinator Review & Manual Rubric Overhaul",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    log_event(
        actor="AURA_RESILIENCE_AGENT",
        actor_role="COORDINATOR_LOOP",
        action="OPS_RESILIENCE_ESCALATED_TO_HUMAN",
        record_id=escalation_id,
        new_status="ESCALATED",
        comments=details["escalation_reason"],
        metadata=details
    )

    return details


# ==============================================================================
# 7. LANGGRAPH STATEGRAPH RESILIENCE PIPELINE
# ==============================================================================

class Lab10State(TypedDict):
    output: Dict[str, Any]
    plan: Dict[str, Any]
    report: Dict[str, Any]
    attempts: int
    max_budget: int
    diagnosis_log: List[Dict[str, Any]]
    repaired_fields_history: List[List[str]]
    status: str
    escalation: Optional[Dict[str, Any]]
    execution_trace: List[str]


def build_lab10_resilience_graph():
    """
    Builds the official LangGraph StateGraph pipeline with self-healing feedback loop:
    START -> ValidateNode -> Conditional:
              • If passed -> END (Status: SELF_HEALED_PASS)
              • If not passed & attempts < budget -> DiagnoseNode -> RegenerateNode -> ValidateNode (Loop)
              • If not passed & attempts >= budget -> EscalateNode -> END (Status: ESCALATED_TO_HUMAN)
    """
    workflow = StateGraph(Lab10State)

    def validate_node(state: Lab10State) -> Lab10State:
        v_rep = validate_pipeline_output(state["output"], state.get("plan"))
        state["report"] = v_rep.to_dict()
        if v_rep.passed:
            state["status"] = "SELF_HEALED_PASS"
        state["execution_trace"].append(
            f"ValidateNode (Attempt {state['attempts']}): Passed={v_rep.passed} [Checks: {v_rep.passed_checks}/{v_rep.total_checks}]"
        )
        return state

    def diagnose_node(state: Lab10State) -> Lab10State:
        rep_obj = ValidationReport(
            passed=state["report"]["passed"],
            total_checks=state["report"]["total_checks"],
            passed_checks=state["report"]["passed_checks"],
            failing=[ConstraintFailure(**item) for item in state["report"]["failing"]],
            summary=state["report"]["summary"]
        )
        diag = diagnose_failures(rep_obj, state["output"], state["attempts"] + 1)
        state["diagnosis_log"].append(diag)
        state["execution_trace"].append(
            f"DiagnoseNode: Diagnosed {diag['total_failures_diagnosed']} constraint failures."
        )
        return state

    def regenerate_node(state: Lab10State) -> Lab10State:
        state["attempts"] += 1
        rep_obj = [ConstraintFailure(**item) for item in state["report"]["failing"]]
        repaired_out, fields = regenerate_offending_parts(rep_obj, state["output"], state.get("plan"))
        state["output"] = repaired_out
        state["repaired_fields_history"].append(fields)
        state["execution_trace"].append(
            f"RegenerateNode (Attempt {state['attempts']}): Targeted repair on only: {fields}."
        )
        return state

    def escalate_node(state: Lab10State) -> Lab10State:
        rep_obj = ValidationReport(
            passed=state["report"]["passed"],
            total_checks=state["report"]["total_checks"],
            passed_checks=state["report"]["passed_checks"],
            failing=[ConstraintFailure(**item) for item in state["report"]["failing"]],
            summary=state["report"]["summary"]
        )
        esc = escalate_to_human(rep_obj, state["output"], state["attempts"])
        state["escalation"] = esc
        state["status"] = "ESCALATED_TO_HUMAN"
        state["execution_trace"].append(
            f"EscalateNode: Escalated ticket {esc['escalation_id']} to Human Coordinator Desk."
        )
        return state

    def route_validation(state: Lab10State) -> str:
        rep = state["report"]
        if rep["passed"]:
            state["status"] = "SELF_HEALED_PASS"
            return "END"
        if state["attempts"] < state["max_budget"]:
            return "DIAGNOSE"
        return "ESCALATE"

    workflow.add_node("validate_node", validate_node)
    workflow.add_node("diagnose_node", diagnose_node)
    workflow.add_node("regenerate_node", regenerate_node)
    workflow.add_node("escalate_node", escalate_node)

    workflow.add_edge(START, "validate_node")
    workflow.add_conditional_edges(
        "validate_node",
        route_validation,
        {
            "END": END,
            "DIAGNOSE": "diagnose_node",
            "ESCALATE": "escalate_node"
        }
    )
    workflow.add_edge("diagnose_node", "regenerate_node")
    workflow.add_edge("regenerate_node", "validate_node")
    workflow.add_edge("escalate_node", END)

    return workflow.compile()


# ==============================================================================
# 8. TEST FIXTURE & FAILURE INJECTION GENERATOR
# ==============================================================================

def generate_candidate_evaluation_output(
    student_usn: str = "1KG21CS045",
    company_name: str = "Tata Consultancy Services (TCS)",
    injection_type: str = "NONE"
) -> Dict[str, Any]:
    """
    Generates a realistic student evaluation dossier.
    Supports injecting specific failure modes to test self-healing resilience:
    - 'NONE': Perfectly compliant dossier.
    - 'MAX_MARKS_EXCEEDED': Technical Depth marks awarded 38 (exceeds faculty max 30).
    - 'CREDIT_CEILING_EXCEEDED': Credits set to 24 (exceeds max 16).
    - 'UNSANDBOXED_EXECUTION': Sandbox disabled / arbitrary host execution.
    - 'STIPEND_FLOOR_VIOLATION': Corrupt negative stipend (-5000 INR).
    - 'COMPOUND_FAULTS': Multiple simultaneous failures (Marks 38, Credits 22, Sandbox False).
    - 'FATAL_UNRECOVERABLE': Injects irreparable cryptographic flaw that exhausts budget and escalates to Human Desk.
    """
    student = get_student_profile(student_usn) or {
        "usn": student_usn,
        "name": "Student",
        "branch": "CSE",
        "cgpa": 8.5
    }

    base = {
        "evaluation_id": f"EVAL-{uuid.uuid4().hex[:8].upper()}",
        "student_usn": student.get("usn", student_usn),
        "student_name": student.get("name", "Student"),
        "student_branch": student.get("branch", "CSE"),
        "target_company": company_name,
        "role": "Research & Innovation Intern",
        "credits_allotted": 16,
        "stipend_monthly": 32000,
        "duration_weeks": 16,
        "evaluations": {
            "technical_depth": 26,   # Max 30
            "system_design": 25,     # Max 30
            "journal_logs": 18,      # Max 20
            "mentor_viva": 17        # Max 20
        },
        "sandbox_environment": {
            "sandbox_contained": True,
            "isolation_type": "DOCKER_SECCOMP",
            "container_id": "box-77fa8901",
            "network_egress_restricted": True,
            "permitted_syscalls": ["read", "write", "openat", "fstat", "exit_group"]
        },
        "fatal_irreparable_anomaly": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Inject specific failures
    if injection_type == "MAX_MARKS_EXCEEDED":
        base["evaluations"]["technical_depth"] = 38  # FAULT: Exceeds 30!

    elif injection_type == "CREDIT_CEILING_EXCEEDED":
        base["credits_allotted"] = 24  # FAULT: Exceeds 16!

    elif injection_type == "UNSANDBOXED_EXECUTION":
        base["sandbox_environment"]["sandbox_contained"] = False  # FAULT: Unsandboxed!
        base["sandbox_environment"]["isolation_type"] = "NONE_HOST_DIRECT"

    elif injection_type == "STIPEND_FLOOR_VIOLATION":
        base["stipend_monthly"] = -5000  # FAULT: Negative / sub-minimum!

    elif injection_type == "COMPOUND_FAULTS":
        base["evaluations"]["technical_depth"] = 38
        base["credits_allotted"] = 24
        base["stipend_monthly"] = 8000
        base["sandbox_environment"]["sandbox_contained"] = False
        base["sandbox_environment"]["isolation_type"] = "HOST_SHELL"

    elif injection_type == "FATAL_UNRECOVERABLE":
        base["fatal_irreparable_anomaly"] = True

    # Compute baseline total
    t_score = sum(base["evaluations"].values())
    base["evaluations"]["total_score"] = t_score
    base["evaluations"]["percentage"] = round((t_score / 100.0) * 100, 2)
    base_str = json.dumps(base, sort_keys=True)
    base["audit_signature"] = hashlib.sha256(base_str.encode("utf-8")).hexdigest()[:16]

    return base


# ==============================================================================
# 9. HIGH-LEVEL RESILIENCE RUNNER (INVOKED VIA API & TESTS)
# ==============================================================================

def run_lab10_ops_resilience(
    student_usn: str = "1KG21CS045",
    company_name: str = "Tata Consultancy Services (TCS)",
    injection_type: str = "MAX_MARKS_EXCEEDED",
    custom_budget: int = 3
) -> Dict[str, Any]:
    """
    Executes the full Lab 10 Ops Resilience pipeline via LangGraph StateGraph.
    Runs self-healing feedback loop until valid or budget exhausted.
    """
    t0 = time.time()
    initial_output = generate_candidate_evaluation_output(student_usn, company_name, injection_type)

    initial_state: Lab10State = {
        "output": initial_output,
        "plan": OPS_RESILIENCE_RUBRIC,
        "report": {},
        "attempts": 0,
        "max_budget": custom_budget,
        "diagnosis_log": [],
        "repaired_fields_history": [],
        "status": "RUNNING",
        "escalation": None,
        "execution_trace": [f"Pipeline initialized with injection mode: '{injection_type}'"]
    }

    graph = build_lab10_resilience_graph()
    final_state = graph.invoke(initial_state)
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    # Log resilience execution event in immutable audit trail
    log_event(
        actor="AURA_RESILIENCE_ENGINE",
        actor_role="COORDINATOR_LOOP",
        action="OPS_RESILIENCE_RUN_COMPLETED",
        metadata={
            "injection_type": injection_type,
            "status": final_state["status"],
            "attempts_used": final_state["attempts"],
            "max_budget": custom_budget,
            "total_diagnoses": len(final_state["diagnosis_log"]),
            "elapsed_ms": elapsed_ms
        }
    )

    return {
        "status": final_state["status"],
        "injection_type": injection_type,
        "attempts_used": final_state["attempts"],
        "max_budget": custom_budget,
        "initial_output": initial_output,
        "repaired_output": final_state["output"],
        "final_report": final_state["report"],
        "diagnosis_log": final_state["diagnosis_log"],
        "repaired_fields_history": final_state["repaired_fields_history"],
        "escalation": final_state.get("escalation"),
        "execution_trace": final_state["execution_trace"],
        "execution_time_ms": elapsed_ms,
        "pitfall_avoided": "Regenerate only the failing part — rebuilding everything wastes budget and churns good work. Preserved untouched components intact."
    }
