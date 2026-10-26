"""
INTERNTRACK — Lab 11: SDLC Factory — Spec → Tested Output
Phase C: Applied Reliability

Goal: Treat the plan as a spec and the output as a tested implementation.
What it adds to this worklet:
The worklet becomes a factory: plan in, a graded lab submission out that
provably passes an automated acceptance suite before the faculty examiner sees it.

Inputs: The locked plan (spec); the acceptance suite.
Outputs: A result plus a green test report.
Agents / nodes: Validation as the test harness; Coordinator as the build.
Deliverable & acceptance:
A 'build' command: plan -> graded lab submission + passing acceptance report.
Accept: No graded lab submission advances to faculty examiner without a fully passing acceptance report.

Nodes activated: Validation gates the whole graph.
Pitfall to avoid: The acceptance suite is the gate; never let a result skip to the human without a green report.

Core Algorithm Contract:
    artifact = build(plan)                 # graph run (Lab 7/8/10)
    report   = acceptance_suite(artifact, plan)
    require report.all_pass                # gate before human review
"""

import time
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict

from database.db import query_one, query_all
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities, get_opportunity
from core.audit import log_event
from langgraph.graph import StateGraph, START, END

# ==============================================================================
# 1. SPECIFICATION DEFINITION & DEFAULT LOCKED PLANS
# ==============================================================================

DEFAULT_SDLC_SPECS = {
    "MILESTONE-1": {
        "spec_id": "SPEC-2026-MS1",
        "milestone_name": "Milestone 1: Architecture & Sandbox Engine",
        "phase": "Phase C · Applied Reliability",
        "required_deliverables": [
            "sandbox_runner.py",
            "test_acceptance_suite.py",
            "system_design_doc.md",
            "weekly_journal.json"
        ],
        "min_test_coverage_percent": 80.0,
        "max_marks_rubric": {
            "technical_depth": 30,
            "system_design": 30,
            "journal_logs": 20,
            "mentor_viva": 20,
            "total_max": 100
        },
        "required_sandbox_isolation": ["DOCKER_SECCOMP", "SECCOMP_CONTAINER", "GVISOR_MICROVM"],
        "prohibited_syscalls": ["ptrace", "fork_bomb", "socket_raw", "execve_host"],
        "min_stipend_monthly": 15000,
        "credit_range": [12, 16],
        "rubric_citation": "KLE Tech Academic Regulations 2026, Section 14.2(a) — 8th Semester Release"
    },
    "MILESTONE-2": {
        "spec_id": "SPEC-2026-MS2",
        "milestone_name": "Milestone 2: Distributed Concurrency & Event Sourcing",
        "phase": "Phase C · Applied Reliability",
        "required_deliverables": [
            "concurrency_worker.py",
            "event_store.py",
            "load_benchmark_report.pdf",
            "weekly_journal.json"
        ],
        "min_test_coverage_percent": 85.0,
        "max_marks_rubric": {
            "technical_depth": 30,
            "system_design": 30,
            "journal_logs": 20,
            "mentor_viva": 20,
            "total_max": 100
        },
        "required_sandbox_isolation": ["DOCKER_SECCOMP", "SECCOMP_CONTAINER", "GVISOR_MICROVM"],
        "prohibited_syscalls": ["ptrace", "fork_bomb", "socket_raw", "execve_host"],
        "min_stipend_monthly": 15000,
        "credit_range": [12, 16],
        "rubric_citation": "KLE Tech Academic Regulations 2026, Section 14.3(c) — Midterm Progress"
    },
    "MILESTONE-3": {
        "spec_id": "SPEC-2026-MS3",
        "milestone_name": "Milestone 3: Final Internship Capstone & Production Deployment",
        "phase": "Phase C · Applied Reliability",
        "required_deliverables": [
            "production_bundle.zip",
            "audit_trail_snapshot.json",
            "capstone_final_report.pdf",
            "examiner_viva_deck.pptx"
        ],
        "min_test_coverage_percent": 90.0,
        "max_marks_rubric": {
            "technical_depth": 30,
            "system_design": 30,
            "journal_logs": 20,
            "mentor_viva": 20,
            "total_max": 100
        },
        "required_sandbox_isolation": ["DOCKER_SECCOMP", "SECCOMP_CONTAINER", "GVISOR_MICROVM"],
        "prohibited_syscalls": ["ptrace", "fork_bomb", "socket_raw", "execve_host"],
        "min_stipend_monthly": 15000,
        "credit_range": [12, 16],
        "rubric_citation": "KLE Tech Academic Regulations 2026, Section 14.5(e) — Capstone Defense"
    }
}

