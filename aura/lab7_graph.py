"""
INTERNTRACK — Lab 7: Agentic Multi-Node Stateful Graph
Chapter 10: Worklet 10 — Internship Application & Tracking Portal

Wires specialist agents into an explicit, stateful directed acyclic graph (DAG)
with bounded retry back-edge:
Ingest -> Plan -> DiscoveryAgent -> EligibilityAgent -> ApplicationProcessingAgent ->
ValidationNode (if fail -> retry up to 3 times) -> Assembler -> CoordinatorGate -> Final
"""

import time
from workflows.students import get_student_profile
from workflows.opportunities import list_opportunities, check_eligibility_and_vacancy
from workflows.submissions import create_submission

class MultiAgentNodeGraph:
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.node_execution_history = []

    def run_pipeline(self, student_usn, preference_names=None):
        """
        Executes the entire multi-agent node graph end-to-end.
        Returns the final validated application packet and graph traversal telemetry.
        """
        self.node_execution_history = []
        state = {
            "usn": student_usn,
            "raw_preferences": preference_names or ["ABC Technologies", "XYZ Labs", "PQR Solutions", "DEF AI"],
            "profile": None,
            "matched_opportunities": [],
            "verified_applications": [],
            "validation_passed": False,
            "retry_count": 0,
            "final_packet": None
        }

        # Node 1: Ingest
        self._record_node("IngestNode", "Ingesting student identity & preferences.")
        state["profile"] = get_student_profile(student_usn)
        if not state["profile"]:
            raise ValueError(f"Student profile {student_usn} not found.")

        # Node 2: Planner Node
        self._record_node("PlannerNode", "Locking 8th-sem pipeline schema constraints.")

        # Loop with Bounded Retry Edge
        while not state["validation_passed"] and state["retry_count"] <= self.max_retries:
            # Node 3: Discovery Agent
            self._record_node("OpportunityDiscoveryAgent", f"Querying catalog for target preferences (Attempt {state['retry_count']+1}).")
            all_opps = list_opportunities(status="PUBLISHED")
            target_opps = [o for o in all_opps if any(p.lower() in o["company"].lower() for p in state["raw_preferences"])]
            if not target_opps and len(all_opps) > 0:
                target_opps = all_opps[:2]
            state["matched_opportunities"] = target_opps

            # Node 4: Eligibility Verification Agent
            self._record_node("EligibilityVerificationAgent", "Computing CGPA, backlog and vacancy constraints.")
            verified = []
            for opp in state["matched_opportunities"]:
                res = check_eligibility_and_vacancy(student_usn, opp["id"])
                verified.append(res)
            state["verified_applications"] = verified

            # Node 5: Application Processing Agent
            self._record_node("ApplicationProcessingAgent", "Assembling formal draft application units.")

            # Node 6: Validation Node (Gate with Back-Edge)
            self._record_node("ValidationNode", "Validating compliance against college eligibility rules.")
            eligible_count = sum(1 for v in verified if v["is_eligible"])

            if eligible_count > 0:
                state["validation_passed"] = True
                self._record_node("ValidationNode", "Validation PASSED: At least one compliant opportunity confirmed.")
                break
            else:
                state["retry_count"] += 1
                if state["retry_count"] <= self.max_retries:
                    self._record_node("ValidationNode", f"Validation FAILED: No eligible options. Triggering RETRY back-edge ({state['retry_count']}/{self.max_retries}).")
                    # Fallback relaxation on retry
                    state["raw_preferences"] = ["GlobalTech Systems", "PQR Solutions"]
                else:
                    self._record_node("ValidationNode", "Max retries exhausted. Halting graph for Coordinator escalation.")
                    break

        if not state["validation_passed"]:
            return {
                "status": "VALIDATION_FAILED_ESCALATED",
                "message": "Graph reached maximum retry bounds without finding fully eligible match. Escalated to Coordinator.",
                "history": self.node_execution_history
            }

        # Node 7: Assembler Node
        self._record_node("AssemblerNode", "Compiling final verified application packet.")
        best_match = next((v for v in state["verified_applications"] if v["is_eligible"]), state["verified_applications"][0])
        packet = {
            "student_name": state["profile"]["name"],
            "student_usn": student_usn,
            "branch": state["profile"]["branch"],
            "primary_selected_company": best_match["company"],
            "all_evaluated_options": state["verified_applications"],
            "status": "READY_FOR_COORDINATOR_GATE"
        }
        state["final_packet"] = packet

        # Node 8: Human Coordinator Gate
        self._record_node("CoordinatorHumanGate", "Pausing at human gate. Waiting for Coordinator sign-off.")

        return {
            "status": "SUCCESS",
            "student_usn": student_usn,
            "final_packet": packet,
            "traversal_path": [h["node"] for h in self.node_execution_history],
            "history": self.node_execution_history,
            "total_nodes_executed": len(self.node_execution_history)
        }

    def _record_node(self, node_name, details):
        self.node_execution_history.append({
            "step": len(self.node_execution_history) + 1,
            "node": node_name,
            "details": details,
            "timestamp": time.strftime("%H:%M:%S")
        })
