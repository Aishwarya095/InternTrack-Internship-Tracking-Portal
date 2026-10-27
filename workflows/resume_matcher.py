"""
INTERNTRACK — Resume & CV Skills Auto-Matcher
Analyzes student resumes (text or extracted documents), identifies candidate skills,
and computes real-time skill-match percentages across all active catalog opportunities.
"""

import re
import json
from datetime import datetime
from database.db import query_all, query_one
from core.audit import log_event

# ---------------------------------------------------------------------------
# Comprehensive Taxonomy of Recognized Tech Skills
# ---------------------------------------------------------------------------
SKILL_TAXONOMY = {
    # Programming Languages
    "python": "Python",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "c": "C",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "php": "PHP",
    "ruby": "Ruby",
    "r": "R",
    "sql": "SQL",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",

    # AI, ML & Data Science
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "nlp": "Natural Language Processing (NLP)",
    "natural language processing": "Natural Language Processing (NLP)",
    "computer vision": "Computer Vision",
    "cv": "Computer Vision",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "data analysis": "Data Analysis",
    "data science": "Data Science",
    "generative ai": "Generative AI",
    "genai": "Generative AI",
    "llm": "LLMs",
    "llms": "LLMs",
    "langchain": "LangChain",
    "langgraph": "LangGraph",

    # Web & Frameworks
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "angular": "Angular",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "express": "Express",
    "express.js": "Express",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "spring": "Spring Boot",
    ".net": ".NET",
    "asp.net": "ASP.NET",
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "graphql": "GraphQL",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "cloud": "Cloud",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "git": "Git",
    "github": "Git",
    "gitlab": "Git",
    "linux": "Linux",
    "bash": "Bash",
    "shell": "Shell Scripting",

    # Databases
    "mongodb": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "redis": "Redis",
    "sqlite": "SQLite",
    "oracle": "Oracle",

    # Core Computer Science & Soft Skills
    "algorithms": "Algorithms",
    "data structures": "Data Structures",
    "dsa": "Data Structures & Algorithms",
    "oop": "OOP",
    "object-oriented": "OOP",
    "system design": "System Design",
    "problem solving": "Problem Solving",
    "software engineering": "Software Engineering",
    "agile": "Agile",
    "scrum": "Scrum"
}


def extract_skills_from_text(text: str) -> list:
    """
    Scans freeform resume text and extracts unique canonical skill names.
    Handles exact word boundaries, case insensitivity, and multi-word terms.
    """
    if not text:
        return []

    cleaned_text = text.lower()
    # Normalize punctuation for token separation while preserving dots in tech terms
    normalized_text = re.sub(r'[,;/|\(\)\[\]\{\}:!?"\']', ' ', cleaned_text)
    raw_tokens = normalized_text.split()
    words_set = set(raw_tokens)
    # Also add tokens stripped of terminal periods (e.g. "postgresql." -> "postgresql")
    for t in raw_tokens:
        words_set.add(t.rstrip('.'))

    detected_canonical = {}

    for term, canonical in SKILL_TAXONOMY.items():
        # Check multi-word phrase or single word with regex boundary
        if " " in term or "." in term or "+" in term or "#" in term or "/" in term:
            pattern = r'(?<![a-zA-Z0-9])' + re.escape(term) + r'(?![a-zA-Z0-9])'
            if re.search(pattern, cleaned_text):
                detected_canonical[canonical] = True
        else:
            if term in words_set:
                detected_canonical[canonical] = True

    return sorted(list(detected_canonical.keys()))


def extract_metadata_from_resume(text: str) -> dict:
    """Extracts summary metrics such as CGPA, education, and word counts."""
    if not text:
        return {"word_count": 0, "detected_cgpa": None, "skills_count": 0}

    word_count = len(text.split())

    # Regex for CGPA e.g. "CGPA: 8.4" or "8.4 / 10" or "CGPA 8.75"
    cgpa_match = re.search(r'(?:cgpa|gpa|pointer)\s*(?:is|:|=)?\s*([0-9]\.[0-9]{1,2})', text, re.IGNORECASE)
    detected_cgpa = float(cgpa_match.group(1)) if cgpa_match else None

    # Education / Branch detection
    branch_match = None
    if re.search(r'\b(computer\s+science|cse|information\s+science|ise|ai\s*(&|and)?\s*ml|artificial\s+intelligence)\b', text, re.IGNORECASE):
        branch_match = "Computer Science & Engineering"
    elif re.search(r'\b(electronics|ece|electrical|eee)\b', text, re.IGNORECASE):
        branch_match = "Electronics & Communication"

    return {
        "word_count": word_count,
        "detected_cgpa": detected_cgpa,
        "detected_branch": branch_match
    }