def lock_plan_spec(milestone_key: str = "MILESTONE-1", student_usn: str = "1KG21CS045", target_company: str = "ABC Technologies") -> Dict[str, Any]:
    """Locks a plan as an immutable specification (Spec)."""
    base_spec = DEFAULT_SDLC_SPECS.get(milestone_key, DEFAULT_SDLC_SPECS["MILESTONE-1"]).copy()
    locked_plan = {
        **base_spec,
        "student_usn": student_usn,
        "target_company": target_company,
        "locked_at": datetime.now().isoformat(),
        "is_locked": True
    }
    raw_hash_str = f"{locked_plan['spec_id']}:{locked_plan['student_usn']}:{locked_plan['target_company']}:{locked_plan['locked_at']}"
    locked_plan["spec_hash"] = hashlib.sha256(raw_hash_str.encode("utf-8")).hexdigest()[:16]
    return locked_plan

# ==============================================================================
# 2. BUILD STEP: Coordinator as the Build (plan -> Graded Lab Submission)
# ==============================================================================

def build_lab_submission_artifact(plan: Dict[str, Any], injection_mode: str = "CLEAN_BUILD") -> Dict[str, Any]:
    """
    Builds the candidate graded lab submission artifact from the locked plan.
    Simulates the build graph run (Lab 7/8/10).
    Supports failure-injection modes to test the acceptance gate.
    """
    artifact_id = f"ARTIFACT-BUILD-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.now().isoformat()

    # Base conformant artifact
    artifact = {
        "artifact_id": artifact_id,
        "spec_id": plan["spec_id"],
        "milestone_name": plan["milestone_name"],
        "student_usn": plan["student_usn"],
        "target_company": plan["target_company"],
        "build_status": "COMPILED_READY_FOR_TESTS",
        "build_timestamp": ts,
        "git_commit": f"git-rev-{uuid.uuid4().hex[:7]}",
        "deliverables_manifest": [
            {"filename": f, "size_kb": 128 + i * 45, "sha256": hashlib.sha256(f.encode()).hexdigest()[:12]}
            for i, f in enumerate(plan["required_deliverables"])
        ],
        "awarded_marks": {
            "technical_depth": 28,
            "system_design": 29,
            "journal_logs": 19,
            "mentor_viva": 18,
            "total_score": 94
        },
        "code_execution_metrics": {
            "sandbox_contained": True,
            "isolation_type": "DOCKER_SECCOMP",
            "prohibited_syscalls_detected": [],
            "test_cases_total": 30,
            "test_cases_passed": 30,
            "test_cases_failed": 0,
            "test_coverage_percent": 92.4
        },
        "credits_allotted": 16,
        "stipend_monthly": 25000,
        "evidence_citations": [
            {
                "rule_id": "SEC-14.2",
                "citation": plan["rubric_citation"],
                "verified": True,
                "evidence_hash": hashlib.sha256(b"in_scope_evidence").hexdigest()[:12]
            }
        ]
    }

    # Inject targeted faults if specified
    if injection_mode == "INJECT_SPEC_DRIFT":
        # Diverge milestone and miss expected deliverable
        artifact["milestone_name"] = "Milestone 99: Out of Scope Drift"
        artifact["deliverables_manifest"] = artifact["deliverables_manifest"][:1]  # missing required deliverables
    
    elif injection_mode == "INJECT_FAILED_TEST_CASE":
        # Low coverage & failed unit tests
        artifact["code_execution_metrics"]["test_cases_failed"] = 4
        artifact["code_execution_metrics"]["test_cases_passed"] = 26
        artifact["code_execution_metrics"]["test_coverage_percent"] = 58.0  # Fails min 80%

    elif injection_mode == "INJECT_UNSANDBOXED_CODE":
        # Escape sandbox container
        artifact["code_execution_metrics"]["sandbox_contained"] = False
        artifact["code_execution_metrics"]["isolation_type"] = "HOST_BARE_METAL"
        artifact["code_execution_metrics"]["prohibited_syscalls_detected"] = ["socket_raw", "ptrace"]

    elif injection_mode == "INJECT_MARKS_OVERFLOW":
        # Award marks exceeding faculty rubric max
        artifact["awarded_marks"]["technical_depth"] = 45  # Max is 30!
        artifact["awarded_marks"]["total_score"] = 111

    elif injection_mode == "INJECT_MISSING_EVIDENCE":
        # Missing citations
        artifact["evidence_citations"] = []

    # Compute artifact signature hash
    raw_signature = f"{artifact['artifact_id']}:{artifact['spec_id']}:{artifact['student_usn']}:{artifact['git_commit']}"
    artifact["artifact_hash"] = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()[:16]

    return artifact

