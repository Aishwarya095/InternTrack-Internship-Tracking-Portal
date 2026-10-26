-- INTERNTRACK Canonical Relational Database Schema
-- SQLite3 DDL with Foreign Keys & Strict Integrity Checks

PRAGMA foreign_keys = ON;

-- 1. Users & RBAC
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('STUDENT', 'COORDINATOR', 'HOD', 'ADMIN')),
    usn TEXT UNIQUE,
    full_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- 2. Student Profiles
CREATE TABLE IF NOT EXISTS student_profiles (
    usn TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    branch TEXT NOT NULL,
    semester INTEGER NOT NULL DEFAULT 8,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    cgpa REAL NOT NULL CHECK(cgpa >= 0.0 AND cgpa <= 10.0),
    backlogs INTEGER NOT NULL DEFAULT 0 CHECK(backlogs >= 0),
    credits INTEGER NOT NULL DEFAULT 0,
    skills TEXT, -- JSON array
    preferred_domains TEXT, -- JSON array
    preferred_locations TEXT, -- JSON array
    placement_status TEXT NOT NULL DEFAULT 'NOT_PLACED' CHECK(placement_status IN ('NOT_PLACED', 'PLACED_COMPANY', 'OPTED_OUT')),
    placed_company TEXT,
    placement_details TEXT,
    placement_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 3. Opportunities Catalog (with Dynamic Vacancy Management)
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    location TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'ON_SITE' CHECK(mode IN ('ON_SITE', 'REMOTE', 'HYBRID')),
    min_cgpa REAL NOT NULL DEFAULT 6.0,
    max_backlogs INTEGER NOT NULL DEFAULT 0,
    required_branch TEXT,
    required_skills TEXT,
    duration TEXT NOT NULL, -- e.g. '3-4 Months'
    stipend_monthly REAL DEFAULT 0.0,
    start_date TEXT,
    end_date TEXT,
    total_vacancies INTEGER NOT NULL CHECK(total_vacancies > 0),
    filled_vacancies INTEGER NOT NULL DEFAULT 0 CHECK(filled_vacancies >= 0),
    available_vacancies INTEGER NOT NULL CHECK(available_vacancies >= 0),
    deadline TEXT NOT NULL,
    eligibility_criteria TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'PUBLISHED', 'CLOSED', 'EXPIRED')),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 4. Student Submissions & Preferences (Multi-submission versioned history)
CREATE TABLE IF NOT EXISTS student_submissions (
    id TEXT PRIMARY KEY,
    student_usn TEXT NOT NULL,
    submission_version INTEGER NOT NULL DEFAULT 1,
    submission_type TEXT NOT NULL DEFAULT 'NORMAL' CHECK(submission_type IN ('NORMAL', 'PLACED_COMPANY')),
    -- Placed Company Fields
    placed_company_name TEXT,
    placement_details TEXT,
    placed_duration TEXT,
    -- Normal Company Preferences (Up to 4)
    pref_1_company TEXT,
    pref_1_role TEXT,
    pref_1_location TEXT,
    pref_1_remarks TEXT,
    pref_2_company TEXT,
    pref_2_role TEXT,
    pref_2_location TEXT,
    pref_2_remarks TEXT,
    pref_3_company TEXT,
    pref_3_role TEXT,
    pref_3_location TEXT,
    pref_3_remarks TEXT,
    pref_4_company TEXT,
    pref_4_role TEXT,
    pref_4_location TEXT,
    pref_4_remarks TEXT,
    -- Workflow Status
    status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN (
        'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'CORRECTION_REQUIRED',
        'REJECTED', 'COORDINATOR_APPROVED', 'HOD_REVIEW', 'HOD_APPROVED', 'CONFIRMED', 'WITHDRAWN'
    )),
    coordinator_decision TEXT,
    rejection_reason TEXT, -- MANDATORY if status = 'REJECTED'
    coordinator_comments TEXT,
    approved_company TEXT,
    approved_role TEXT,
    approved_duration TEXT,
    coordinator_id TEXT,
    coordinator_timestamp TEXT,
    hod_status TEXT DEFAULT 'PENDING' CHECK(hod_status IN ('PENDING', 'APPROVED', 'REJECTED', 'NOT_REQUIRED')),
    hod_comments TEXT,
    hod_timestamp TEXT,
    submitted_at TEXT NOT NULL,
    FOREIGN KEY(student_usn) REFERENCES student_profiles(usn)
);

