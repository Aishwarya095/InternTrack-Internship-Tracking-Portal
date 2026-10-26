"""
INTERNTRACK — Lab 4: Memory & Retrieval (Short-Term Session vs Long-Term Vector History)
Chapter 10: Worklet 10 — Internship Application & Tracking Portal

Separates ephemeral working session state from persistent historical reference memory.
Provides bi-directional cross-lab memory persistence:
- Lab 1 Clarification questions, student answers, structured plan, and revised plan
  are stored in SessionState and HistoryArchive.
- Labs 2 to 8 dynamically read and utilize this updated memory.
"""

import json
import math
import uuid
from datetime import datetime
from database.db import query_all, query_one, execute
from workflows.submissions import get_submissions_by_student

# In-Memory Cache for Active Working Sessions
_ACTIVE_SESSIONS = {}

class SessionState:
    """Working Memory: Ephemeral active conversation, student answers, and drafting state."""
    def __init__(self, session_id, student_usn):
        self.session_id = session_id
        self.student_usn = student_usn
        self.active_draft = {}
        self.conversation_turn = 0
        self.clarifications_asked = []
        self.student_answers = {}
        self.active_plan = None
        self.revised_plan = None
        self.revision_history = []
        self.ephemeral_notes = []
        self.last_updated = datetime.now().isoformat()

    def update_answers(self, answers_dict):
        """Records student answers to clarification questions."""
        self.student_answers.update(answers_dict)
        self.conversation_turn += 1
        self.last_updated = datetime.now().isoformat()

    def set_plan(self, plan_obj):
        """Stores newly generated structured plan."""
        self.active_plan = plan_obj
        self.last_updated = datetime.now().isoformat()

    def set_revised_plan(self, revised_plan_obj, feedback_text):
        """Stores revised plan and logs revision feedback."""
        self.revised_plan = revised_plan_obj
        self.revision_history.append({
            "feedback": feedback_text,
            "version": revised_plan_obj.get("version", 2),
            "timestamp": datetime.now().isoformat()
        })
        self.last_updated = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "student_usn": self.student_usn,
            "turn": self.conversation_turn,
            "clarifications_asked": self.clarifications_asked,
            "student_answers": self.student_answers,
            "has_active_plan": self.active_plan is not None,
            "active_plan": self.active_plan,
            "has_revised_plan": self.revised_plan is not None,
            "revised_plan": self.revised_plan,
            "revision_history": self.revision_history,
            "last_updated": self.last_updated
        }

def get_or_create_session(student_usn="1KG21CS045") -> SessionState:
    """Retrieves or instantiates an active session for the candidate."""
    if student_usn not in _ACTIVE_SESSIONS:
        # Check if saved state exists in memory_records DB
        try:
            row = query_one(
                "SELECT content_json FROM memory_records WHERE student_usn = ? AND memory_type = 'SESSION_STATE' ORDER BY updated_at DESC LIMIT 1",
                (student_usn,)
            )
            if row and row.get("content_json"):
                data = json.loads(row["content_json"])
                sess = SessionState(data.get("session_id", f"SESS-{student_usn}"), student_usn)
                sess.clarifications_asked = data.get("clarifications_asked", [])
                sess.student_answers = data.get("student_answers", {})
                sess.active_plan = data.get("active_plan")
                sess.revised_plan = data.get("revised_plan")
                sess.revision_history = data.get("revision_history", [])
                _ACTIVE_SESSIONS[student_usn] = sess
                return sess
        except Exception:
            pass

        session_id = f"SESS-{student_usn}-{uuid.uuid4().hex[:6]}"
        _ACTIVE_SESSIONS[student_usn] = SessionState(session_id, student_usn)
    return _ACTIVE_SESSIONS[student_usn]

def _ensure_student_exists(student_usn: str, name: str = None, branch: str = None, cgpa: float = None):
    """Ensures a record exists in student_profiles so foreign key references in memory_records succeed."""
    try:
        from workflows.students import get_student_profile, upsert_student_profile
        clean_usn = (student_usn or "1KG21CS045").strip().upper()
        if not get_student_profile(clean_usn):
            upsert_student_profile(
                usn=clean_usn,
                name=name or "Student",
                branch=branch or "CSE",
                cgpa=cgpa or 8.0,
                preferred_location="Bengaluru"
            )
    except Exception:
        pass

def persist_session_state(session: SessionState):
    """Saves SessionState to database memory_records for durable recovery."""
    try:
        now = datetime.now().isoformat()
        student_name = session.student_answers.get("name") if session.student_answers else None
        student_branch = session.student_answers.get("branch") if session.student_answers else None
        student_cgpa = session.student_answers.get("cgpa") if session.student_answers else None
        _ensure_student_exists(session.student_usn, name=student_name, branch=student_branch, cgpa=student_cgpa)

        rec_id = f"MEM-SESS-{session.student_usn}"
        payload_str = json.dumps(session.to_dict())
        execute(
            """
            INSERT INTO memory_records (id, student_usn, memory_type, key_name, content_json, created_at, updated_at)
            VALUES (?, ?, 'SESSION_STATE', 'ACTIVE_SESSION', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET content_json = excluded.content_json, updated_at = excluded.updated_at
            """,
            (rec_id, session.student_usn, payload_str, now, now)
        )
    except Exception as e:
        # Fallback to in-memory if DB table not yet migrated
        pass