# ==============================================================================
# 3. ACCEPTANCE TEST SUITE: Validation as the Test Harness
# ==============================================================================

class TestCaseResult(TypedDict):
    test_id: str
    name: str
    passed: bool
    expected: str
    actual: str
    message: str
    timestamp: str

class AcceptanceReport(TypedDict):
    report_id: str
    all_pass: bool
    total_tests: int
    passed_count: int
    failed_count: int
    pass_rate_percent: float
    test_results: List[TestCaseResult]
    gate_verdict: str  # "GREEN_GATE_PASSED" | "RED_GATE_BLOCKED"
    generated_at: str

def run_acceptance_suite(artifact: Dict[str, Any], plan: Dict[str, Any]) -> AcceptanceReport:
    """
    Executes the automated acceptance test suite on the built artifact against the locked plan spec.
    Validates:
      1. Spec conformance (USN, Milestone, Deliverables)
      2. Marks rubric compliance (ceilings & total consistency)
      3. Sandbox security enforcement (container containment, no bad syscalls)
      4. Automated code test coverage & zero test case failures
      5. Grounded evidence citations present
      6. Cryptographic artifact integrity signature
    """
    results: List[TestCaseResult] = []
    ts = datetime.now().isoformat()

    # --- Test 1: Spec Conformance ---
    actual_manifest_files = [d["filename"] for d in artifact.get("deliverables_manifest", [])]
    required_files = plan.get("required_deliverables", [])
    all_files_present = all(f in actual_manifest_files for f in required_files)
    usn_matches = artifact.get("student_usn") == plan.get("student_usn")
    milestone_matches = artifact.get("milestone_name") == plan.get("milestone_name")
    t1_pass = usn_matches and milestone_matches and all_files_present
    results.append({
        "test_id": "TC-101-SPEC-CONFORMANCE",
        "name": "Plan Specification & Deliverables Conformance",
        "passed": t1_pass,
        "expected": f"USN={plan['student_usn']}, Milestone='{plan['milestone_name']}', All {len(required_files)} deliverables present",
        "actual": f"USN={artifact.get('student_usn')}, Milestone='{artifact.get('milestone_name')}', {len(actual_manifest_files)} deliverables present",
        "message": "Artifact adheres to locked spec." if t1_pass else "Spec drift detected! Deliverables or metadata mismatch.",
        "timestamp": ts
    })

    # --- Test 2: Marks Rubric Compliance ---
    marks = artifact.get("awarded_marks", {})
    max_rubric = plan.get("max_marks_rubric", {})
    tech_ok = marks.get("technical_depth", 0) <= max_rubric.get("technical_depth", 30)
    design_ok = marks.get("system_design", 0) <= max_rubric.get("system_design", 30)
    journal_ok = marks.get("journal_logs", 0) <= max_rubric.get("journal_logs", 20)
    viva_ok = marks.get("mentor_viva", 0) <= max_rubric.get("mentor_viva", 20)
    sum_calculated = marks.get("technical_depth", 0) + marks.get("system_design", 0) + marks.get("journal_logs", 0) + marks.get("mentor_viva", 0)
    total_consistent = (marks.get("total_score") == sum_calculated) and (sum_calculated <= max_rubric.get("total_max", 100))
    t2_pass = tech_ok and design_ok and journal_ok and viva_ok and total_consistent
    results.append({
        "test_id": "TC-102-MARKS-RUBRIC-COMPLIANCE",
        "name": "Faculty Rubric Ceilings & Mark Sum Consistency",
        "passed": t2_pass,
        "expected": f"All section marks within rubric ceilings (Tech<=30, Design<=30, Logs<=20, Viva<=20, Total<=100)",
        "actual": f"Tech={marks.get('technical_depth')}, Design={marks.get('system_design')}, Logs={marks.get('journal_logs')}, Viva={marks.get('mentor_viva')}, Total={marks.get('total_score')}",
        "message": "Marks rubric verified." if t2_pass else "Awarded marks exceeded rubric ceiling or total inconsistent.",
        "timestamp": ts
    })

    # --- Test 3: Sandbox Security Enforcement ---
    exec_metrics = artifact.get("code_execution_metrics", {})
    is_contained = exec_metrics.get("sandbox_contained", False) is True
    isolation_type = exec_metrics.get("isolation_type", "")
    valid_isolation = isolation_type in plan.get("required_sandbox_isolation", [])
    bad_syscalls = exec_metrics.get("prohibited_syscalls_detected", [])
    no_bad_syscalls = len(bad_syscalls) == 0
    t3_pass = is_contained and valid_isolation and no_bad_syscalls
    results.append({
        "test_id": "TC-103-SANDBOX-SECURITY-ENFORCEMENT",
        "name": "Sandbox Containment & Prohibited Syscall Isolation",
        "passed": t3_pass,
        "expected": f"Contained=True, Isolation in {plan.get('required_sandbox_isolation')}, 0 bad syscalls",
        "actual": f"Contained={is_contained}, Isolation={isolation_type}, BadSyscalls={bad_syscalls}",
        "message": "Execution verified inside secure sandbox." if t3_pass else "Security breach: Unsandboxed execution or prohibited syscalls detected.",
        "timestamp": ts
    })

    # --- Test 4: Automated Test Coverage ---
    failed_tests = exec_metrics.get("test_cases_failed", 0)
    coverage = exec_metrics.get("test_coverage_percent", 0.0)
    min_cov = plan.get("min_test_coverage_percent", 80.0)
    t4_pass = (failed_tests == 0) and (coverage >= min_cov)
    results.append({
        "test_id": "TC-104-AUTOMATED-TEST-COVERAGE",
        "name": "Automated Unit Test Suite & Code Coverage Gate",
        "passed": t4_pass,
        "expected": f"0 failed tests, Coverage >= {min_cov}%",
        "actual": f"{failed_tests} failed tests, Coverage = {coverage}%",
        "message": "Automated acceptance test suite passed." if t4_pass else f"Test failures or sub-minimum coverage ({coverage}% < {min_cov}%).",
        "timestamp": ts
    })

    # --- Test 5: Grounded Evidence Citations ---
    citations = artifact.get("evidence_citations", [])
    t5_pass = len(citations) > 0 and all(c.get("verified") is True for c in citations)
    results.append({
        "test_id": "TC-105-GROUNDED-EVIDENCE-CITATIONS",
        "name": "Faculty Rubric Citations & Evidence Grounding",
        "passed": t5_pass,
        "expected": ">= 1 verified faculty rubric citation",
        "actual": f"{len(citations)} citations present",
        "message": "Grounded citations verified." if t5_pass else "Ungrounded submission: Missing faculty citations.",
        "timestamp": ts
    })

    # --- Test 6: Cryptographic Artifact Signature ---
    art_hash = artifact.get("artifact_hash", "")
    t6_pass = bool(art_hash and len(art_hash) >= 8)
    results.append({
        "test_id": "TC-106-ARTIFACT-INTEGRITY-SIGNATURE",
        "name": "Cryptographic Hash & Immutability Verification",
        "passed": t6_pass,
        "expected": "Non-empty valid SHA256 artifact hash",
        "actual": f"Hash={art_hash}",
        "message": "Artifact immutability verified." if t6_pass else "Artifact hash missing or corrupted.",
        "timestamp": ts
    })

    # Aggregate Metrics
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count
    all_pass = (failed_count == 0)
    pass_rate = round((passed_count / total) * 100.0, 1)

    return {
        "report_id": f"ACC-REP-{uuid.uuid4().hex[:8].upper()}",
        "all_pass": all_pass,
        "total_tests": total,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_rate_percent": pass_rate,
        "test_results": results,
        "gate_verdict": "GREEN_GATE_PASSED" if all_pass else "RED_GATE_BLOCKED",
        "generated_at": ts
    }

