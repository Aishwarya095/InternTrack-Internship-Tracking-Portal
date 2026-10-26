# InternTrack (AURA) — Autonomous University Regulatory Assistant

## Guiding Institutional Principle
> *"Agents draft and flag; a named human approves."*  
Autonomous multi-agent swarms assist in screening, matching, and validating deliverables, but consequential state transitions (committing company placements, awarding 12 academic credits) are strictly governed by human approval checkpoints.

---

## Key Features & Architectural Roles

InternTrack enforces role-based access control (RBAC) across three primary personas:

1. **Student (`STUDENT`):**
   * Automatic routing to **Internship Form**.
   * Multi-preference selection (Preferences 1 to 4) or Placed-Company direct bypass.
   * Multi-version resubmission handling ($v+1$) upon feedback.
   * Weekly/monthly progress journal submission.
   * View published credits & grades (with sensitive faculty remarks masked).

2. **Internship Coordinator (`COORDINATOR`):**
   * Automatic routing to **Coordinator Review Queue**.
   * Batch screening against academic criteria (minimum CGPA $\ge 7.0$, 0 active backlogs).
   * Consequential human approval gate: approving applications dynamically decrements vacancies.
   * Rubric mark entry across Mentor (40), Presentation (30), and Report (30).
   * **Direct Authority to Award 12 Academic Credits!**

3. **Head of Department (`HOD`):**
   * Automatic routing to **HOD Sanction Desk**.
   * Apex departmental governance and official sanction.
   * Cohort-wide grade distribution monitoring.
   * **Direct Authority to Award 12 Academic Credits!**
   * Real-time inspection of immutable append-only audit trail.

---

## Master 14-Lab Implementation Matrix (81 / 81 Passed)

| Lab # | Phase | Title & Capability | Implementation Module | Tests |
| :---: | :---: | :--- | :--- | :---: |
| **Lab 1** | Phase A | **Agent vs Chatbot:** Clarify-Plan-Revise Goal Loop | `aura/lab1_planner.py` | Integrated |
| **Lab 2** | Phase A | **Tool-Using Agent:** ReAct Schema SQL Lookups | `aura/lab2_tools.py` | Integrated |
| **Lab 3** | Phase A | **Skill Creation:** 4 Schema-Typed Capability Units | `aura/lab3_skills.py` | Integrated |
| **Lab 4** | Phase A | **Memory & Retrieval:** SessionState & SQLite History | `aura/lab4_memory.py` | Integrated |
| **Lab 5** | Phase A | **MCP-Style Connector:** Scoped Bearer Token Auth | `aura/lab5_connector.py` | Integrated |
| **Lab 6** | Phase A | **Controlled Runtime:** Step Budgets & Coordinator Gate | `aura/lab6_runtime.py` | Integrated |
| **Lab 7** | Phase B | **LangGraph Workflow:** StateGraph & Checkpointing | `aura/lab7_langgraph.py` | Integrated |
| **Lab 8** | Phase B | **Parallel Swarm:** 4-Preference Fan-Out / Fan-In Reducer | `aura/lab8_langgraph.py` | 13 Tests |
| **Lab 9** | Phase C | **Deep Research & Grounding:** Evidence Tables & Defense | `aura/lab9_grounding.py` | 9 Tests |
| **Lab 10** | Phase C | **Ops Resilience:** Jitter Retry, Circuit Breaker & DLQ | `aura/lab10_resilience.py` | 9 Tests |
| **Lab 11** | Phase C | **SDLC Factory:** Policy Ingestion & Green Acceptance Gate | `aura/lab11_sdlc_factory.py` | 9 Tests |
| **Lab 12** | Phase D | **Safety & Governance:** Gate, Masking & 1-Click Rollback | `aura/lab12_governance.py` | 9 Tests |
| **Lab 13** | Phase D | **Discipline Specialists:** 5 Engineering Domain Packs | `aura/lab13_discipline_specialists.py` | 9 Tests |
| **Lab 14** | Phase D | **Capstone Studio:** Full Integrated University Stack | `aura/lab14_capstone.py` | 10 Tests |
| **TOTAL** | | **All 14 Labs Implemented & Unit-Tested** | **Full University System** | **81 / 81 PASS** |

---

## Live Cohort State (`database/interntrack.db`)
* **65 Students** registered across the department.
* **50 Corporate Opportunities** with **207 Available Vacancies**.
* **19 Placed-Company Direct Confirmations**.
* **44 Active Tracked Internships** with verified progress journals.
* **44 Milestone Evaluations** with authentic S, A, and B grades.

---

## Quick Start & Running Locally

### 1. Install Requirements
```bash
pip install -r requirements.txt
```

### 2. Run the Web Application
```bash
python server.py
```
Open **`http://localhost:8000/`** in your browser.

### 3. Run the Master 14-Lab Verification Suite
```bash
python run_master_verification_1_to_14.py
```
Verifies all 81 unit tests across Labs 1 through 14.

---

## Official Documentation Artifacts
* `InternTrack_AURA_14_Labs_Master_Implementation_and_Test_Report.pdf`: Complete 14-lab technical report with architectural diagrams and test proofs.
* `AAI_26ECAC401_Lab_Worklet_Review_Sheet_LAB1_to_14_FILLED.pdf`: Official university evaluation review sheet filled for all 14 labs.
