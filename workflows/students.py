"""
INTERNTRACK — Student Profile Workflow
Handles student personal and academic records, placement state, and dashboard stats.
"""

from database.db import query_one, query_all, execute
from datetime import datetime

def get_student_profile(usn):
    """Retrieves full student profile by USN."""
    return query_one("SELECT * FROM student_profiles WHERE usn = ?", (usn,))

def list_all_students(search_query=None):
    """Lists students, optionally filtered by name/USN/branch."""
    if search_query:
        param = f"%{search_query}%"
        return query_all("""
        SELECT * FROM student_profiles 
        WHERE usn LIKE ? OR name LIKE ? OR branch LIKE ? OR placed_company LIKE ?
        ORDER BY usn ASC
        """, (param, param, param, param))
    return query_all("SELECT * FROM student_profiles ORDER BY usn ASC")

def update_student_profile(usn, data):
    """Updates profile attributes such as phone, skills, and preferences."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute("""
    UPDATE student_profiles SET
        phone = COALESCE(?, phone),
        skills = COALESCE(?, skills),
        preferred_domains = COALESCE(?, preferred_domains),
        preferred_locations = COALESCE(?, preferred_locations),
        updated_at = ?
    WHERE usn = ?
    """, (data.get("phone"), data.get("skills"), data.get("preferred_domains"),
          data.get("preferred_locations"), now, usn))
    return get_student_profile(usn)

def mark_placed_company(usn, company, package_details, duration="4 Months", placement_date=None):
    """
    Marks a student as PLACED_COMPANY.
    Directly bypasses the normal application workflow.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p_date = placement_date or now[:10]
    execute("""
    UPDATE student_profiles SET
        placement_status = 'PLACED_COMPANY',
        placed_company = ?,
        placement_details = ?,
        placement_date = ?,
        updated_at = ?
    WHERE usn = ?
    """, (company, package_details, p_date, now, usn))
    return get_student_profile(usn)

def upsert_student_profile(usn, name, branch="CSE", cgpa=8.0, preferred_location="Bengaluru", email=None):
    """
    Inserts student if they do not exist, or updates their existing profile.
    Guarantees the student profile is saved in the database for tracking and memory integrity.
    """
    import json
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_usn = (usn or "1KG21CS045").strip().upper()
    student_email = email or f"{clean_usn.lower()}@college.edu"
    
    existing = get_student_profile(clean_usn)
    loc_json = json.dumps([preferred_location] if preferred_location else ["Bengaluru"])
    
    try:
        cgpa_val = float(str(cgpa).replace("CGPA", "").strip())
    except Exception:
        cgpa_val = 8.0

    if not existing:
        execute("""
        INSERT INTO student_profiles (
            usn, name, branch, semester, email, phone, cgpa, backlogs, credits,
            skills, preferred_domains, preferred_locations, placement_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, 8, ?, '9876543210', ?, 0, 160, '["Python", "Problem Solving"]', '["AI/ML"]', ?, 'NOT_PLACED', ?, ?)
        """, (clean_usn, name or "Student", branch or "CSE", student_email, cgpa_val, loc_json, now, now))
    else:
        execute("""
        UPDATE student_profiles SET
            name = COALESCE(?, name),
            branch = COALESCE(?, branch),
            cgpa = COALESCE(?, cgpa),
            preferred_locations = COALESCE(?, preferred_locations),
            updated_at = ?
        WHERE usn = ?
        """, (name or existing["name"], branch or existing["branch"], cgpa_val, loc_json, now, clean_usn))
    return get_student_profile(clean_usn)
