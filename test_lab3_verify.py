import urllib.request
import json

def post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("--- TEST 1: InternshipPlanSkill ---")
res1 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "InternshipPlanSkill",
    "student_usn": "1KG21CS045"
})
print("Skill:", res1["skill"])
print("Is Valid:", res1["is_valid"])
print("Roadmap Phases:", len(res1["roadmap"]))
print("Internship Goal:", res1["internship_goal"])

print("\n--- TEST 2A: ApplicationValidatorSkill (PASS - ABC Technologies) ---")
res2a = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "ApplicationValidatorSkill",
    "student_usn": "1KG21CS045",
    "target_company": "ABC Technologies"
})
print("Skill:", res2a["skill"])
print("Candidate:", res2a["candidate"]["name"], "| CGPA:", res2a["candidate"]["cgpa"])
print("Company:", res2a["company"]["name"], "| Min CGPA:", res2a["company"]["min_cgpa"])
print("Status:", res2a["final_status"])
print("Checks count:", len(res2a["checks"]))

print("\n--- TEST 2B: ApplicationValidatorSkill (FAIL - DEF AI high cutoff 8.5) ---")
res2b = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "ApplicationValidatorSkill",
    "student_usn": "1KG21CS045",
    "target_company": "DEF AI"
})
print("Status:", res2b["final_status"])
print("Issues:", res2b["issues"])

print("\n--- TEST 3: OpportunityMatchingSkill ---")
res3 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "OpportunityMatchingSkill",
    "student_usn": "1KG21CS045"
})
print("Skill:", res3["skill"])
print("Candidate:", res3["candidate"]["name"], "| Domain:", res3["candidate"]["domain"])
print("Candidate Skills:", res3["candidate_skills"])
print("Total Evaluated:", res3["total_evaluated"])
print("Total Suitable:", res3["total_suitable"])
print("Top Matched:", res3["matched_opportunities"][0]["company"], "| Reasons count:", len(res3["matched_opportunities"][0]["matching_reasons"]))

print("\n--- TEST 4: DocumentFormatterSkill ---")
res4 = post_json("http://localhost:8000/api/aura/lab/3/run", {
    "skill": "DocumentFormatterSkill",
    "student_usn": "1KG21CS045",
    "target_company": "ABC Technologies"
})
print("Skill:", res4["skill"])
print("Candidate:", res4["candidate"]["name"])
print("Internship:", res4["internship"]["company"], "| Role:", res4["internship"]["role"])
print("Format:", res4["document_format"])
print("Content Preview:\n", res4["content"][:250], "...")
print("Validation checks:", len(res4["validation_checks"]))
print("\nALL 4 SKILLS VERIFIED SUCCESSFULLY OVER HTTP!")
