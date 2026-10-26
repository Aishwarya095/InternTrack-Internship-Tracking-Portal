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
print("=== TESTING LAB 3: REUSABLE SCHEMA-TYPED SKILLS & PRESENTATION ===")
print("==================================================================")

# 1. InternshipPlanSkill with Candidate 1: Rahul Kumar (1KG21CS045)
print("\n--- 1. Testing InternshipPlanSkill (Candidate: Rahul Kumar) ---")
res1 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "InternshipPlanSkill",
    "student_usn": "1KG21CS045"
})
print("Skill:", res1["skill"])
print("Status:", res1["status_text"])
print("Candidate:", res1["candidate"]["name"], f"({res1['candidate']['usn']})")
print("Branch:", res1["candidate"]["branch"], "| CGPA:", res1["candidate"]["cgpa"])
print("Domain:", res1["domain"])
print("Preferred Companies:", res1["target_companies"])
print("Milestones Count:", len(res1["milestones"]))
print("Validation Checks:")
for chk in res1["validation_checks"]:
    print(f"  ✓ {chk['check']}: {chk['detail']}")
print("Final Result:", res1["final_result"]["badge"])

assert res1["is_valid"] is True
assert res1["candidate"]["name"] == "Rahul Kumar"
assert res1["candidate"]["usn"] == "1KG21CS045"
assert len(res1["milestones"]) == 5
assert len(res1["validation_checks"]) == 6

# 2. InternshipPlanSkill with Candidate 2: Pooja Hegde (1KG21IS099) - Reusability Test
print("\n--- 2. Testing Reusability: InternshipPlanSkill (Candidate: Pooja Hegde 1KG21IS099) ---")
res2 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "InternshipPlanSkill",
    "student_usn": "1KG21IS099"
})
print("Candidate loaded dynamically:", res2["candidate"]["name"], f"({res2['candidate']['usn']})")
print("Branch:", res2["candidate"]["branch"], "| CGPA:", res2["candidate"]["cgpa"])
assert res2["candidate"]["name"] == "Pooja Hegde"
assert res2["candidate"]["usn"] == "1KG21IS099"
assert res2["candidate"]["branch"] == "ISE"
assert res2["is_valid"] is True
print("✓ Reusability Verified: Skill executed identically for different student without hardcoding!")

# 3. ApplicationValidatorSkill
print("\n--- 3. Testing ApplicationValidatorSkill ---")
res3 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "ApplicationValidatorSkill",
    "student_usn": "1KG21CS045"
})
print("Skill:", res3["skill"])
print("Status:", res3["status_text"])
print("Candidate:", res3["candidate"]["name"], f"({res3['candidate']['usn']})")
print("Validation Checks:")
for chk in res3["validation_checks"]:
    print(f"  ✓ {chk['check']}: {chk['detail']}")
print("Issues Count:", len(res3["issues"]))
print("Final Result:", res3["final_result"]["badge"])
assert res3["is_valid"] is True
assert len(res3["validation_checks"]) == 4

# 4. OpportunityMatchingSkill
print("\n--- 4. Testing OpportunityMatchingSkill ---")
res4 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "OpportunityMatchingSkill",
    "student_usn": "1KG21CS045"
})
print("Skill:", res4["skill"])
print("Candidate Skills:", res4["candidate_skills"])
print("Matched Opportunities Count:", len(res4["matched_opportunities"]))
for opp in res4["matched_opportunities"][:3]:
    print(f"  • {opp['company']} ({opp['title']}) -> Score: {opp['match_percentage']}")
assert len(res4["matched_opportunities"]) > 0
assert res4["is_valid"] is True

# 5. DocumentFormatterSkill
print("\n--- 5. Testing DocumentFormatterSkill ---")
res5 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "DocumentFormatterSkill",
    "student_usn": "1KG21CS045"
})
print("Skill:", res5["skill"])
print("Document Format:", res5["document_format"])
print("Allotted Organization:", res5["allotment_details"]["company"])
print("Content length:", len(res5["content"]))
assert res5["document_format"] == "MARKDOWN_DOSSIER"
assert res5["is_valid"] is True

print("\n==================================================================")
print(">>> ALL 4 LAB 3 SKILL VERIFICATIONS & REUSABILITY CHECKS PASSED! <<<")
print("==================================================================")
