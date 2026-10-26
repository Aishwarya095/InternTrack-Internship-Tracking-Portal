import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def post_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

print("==================================================================")
print("=== TESTING LAB 1: INTERACTIVE 3-STEP CLARIFY -> PLAN -> REVISE ===")
print("==================================================================")

# STEP 1: Student sends "I want an internship."
print("\n--- STEP 1: Student submits vague request 'I want an internship.' ---")
step1_res = post_json("http://localhost:8000/api/aura/lab/1/run", {
    "message": "I want an internship.",
    "student_usn": "1KG21CS045",
    "step": 1
})
print("Phase:", step1_res["phase"])
print("Needs Clarification:", step1_res["needs_clarification"])
print(f"Clarification Questions Count: {len(step1_res['clarification_questions'])}")
for idx, q in enumerate(step1_res["clarification_questions"]):
    print(f"  {q['question']}")

assert step1_res["needs_clarification"] == True
assert len(step1_res["clarification_questions"]) >= 4

# STEP 2: Student provides answers
print("\n--- STEP 2: Student provides answers (Name: Rahul Kumar, USN: 1KG21CS045, Branch: CSE, CGPA: 8.2, Location: Bengaluru) ---")
answers = {
    "name": "Rahul Kumar",
    "usn": "1KG21CS045",
    "branch": "CSE",
    "cgpa": "8.2",
    "preferred_location": "Bengaluru"
}
step2_res = post_json("http://localhost:8000/api/aura/lab/1/run", {
    "message": "Here are my details.",
    "student_usn": "1KG21CS045",
    "step": 2,
    "provided_fields": answers
})
print("Phase:", step2_res["phase"])
print("Plan Title:", step2_res["plan"]["title"])
print("Plan Version:", step2_res["plan"]["version"])
print("Is Editable Plan:", step2_res.get("is_editable"))
print("Acceptance Criterion:", step2_res.get("acceptance_criterion"))
print("Memory Updated:", step2_res["memory_updated"])
print("Memory Badge:", step2_res.get("memory_badge"))
print("Phases Generated:")
for p in step2_res["plan"]["phases"]:
    print(f"  - [{p['phase_id']}] {p['title']} ({p['duration']})")

assert step2_res["plan"]["version"] == 1
assert step2_res["is_editable"] == True
assert step2_res["memory_updated"] == True
assert step2_res["answers_received"]["name"] == "Rahul Kumar"
assert step2_res["answers_received"]["usn"] == "1KG21CS045"
assert step2_res["answers_received"]["branch"] == "CSE"
assert float(step2_res["answers_received"]["cgpa"]) == 8.2
assert step2_res["answers_received"]["preferred_location"] == "Bengaluru"

# STEP 3: Student gives feedback: "Add a milestone for Week 8."
print("\n--- STEP 3: Student gives feedback 'Add a milestone for Week 8.' ---")
step3_res = post_json("http://localhost:8000/api/aura/lab/1/run", {
    "student_usn": "1KG21CS045",
    "step": 3,
    "feedback": "Add a milestone for Week 8."
})
print("Phase:", step3_res["phase"])
print("Title:", step3_res["title"])
print("Plan Version:", step3_res["plan"]["version"])
print("Revision Note:", step3_res["plan"].get("revision_note"))
print("Memory Badge:", step3_res.get("memory_badge"))
print("All Phases in FINAL REVISED PLAN:")
w8_found = False
for p in step3_res["plan"]["phases"]:
    is_w8 = p["phase_id"] == "PHASE-W8" or "Week 8" in p["title"]
    mark = "⭐ [ADDED VIA FEEDBACK]" if is_w8 else " "
    print(f"  - [{p['phase_id']}] {p['title']} ({p['duration']}) {mark}")
    if is_w8:
        w8_found = True
        print(f"      Action Items: {p['action_items']}")
        print(f"      Signoff: {p['signoff_required']}")

assert step3_res["plan"]["version"] == 2
assert w8_found == True
assert step3_res["title"] == "FINAL REVISED PLAN"

print("\n==================================================================")
print("=== TESTING LAB 4 & SUBSEQUENT LABS MEMORY SYNCHRONIZATION ======")
print("==================================================================")

# Verify Lab 4 Memory
lab4_res = post_json("http://localhost:8000/api/aura/lab/4/run", {
    "student_usn": "1KG21CS045",
    "action": "RECALL_CONTEXT"
})
ctx = lab4_res["student_context"]
print("\nLab 4 Recalled Context:")
print("• Has Active Session:", ctx["has_active_session"])
print("• Clarified Answers in SessionState:", ctx["clarified_answers"])
print("• Active Plan in SessionState:", ctx["active_plan_title"])
print("• Final Revised Plan in SessionState:", ctx["revised_plan_title"])
print("• Persistent Database Memory Records Count:", len(ctx.get("history_archive_records", [])))

assert ctx["has_active_session"] == True
assert ctx["clarified_answers"]["branch"] == "CSE"
assert float(ctx["clarified_answers"]["cgpa"]) == 8.2
assert ctx["revised_plan_title"] is not None

# Verify Lab 2 Tools reads this updated memory
print("\n--- Testing Lab 2 Tool-Using Agent with Updated Memory ---")
lab2_res = post_json("http://localhost:8000/api/aura/lab/2/run", {
    "student_usn": "1KG21CS045",
    "target_company": "ABC Technologies"
})
prof_tool = next(t for t in lab2_res["trace"] if t["tool"] == "read_student_profile")
print("Lab 2 read_student_profile tool output:")
print("  Student:", prof_tool["output"]["name"], prof_tool["output"]["usn"])
print("  Branch:", prof_tool["output"]["branch"], "| CGPA:", prof_tool["output"]["cgpa"])
print("  Memory Domain Target:", prof_tool["output"].get("memory_domain_target"))
print("  Plan Version from Memory:", prof_tool["output"].get("plan_version"))
print("  Active Plan Title:", prof_tool["output"].get("active_plan_title"))

assert prof_tool["output"]["plan_version"] == 2

print("\n==================================================================")
print(">>> ALL LAB 1 THREE-STEP & CROSS-LAB MEMORY TESTS PASSED! <<<")
print("==================================================================")