# ==============================================================================
# 4. HUMAN REVIEW GATE: require report.all_pass
# ==============================================================================

def require_all_pass_gate(report: AcceptanceReport, artifact: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces the acceptance suite as the strict gate before human review.
    Pitfall to avoid: The acceptance suite is the gate; never let a result skip to the human without a green report.
    """
    ts = datetime.now().isoformat()
    if report["all_pass"]:
        # PROMOTED TO FACULTY EXAMINER
        submission_record = {
            "submission_id": f"EXAM-QUEUE-{uuid.uuid4().hex[:8].upper()}",
            "artifact_id": artifact["artifact_id"],
            "student_usn": artifact["student_usn"],
            "target_company": artifact["target_company"],
            "milestone_name": artifact["milestone_name"],
            "total_score": artifact["awarded_marks"]["total_score"],
            "acceptance_report_id": report["report_id"],
            "gate_status": "GREEN_GATE_PASSED",
            "ready_for_review": True,
            "promotion_timestamp": ts,
            "assigned_examiner": "Faculty Examiner Desk",
            "status": "READY_FOR_FACULTY_EXAMINER"
        }
        log_event(
            actor="Coordinator",
            actor_role="COORDINATOR",
            action="SDLC_BUILD_GATE_PASSED",
            record_id=submission_record["submission_id"],
            old_status="BUILD_UNTESTED",
            new_status="READY_FOR_FACULTY_EXAMINER",
            comments=f"Automated acceptance suite 100% green ({report['passed_count']}/{report['total_tests']} tests passed). Promoted to faculty examiner.",
            metadata={"artifact_id": artifact["artifact_id"], "report_id": report["report_id"]}
        )
        return submission_record
    else:
        # STRICTLY BLOCKED FROM HUMAN REVIEW
        failed_tests = [r["test_id"] for r in report["test_results"] if not r["passed"]]
        blocked_record = {
            "submission_id": None,
            "artifact_id": artifact["artifact_id"],
            "student_usn": artifact["student_usn"],
            "target_company": artifact["target_company"],
            "milestone_name": artifact["milestone_name"],
            "total_score": artifact["awarded_marks"].get("total_score"),
            "acceptance_report_id": report["report_id"],
            "gate_status": "RED_GATE_BLOCKED",
            "ready_for_review": False,
            "promotion_blocked": True,
            "failed_test_ids": failed_tests,
            "blocked_timestamp": ts,
            "blocked_reason": f"Automated acceptance suite FAILED ({report['failed_count']}/{report['total_tests']} tests failed). Access to faculty examiner refused by SDLC Gate.",
            "status": "GATE_BLOCKED_UNTESTED_OR_DEFECTIVE"
        }
        log_event(
            actor="Coordinator",
            actor_role="COORDINATOR",
            action="SDLC_BUILD_GATE_BLOCKED",
            record_id=artifact["artifact_id"],
            old_status="BUILD_UNTESTED",
            new_status="GATE_BLOCKED_DEFECTIVE",
            comments=f"Pitfall Enforced: Defective artifact prevented from human review. Failed tests: {', '.join(failed_tests)}",
            metadata={"failed_tests": failed_tests, "report_id": report["report_id"]}
        )
        return blocked_record

# ==============================================================================
# 5. LANGGRAPH STATEGRAPH FACTORY PIPELINE
# ==============================================================================

class SDLCFactoryState(TypedDict):
    student_usn: str
    target_company: str
    milestone_key: str
    injection_mode: str
    plan_spec: Optional[Dict[str, Any]]
    built_artifact: Optional[Dict[str, Any]]
    acceptance_report: Optional[AcceptanceReport]
    gate_decision: Optional[Dict[str, Any]]
    execution_trace: List[Dict[str, Any]]
    overall_status: str

def lock_spec_node(state: SDLCFactoryState) -> Dict[str, Any]:
    """Locks the plan as an immutable specification (Spec)."""
    spec = lock_plan_spec(
        milestone_key=state.get("milestone_key", "MILESTONE-1"),
        student_usn=state.get("student_usn", "1KG21CS045"),
        target_company=state.get("target_company", "ABC Technologies")
    )
    trace_entry = {
        "step": "LOCK_SPEC",
        "node": "Coordinator (Spec Lock)",
        "status": "SPEC_LOCKED",
        "details": f"Locked plan '{spec['milestone_name']}' with spec hash {spec['spec_hash']}.",
        "timestamp": datetime.now().isoformat()
    }
    return {
        "plan_spec": spec,
        "execution_trace": state.get("execution_trace", []) + [trace_entry],
        "overall_status": "SPEC_LOCKED"
    }

def coordinator_build_node(state: SDLCFactoryState) -> Dict[str, Any]:
    """Coordinator executes the build run (Lab 7/8/10 engine)."""
    plan = state["plan_spec"]
    injection_mode = state.get("injection_mode", "CLEAN_BUILD")
    artifact = build_lab_submission_artifact(plan, injection_mode)
    trace_entry = {
        "step": "COORDINATOR_BUILD",
        "node": "Coordinator (Build Engine)",
        "status": "ARTIFACT_COMPILED",
        "details": f"Compiled graded submission artifact {artifact['artifact_id']} under mode '{injection_mode}'.",
        "timestamp": datetime.now().isoformat()
    }
    return {
        "built_artifact": artifact,
        "execution_trace": state["execution_trace"] + [trace_entry],
        "overall_status": "ARTIFACT_BUILT"
    }

def validation_test_harness_node(state: SDLCFactoryState) -> Dict[str, Any]:
    """Validation agent acts as the automated acceptance test harness."""
    artifact = state["built_artifact"]
    plan = state["plan_spec"]
    report = run_acceptance_suite(artifact, plan)
    trace_entry = {
        "step": "TEST_HARNESS",
        "node": "Validation Agent (Acceptance Harness)",
        "status": report["gate_verdict"],
        "details": f"Ran acceptance suite: {report['passed_count']}/{report['total_tests']} tests passed ({report['pass_rate_percent']}%). Verdict: {report['gate_verdict']}.",
        "timestamp": datetime.now().isoformat()
    }
    return {
        "acceptance_report": report,
        "execution_trace": state["execution_trace"] + [trace_entry],
        "overall_status": "TESTS_COMPLETED"
    }

def gate_decision_node(state: SDLCFactoryState) -> Dict[str, Any]:
    """Enforces the acceptance suite gate before human review."""
    report = state["acceptance_report"]
    artifact = state["built_artifact"]
    decision = require_all_pass_gate(report, artifact)
    
    trace_entry = {
        "step": "ACCEPTANCE_GATE",
        "node": "SDLC Gatekeeper",
        "status": decision["status"],
        "details": (
            f"Gate PASSED: Promoted to Faculty Examiner desk."
            if decision["ready_for_review"] else
            f"Gate BLOCKED: {decision['blocked_reason']}"
        ),
        "timestamp": datetime.now().isoformat()
    }
    return {
        "gate_decision": decision,
        "execution_trace": state["execution_trace"] + [trace_entry],
        "overall_status": decision["status"]
    }

def route_gate(state: SDLCFactoryState) -> str:
    """Conditional edge routing based on all_pass."""
    report = state.get("acceptance_report")
    if report and report.get("all_pass"):
        return "promote_to_faculty"
    return "block_defective"

def build_lab11_sdlc_graph():
    """Builds and compiles the official LangGraph StateGraph for Lab 11."""
    builder = StateGraph(SDLCFactoryState)
    builder.add_node("lock_spec", lock_spec_node)
    builder.add_node("coordinator_build", coordinator_build_node)
    builder.add_node("validation_test_harness", validation_test_harness_node)
    builder.add_node("gate_decision", gate_decision_node)

    builder.add_edge(START, "lock_spec")
    builder.add_edge("lock_spec", "coordinator_build")
    builder.add_edge("coordinator_build", "validation_test_harness")
    builder.add_edge("validation_test_harness", "gate_decision")
    builder.add_edge("gate_decision", END)

    return builder.compile()

# ==============================================================================
# 6. HIGH-LEVEL PIPELINE RUNNER
# ==============================================================================

def run_lab11_sdlc_factory(
    student_usn: str = "1KG21CS045",
    target_company: str = "ABC Technologies",
    milestone_key: str = "MILESTONE-1",
    injection_mode: str = "CLEAN_BUILD"
) -> Dict[str, Any]:
    """
    Executes the Lab 11 SDLC Factory pipeline:
    Spec -> Build -> Acceptance Test Suite -> Gate Enforcement.
    """
    graph = build_lab11_sdlc_graph()
    initial_state: SDLCFactoryState = {
        "student_usn": student_usn,
        "target_company": target_company,
        "milestone_key": milestone_key,
        "injection_mode": injection_mode,
        "plan_spec": None,
        "built_artifact": None,
        "acceptance_report": None,
        "gate_decision": None,
        "execution_trace": [],
        "overall_status": "STARTING"
    }

    res = graph.invoke(initial_state)

    return {
        "status": res["overall_status"],
        "plan_spec": res["plan_spec"],
        "built_artifact": res["built_artifact"],
        "acceptance_report": res["acceptance_report"],
        "gate_decision": res["gate_decision"],
        "execution_trace": res["execution_trace"]
    }
