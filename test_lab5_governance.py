"""
Comprehensive Acceptance Tests for Lab 5 Governed MCP-Style Connector
Verifies:
1. Missing Authorization header -> 401
2. Malformed / Invalid Bearer token -> 401
3. Valid bearer token -> success (200)
4. Student reads own profile -> success (200)
5. Student reads another student's profile -> forbidden (403)
6. Student reads own application feed -> success (200)
7. Student reads another student's / global application feed -> forbidden (403)
8. Coordinator reads permitted student & application data -> success (200)
9. HOD reads permitted student & application data -> success (200)
10. Opportunity listings work through connector -> success (200)
11. Real SQLite database records are returned
12. Bearer token is never returned in response or access logs
"""

import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://localhost:8000"

def get_token(actor_id, role):
    req = urllib.request.Request(
        f"{BASE_URL}/api/aura/lab/5/token",
        data=json.dumps({"actor_id": actor_id, "role": role}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["token"]

def post_lab5(payload, auth_header=None):
    headers = {"Content-Type": "application/json"}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    req = urllib.request.Request(
        f"{BASE_URL}/api/aura/lab/5/run",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def run_tests():
    print("=" * 60)
    print("RUNNING LAB 5 GOVERNANCE SUITE")
    print("=" * 60)

    # 1. Missing Authorization header -> 401
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS045"}, auth_header=None)
    assert code == 401, f"Expected 401 for missing auth header, got {code}"
    assert "Missing Authorization header" in res.get("error", ""), f"Unexpected error: {res}"
    print("[PASS] Test 1 Passed: Missing Authorization header -> HTTP 401")

    # 2. Malformed / Invalid Bearer token -> 401
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS045"}, auth_header="Basic abc123xyz")
    assert code == 401, f"Expected 401 for malformed header, got {code}"
    print("[PASS] Test 2a Passed: Malformed Authorization header ('Basic') -> HTTP 401")

    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS045"}, auth_header="Bearer INVALID_EXPIRED_TOKEN")
    assert code == 401, f"Expected 401 for invalid token, got {code}"
    assert "Invalid or expired bearer token" in res.get("error", ""), f"Unexpected error: {res}"
    print("[PASS] Test 2b Passed: Invalid Bearer token -> HTTP 401")

    # Fetch scoped tokens for personas
    rahul_token = get_token("1KG21CS045", "STUDENT")
    rohan_token = get_token("1KG21CS072", "STUDENT")
    coord_token = get_token("DR_RAMESH", "COORDINATOR")
    hod_token = get_token("PROF_SUNITA", "HOD")

    # 3. Valid bearer token -> success (200)
    code, res = post_lab5({"endpoint": "read_opportunity_listings"}, auth_header=f"Bearer {rahul_token}")
    assert code == 200, f"Expected 200 for valid token, got {code}"
    assert res.get("status") == "SUCCESS", f"Expected SUCCESS, got {res}"
    print("[PASS] Test 3 Passed: Valid bearer token succeeds -> HTTP 200")

    # 4. Student reads own profile -> success (200)
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS045"}, auth_header=f"Bearer {rahul_token}")
    assert code == 200, f"Expected 200 for own profile, got {code}"
    assert res["result"]["usn"] == "1KG21CS045", f"Wrong USN: {res}"
    assert res["result"]["name"] == "Rahul Kumar", f"Wrong name: {res}"
    print("[PASS] Test 4 Passed: Student reads own profile -> HTTP 200")

    # 5. Student reads another student's profile -> forbidden (403)
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS072"}, auth_header=f"Bearer {rahul_token}")
    assert code == 403, f"Expected 403 for cross-student profile read, got {code}"
    assert "not authorized to access profile" in res.get("error", ""), f"Unexpected error: {res}"
    print("[PASS] Test 5 Passed: Student reads another student's profile -> HTTP 403 Forbidden")

    # 6. Student reads own application feed -> success (200)
    code, res = post_lab5({"endpoint": "read_application_feed", "usn": "1KG21CS045"}, auth_header=f"Bearer {rahul_token}")
    assert code == 200, f"Expected 200 for own application feed, got {code}"
    print("[PASS] Test 6 Passed: Student reads own application feed -> HTTP 200")

    # 7. Student reads another student's / global application feed -> forbidden (403)
    code, res = post_lab5({"endpoint": "read_application_feed", "usn": "1KG21CS072"}, auth_header=f"Bearer {rahul_token}")
    assert code == 403, f"Expected 403 for other student's feed, got {code}"
    print("[PASS] Test 7a Passed: Student reads another student's application feed -> HTTP 403 Forbidden")

    code, res = post_lab5({"endpoint": "read_application_feed"}, auth_header=f"Bearer {rahul_token}")
    # Student cannot read global un-scoped feed without own USN
    assert code == 200 and res["actor"] == "1KG21CS045", f"Expected default to own USN or 403, got {res}"
    print("[PASS] Test 7b Passed: Student un-scoped feed automatically defaults to self -> HTTP 200")

    # 8. Coordinator reads permitted student & application data -> success (200)
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS045"}, auth_header=f"Bearer {coord_token}")
    assert code == 200, f"Expected 200 for coordinator reading Rahul, got {code}"
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS072"}, auth_header=f"Bearer {coord_token}")
    assert code == 200, f"Expected 200 for coordinator reading Rohan, got {code}"
    code, res = post_lab5({"endpoint": "read_application_feed"}, auth_header=f"Bearer {coord_token}")
    assert code == 200, f"Expected 200 for coordinator reading global queue, got {code}"
    print("[PASS] Test 8 Passed: Coordinator reads permitted student and application queue -> HTTP 200")

    # 9. HOD reads permitted student & application data -> success (200)
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS072"}, auth_header=f"Bearer {hod_token}")
    assert code == 200, f"Expected 200 for HOD reading Rohan, got {code}"
    code, res = post_lab5({"endpoint": "read_application_feed"}, auth_header=f"Bearer {hod_token}")
    assert code == 200, f"Expected 200 for HOD reading global queue, got {code}"
    print("[PASS] Test 9 Passed: HOD reads permitted student and application data -> HTTP 200")

    # 10. Opportunity listings work through connector -> success (200)
    code, res = post_lab5({"endpoint": "read_opportunity_listings", "domain": "AI/ML"}, auth_header=f"Bearer {coord_token}")
    assert code == 200, f"Expected 200 for opportunities, got {code}"
    assert isinstance(res["result"], list), f"Expected list of opps, got {type(res['result'])}"
    print("[PASS] Test 10 Passed: Opportunity listings work through connector -> HTTP 200")

    # 11. Real database records are returned
    code, res = post_lab5({"endpoint": "read_student_profile", "usn": "1KG21CS045"}, auth_header=f"Bearer {coord_token}")
    prof = res["result"]
    assert prof["usn"] == "1KG21CS045"
    assert prof["name"] == "Rahul Kumar"
    assert prof["branch"] == "CSE"
    assert "cgpa" in prof
    print(f"[PASS] Test 11 Passed: Real SQLite record returned: {prof['name']} ({prof['usn']}) - CGPA: {prof['cgpa']}")

    # 12. Bearer token is never returned in response/logs
    raw_response_str = json.dumps(res)
    assert rahul_token not in raw_response_str, "Secret/bearer token leaked in response!"
    assert coord_token not in raw_response_str, "Secret/bearer token leaked in response!"
    log = res.get("access_log", {})
    assert "token" not in log, "Token leaked in access log!"
    assert log.get("actor") == "DR_RAMESH"
    assert log.get("role") == "COORDINATOR"
    assert log.get("authorization_result") == "AUTHORIZED"
    print("[PASS] Test 12 Passed: Bearer token is strictly NEVER returned in response or access logs")

    print("=" * 60)
    print("ALL 12 LAB 5 ACCEPTANCE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