def append_history_archive(student_usn: str, memory_type: str, key_name: str, data_dict: dict):
    """Appends an immutable historical record to long-term memory archive."""
    try:
        _ensure_student_exists(student_usn)
        now = datetime.now().isoformat()
        rec_id = f"HIST-{uuid.uuid4().hex[:8]}"
        execute(
            """
            INSERT INTO memory_records (id, student_usn, memory_type, key_name, content_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (rec_id, student_usn, memory_type, key_name, json.dumps(data_dict), now, now)
        )
    except Exception:
        pass

class MemoryRetrievalEngine:
    """Long-Term Reference Memory: Indexes and retrieves historical submissions and preferences."""
    
    @staticmethod
    def retrieve_submission_history(student_usn):
        """Fetches all past submission versions for the student."""
        return get_submissions_by_student(student_usn)

    @staticmethod
    def search_similar_opportunities(query_text, limit=3):
        """
        Retrieves opportunities semantically/keyword aligned with student preference query.
        Uses term-frequency cosine vector similarity.
        """
        opps = query_all("SELECT * FROM opportunities WHERE status = 'PUBLISHED'")
        if not opps:
            return []

        def tokenize(text):
            return [w.lower().strip(".,!?:;()") for w in text.split() if len(w) > 2]

        q_tokens = tokenize(query_text)
        q_freq = {}
        for t in q_tokens:
            q_freq[t] = q_freq.get(t, 0) + 1

        scored = []
        for o in opps:
            corpus = f"{o['company']} {o['title']} {o['domain']} {o['description']} {o['required_skills']} {o['location']}"
            c_tokens = tokenize(corpus)
            c_freq = {}
            for t in c_tokens:
                c_freq[t] = c_freq.get(t, 0) + 1

            common = set(q_freq.keys()).intersection(set(c_freq.keys()))
            dot = sum(q_freq[k] * c_freq[k] for k in common)
            mag_q = math.sqrt(sum(v*v for v in q_freq.values()))
            mag_c = math.sqrt(sum(v*v for v in c_freq.values()))

            score = round(dot / (mag_q * mag_c), 3) if (mag_q > 0 and mag_c > 0) else 0.0
            scored.append({
                "opportunity_id": o["id"],
                "company": o["company"],
                "title": o["title"],
                "domain": o["domain"],
                "similarity_score": score,
                "available_vacancies": o["available_vacancies"]
            })

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:limit]

    @staticmethod
    def recall_student_context(student_usn):
        """
        Synthesizes complete memory context for a student across:
        - Working SessionState (Lab 1 answers, current plan, revised plan, Week 8 milestone)
        - Persistent History Archive (Prior submissions, prior rejections)
        """
        session = get_or_create_session(student_usn)
        subs = get_submissions_by_student(student_usn)
        past_companies = set()
        prior_rejections = []

        for s in subs:
            for pref_key in ["pref_1_company", "pref_2_company", "pref_3_company", "pref_4_company"]:
                val = s.get(pref_key)
                if val:
                    past_companies.add(val)
            if s.get("status") == "REJECTED" and s.get("rejection_reason"):
                prior_rejections.append({
                    "version": s["submission_version"],
                    "reason": s["rejection_reason"]
                })

        # Fetch any historical records from DB
        db_history_records = []
        try:
            rows = query_all(
                "SELECT memory_type, key_name, content_json, created_at FROM memory_records WHERE student_usn = ? AND memory_type != 'SESSION_STATE' ORDER BY created_at DESC LIMIT 10",
                (student_usn,)
            )
            for r in rows:
                db_history_records.append({
                    "type": r["memory_type"],
                    "key": r["key_name"],
                    "created_at": r["created_at"],
                    "summary": json.loads(r["content_json"]).get("title") or json.loads(r["content_json"]).get("feedback") or "Memory Record"
                })
        except Exception:
            pass

        return {
            "student_usn": student_usn,
            "session_state": session.to_dict(),
            "has_active_session": bool(session.student_answers or session.active_plan),
            "clarified_answers": session.student_answers,
            "active_plan_title": session.active_plan.get("title") if session.active_plan else None,
            "revised_plan_title": session.revised_plan.get("title") if session.revised_plan else None,
            "total_submissions": len(subs),
            "historical_companies_targeted": list(past_companies),
            "prior_rejection_history": prior_rejections,
            "has_prior_rejections": len(prior_rejections) > 0,
            "history_archive_records": db_history_records
        }
