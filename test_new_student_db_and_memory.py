import urllib.request
import json
import sqlite3
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

NEW_USN = "1KG21IS099"
NEW_NAME = "Pooja Hegde"
NEW_BRANCH = "ISE"
NEW_CGPA = "8.7"
NEW_LOC = "Mysuru"

print("==================================================================")
print("=== VERIFYING LAB 1 NEW STUDENT CREATION & MEMORY RETRIEVAL ===")
print("==================================================================")

# 1. Step 1: Vague Request
print(f"\n1. Submitting Step 1 vague prompt for new student ({NEW_USN})...")
s1 = post_json("http://localhost:8000/api/aura/lab/1/run", {
    "message": "I want an internship.",
    "student_usn": NEW_USN,
    "step": 1
})
print("   Phase:", s1["phase"])
print("   Needs Clarification:", s1["needs_clarification"])
print("   Questions Count:", len(s1["clarification_questions"]))
assert s1["needs_clarification"] is True

# 2. Step 2: Submit Clarification Answers
print(f"\n2. Submitting Step 2 answers (Name: {NEW_NAME}, USN: {NEW_USN}, Branch: {NEW_BRANCH}, CGPA: {NEW_CGPA}, Loc: {NEW_LOC})...")
s2 = post_json("http://localhost:8000/api/aura/lab/1/run", {
    "message": "Here are my details.",
    "student_usn": NEW_USN,
    "step": 2,
    "provided_fields": {
        "name": NEW_NAME,
        "usn": NEW_USN,
        "student_usn": NEW_USN,
        "branch": NEW_BRANCH,
        "cgpa": NEW_CGPA,
        "preferred_location": NEW_LOC
    }
})
print("   Phase:", s2["phase"])
print("   Plan Title:", s2["plan"]["title"])
print("   Candidate in Plan:", s2["plan"]["student_name"], f"({s2['plan']['student_usn']})")
print("   Plan Version:", s2["plan"]["version"])
print("   Editable:", s2.get("is_editable"))
assert s2["answers_received"]["usn"] == NEW_USN
assert s2["answers_received"]["name"] == NEW_NAME
assert s2["plan"]["student_usn"] == NEW_USN

# 3. Step 3: Student Feedback Loop
print(f"\n3. Submitting Step 3 feedback 'Add a milestone for Week 8.'...")
s3 = post_json("http://localhost:8000/api/aura/lab/1/run", {
    "student_usn": NEW_USN,
    "step": 3,
    "feedback": "Add a milestone for Week 8."
})
print("   Phase:", s3["phase"])
print("   Title:", s3["title"])
print("   Candidate:", s3["plan"]["student_name"], f"({s3['plan']['student_usn']})")
print("   Plan Version:", s3["plan"]["version"])
assert s3["plan"]["version"] == 2
has_w8 = any(p["phase_id"] == "PHASE-W8" or "Week 8" in p["title"] for p in s3["plan"]["phases"])
assert has_w8 is True

# 4. Direct SQLite Database Inspection
print(f"\n4. Directly querying SQLite database for student profile and memory records...")
conn = sqlite3.connect("database/interntrack.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check student_profiles
cursor.execute("SELECT usn, name, branch, cgpa, preferred_locations, placement_status FROM student_profiles WHERE usn = ?", (NEW_USN,))
prof = cursor.fetchone()
print("   [SQL DB] student_profiles row:")
assert prof is not None, f"Student {NEW_USN} was NOT found in student_profiles table!"
print(f"      USN: {prof['usn']}")
print(f"      Name: {prof['name']}")
print(f"      Branch: {prof['branch']}")
print(f"      CGPA: {prof['cgpa']}")
print(f"      Preferred Locations: {prof['preferred_locations']}")

# Check memory_records
cursor.execute("SELECT id, memory_type, key_name, created_at FROM memory_records WHERE student_usn = ? ORDER BY created_at ASC", (NEW_USN,))
mem_rows = cursor.fetchall()
print(f"   [SQL DB] memory_records rows ({len(mem_rows)} found):")
for r in mem_rows:
    print(f"      [{r['memory_type']}] Key: {r['key_name']} (ID: {r['id']})")
assert len(mem_rows) >= 3, f"Expected at least 3 memory records for {NEW_USN}, found {len(mem_rows)}"
conn.close()

# 5. Cross-Lab Retrieval via Lab 4 Memory Engine
print(f"\n5. Testing Lab 4 context recall for {NEW_USN}...")
lab4_res = post_json("http://localhost:8000/api/aura/lab/4/run", {
    "student_usn": NEW_USN,
    "action": "RECALL_CONTEXT"
})
ctx = lab4_res["student_context"]
print("   Has Active Session:", ctx["has_active_session"])
print("   Clarified Answers:", ctx["clarified_answers"])
print("   Active Plan:", ctx["active_plan_title"])
print("   Revised Plan:", ctx["revised_plan_title"])
print("   History Archive Records Count:", len(ctx["history_archive_records"]))
assert ctx["has_active_session"] is True
assert ctx["clarified_answers"]["name"] == NEW_NAME
assert ctx["clarified_answers"]["branch"] == NEW_BRANCH
assert ctx["revised_plan_title"] is not None

# 6. Cross-Lab Retrieval via Lab 2 Tool-Using Agent
print(f"\n6. Testing Lab 2 Tool Agent grounded lookup for {NEW_USN}...")
lab2_res = post_json("http://localhost:8000/api/aura/lab/2/run", {
    "student_usn": NEW_USN,
    "target_company": "ABC Technologies"
})
prof_tool = next(t for t in lab2_res["trace"] if t["tool"] == "read_student_profile")
print("   Tool read_student_profile returned:")
print("      Candidate:", prof_tool["output"]["name"], prof_tool["output"]["usn"])
print("      Branch:", prof_tool["output"]["branch"], "| CGPA:", prof_tool["output"]["cgpa"])
print("      Plan Version from Memory:", prof_tool["output"].get("plan_version"))
assert prof_tool["output"]["usn"] == NEW_USN
assert prof_tool["output"]["name"] == NEW_NAME
assert prof_tool["output"]["branch"] == NEW_BRANCH
assert prof_tool["output"]["plan_version"] == 2

print("\n==================================================================")
print(">>> ALL CHECKS PASSED: LAB 1 STUDENT ADDED TO DB & RETRIEVABLE! <<<")
print("==================================================================")