def match_resume_to_opportunities(resume_text: str, student_usn: str = None) -> dict:
    """
    Core Engine:
    1. Extracts technical skills from resume text.
    2. Retrieves all PUBLISHED opportunities from SQLite.
    3. Calculates skill-match percentage, identifies matched & missing skills, and ranks results.
    """
    if not resume_text or len(resume_text.strip()) < 15:
        raise ValueError("Resume text is too short. Please paste or upload a meaningful resume.")

    detected_skills = extract_skills_from_text(resume_text)
    metadata = extract_metadata_from_resume(resume_text)

    # If student_usn provided, supplement CGPA and profile from database
    if student_usn:
        profile = query_one("SELECT * FROM student_profiles WHERE usn = ?", (student_usn,))
        if profile:
            if not metadata["detected_cgpa"] and profile.get("cgpa"):
                metadata["detected_cgpa"] = profile["cgpa"]
            if not metadata["detected_branch"] and profile.get("branch"):
                metadata["detected_branch"] = profile["branch"]

    # Fetch active opportunities from database
    opps = query_all("""
        SELECT id, company, title, domain, location, mode, min_cgpa, required_skills,
               duration, stipend_monthly, available_vacancies, status
        FROM opportunities
        WHERE status = 'PUBLISHED'
        ORDER BY available_vacancies DESC
    """)

    results = []
    normalized_candidate_skills = {s.lower(): s for s in detected_skills}

    for opp in opps:
        raw_req_skills = opp.get("required_skills") or ""
        # Parse required skills from comma-separated string or tokens
        req_skills_list = [s.strip() for s in raw_req_skills.split(",") if s.strip()]
        if not req_skills_list:
            req_skills_list = ["Python", "Problem Solving", "Software Engineering"]

        matched_skills = []
        missing_skills = []

        for req in req_skills_list:
            req_clean = req.lower()
            # Direct or taxonomy match
            matched = False
            for cand_lower, cand_canon in normalized_candidate_skills.items():
                if cand_lower == req_clean or req_clean in cand_lower or cand_lower in req_clean:
                    matched_skills.append(cand_canon)
                    matched = True
                    break
            if not matched:
                missing_skills.append(req)

        # Remove duplicates
        matched_skills = sorted(list(set(matched_skills)))
        missing_skills = sorted(list(set(missing_skills)))

        total_req = len(req_skills_list)
        match_count = len(matched_skills)

        # Baseline percentage
        if total_req > 0:
            base_score = (match_count / total_req) * 100.0
        else:
            base_score = 70.0

        # Quality bonus: if candidate has extra tech skills
        bonus = min(10.0, max(0.0, (len(detected_skills) - match_count) * 1.5))
        final_score = round(min(98.0, base_score + bonus), 1)

        # If all required matched, allow up to 99-100%
        if match_count >= total_req and total_req > 0:
            final_score = 99.0

        # Eligibility check
        is_cgpa_eligible = True
        cgpa_gap = 0.0
        if metadata.get("detected_cgpa") is not None and opp.get("min_cgpa"):
            if metadata["detected_cgpa"] < opp["min_cgpa"]:
                is_cgpa_eligible = False
                cgpa_gap = round(opp["min_cgpa"] - metadata["detected_cgpa"], 2)
                final_score = max(20.0, final_score - 15.0)

        # Fit categorization
        if final_score >= 80.0:
            fit_level = "EXCELLENT MATCH"
            fit_color = "#10b981" # emerald
        elif final_score >= 60.0:
            fit_level = "STRONG MATCH"
            fit_color = "#3b82f6" # blue
        elif final_score >= 40.0:
            fit_level = "MODERATE MATCH"
            fit_color = "#f59e0b" # amber
        else:
            fit_level = "UPSKILLING NEEDED"
            fit_color = "#ef4444" # red

        # Recommendation reasoning
        if match_count == total_req:
            reason = f"Complete alignment! Candidate possesses all {total_req} core technical skills required by {opp['company']}."
        elif match_count > 0:
            reason = f"Matches {match_count} of {total_req} core requirements ({', '.join(matched_skills[:3])}). Upskilling in {missing_skills[0] if missing_skills else 'advanced tooling'} recommended."
        else:
            reason = f"Foundational alignment. Requires skills acquisition in {', '.join(missing_skills[:2])} for full readiness."

        results.append({
            "opportunity_id": opp["id"],
            "company_name": opp["company"],
            "title": opp["title"],
            "domain": opp["domain"],
            "location": opp["location"],
            "mode": opp["mode"],
            "stipend_monthly": opp.get("stipend_monthly") or 0.0,
            "available_vacancies": opp.get("available_vacancies") or 0,
            "min_cgpa": opp.get("min_cgpa") or 6.0,
            "match_percentage": final_score,
            "fit_level": fit_level,
            "fit_color": fit_color,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "is_cgpa_eligible": is_cgpa_eligible,
            "cgpa_gap": cgpa_gap,
            "recommendation_reason": reason
        })

    # Sort opportunities by match percentage descending, then available vacancies
    results.sort(key=lambda x: (x["match_percentage"], x["available_vacancies"]), reverse=True)

    # Audit logging
    try:
        log_event(
            actor=student_usn or "STUDENT_ANONYMOUS",
            action="RESUME_SKILL_AUTO_MATCH",
            details={
                "skills_extracted_count": len(detected_skills),
                "top_company": results[0]["company_name"] if results else None,
                "top_score": results[0]["match_percentage"] if results else 0,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "extracted_profile": {
            "detected_skills": detected_skills,
            "skills_count": len(detected_skills),
            "word_count": metadata["word_count"],
            "detected_cgpa": metadata["detected_cgpa"],
            "detected_branch": metadata["detected_branch"]
        },
        "total_catalog_opportunities": len(opps),
        "matches_count": len(results),
        "matches": results
    }
