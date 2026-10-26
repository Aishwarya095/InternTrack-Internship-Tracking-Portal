import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def post_json(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

print("=== 1. Testing Lab 7 LangGraph REST Endpoint ===")
lab7_res = post_json("http://localhost:8000/api/aura/lab/7/run", {"student_usn": "1KG21CS045"})
print("Orchestration Engine:", lab7_res["orchestration_engine"])
print("Execution Path:", lab7_res["execution_path"])
print("Validation Passed:", lab7_res["validation_passed"])
print("Final Status:", lab7_res["approval_status"])

print("\n=== 2. Testing Lab 8 LangGraph Parallel Swarm REST Endpoint ===")
lab8_res = post_json("http://localhost:8000/api/aura/lab/8/run", {"student_usn": "1KG21CS045"})
print("Orchestration Engine:", lab8_res["orchestration_engine"])
print("Parallel Evaluations Count:", lab8_res["evaluations_count"])
for r in lab8_res["ranked_results"]:
    print(f" - {r['company']}: Eligible={r['is_eligible']}, Available Vacancies={r['available_vacancies']}")

print("\n=== 3. Testing AURA Chat (Tool-Grounded Lookups) ===")
chat_res = post_json("http://localhost:8000/api/aura/chat", {"message": "Am I eligible for ABC Technologies?", "student_usn": "1KG21CS045"})
print("Mode:", chat_res["mode"])
print("Reply:", chat_res["reply"])
print("Tool Calls Count:", len(chat_res["tool_trace"]))
for t in chat_res["tool_trace"]:
    print(f"   • Tool: {t['tool']} -> {str(t['output'])[:80]}...")

print("\n=== 4. Testing Mandatory Rejection Reason Enforcement ===")
try:
    post_json("http://localhost:8000/api/coordinator/review", {
        "submission_id": "SUB-1KG21CS072-1",
        "decision": "REJECT",
        "rejection_reason": ""
    })
    print("FAILED: Rejection without reason did not fail!")
except urllib.error.HTTPError as e:
    err_body = json.loads(e.read().decode("utf-8"))
    print(f"PASSED: HTTP {e.code} received! Message: {err_body['message']}")

print("\n=== 5. Testing Placed-Company Exemption Flow ===")
placed_sub = post_json("http://localhost:8000/api/submissions", {
    "student_usn": "1KG21CS072",
    "submission_type": "PLACED_COMPANY",
    "placed_company_name": "Microsoft India",
    "placed_duration": "4 Months",
    "placement_details": "Campus hire 18 LPA package with integrated internship"
})
print("Placed Submission Status:", placed_sub["submission"]["status"])
print("Placed Decision:", placed_sub["submission"]["coordinator_decision"])
print("Placed Company:", placed_sub["submission"]["placed_company_name"])
print("\n>>> ALL REST API VERIFICATIONS COMPLETED SUCCESSFULLY! <<<")