-- 5. Confirmed Internships (3-4 Month Execution)
CREATE TABLE IF NOT EXISTS internships (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    student_usn TEXT NOT NULL,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    domain TEXT,
    internship_type TEXT NOT NULL CHECK(internship_type IN ('NORMAL', 'PLACED_COMPANY')),
    mentor_name TEXT,
    coordinator_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    expected_end_date TEXT NOT NULL,
    actual_end_date TEXT,
    duration TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'UPCOMING' CHECK(status IN ('UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(submission_id) REFERENCES student_submissions(id),
    FOREIGN KEY(student_usn) REFERENCES student_profiles(usn)
);

-- 6. Bi-Weekly Progress Reports & Journals
CREATE TABLE IF NOT EXISTS progress_reports (
    id TEXT PRIMARY KEY,
    internship_id TEXT NOT NULL,
    student_usn TEXT NOT NULL,
    reporting_period TEXT NOT NULL, -- e.g. 'Weeks 1-2', 'Weeks 3-4'
    submission_date TEXT NOT NULL,
    work_completed TEXT NOT NULL,
    skills_learned TEXT,
    challenges TEXT,
    next_objectives TEXT,
    hours_logged INTEGER NOT NULL CHECK(hours_logged >= 0),
    mentor_comments TEXT,
    status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN ('DRAFT', 'SUBMITTED', 'REVIEWED', 'NEEDS_CORRECTION')),
    reviewed_at TEXT,
    FOREIGN KEY(internship_id) REFERENCES internships(id),
    FOREIGN KEY(student_usn) REFERENCES student_profiles(usn)
);

-- 7. Final Evaluations & Academic Credits
CREATE TABLE IF NOT EXISTS evaluations (
    id TEXT PRIMARY KEY,
    internship_id TEXT NOT NULL UNIQUE,
    student_usn TEXT NOT NULL,
    employer_feedback TEXT,
    mentor_assessment TEXT,
    mentor_score REAL CHECK(mentor_score >= 0.0 AND mentor_score <= 40.0),
    presentation_score REAL CHECK(presentation_score >= 0.0 AND presentation_score <= 30.0),
    report_score REAL CHECK(report_score >= 0.0 AND report_score <= 30.0),
    total_score REAL CHECK(total_score >= 0.0 AND total_score <= 100.0),
    proposed_grade TEXT CHECK(proposed_grade IN ('S', 'A', 'B', 'C', 'D', 'F')),
    academic_credits INTEGER NOT NULL DEFAULT 12,
    evaluator_name TEXT NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL' CHECK(approval_status IN ('PENDING_APPROVAL', 'APPROVED', 'FINALIZED')),
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY(internship_id) REFERENCES internships(id),
    FOREIGN KEY(student_usn) REFERENCES student_profiles(usn)
);

-- 8. Immutable Audit Trail
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    record_id TEXT,
    old_status TEXT,
    new_status TEXT,
    comments TEXT,
    metadata TEXT,
    timestamp TEXT NOT NULL
);

-- 9. Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    recipient_usn_or_role TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- 10. Agent Runs & Tool Tracing
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    lab_number INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    student_usn TEXT,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    budget_limit INTEGER DEFAULT 10,
    budget_used INTEGER DEFAULT 0,
    trace_log TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT
);

-- 11. Memory Records (Lab 4: Short-term SessionState & Long-term HistoryArchive)
CREATE TABLE IF NOT EXISTS memory_records (
    id TEXT PRIMARY KEY,
    student_usn TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK(memory_type IN ('SESSION_STATE', 'HISTORICAL_PLAN', 'CLARIFICATION_ANSWER', 'REVISION_NOTE')),
    key_name TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(student_usn) REFERENCES student_profiles(usn)
);
