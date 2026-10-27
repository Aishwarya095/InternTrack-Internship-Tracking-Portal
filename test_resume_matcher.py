"""
INTERNTRACK — Unit Tests for Resume & CV Skills Auto-Matcher
Tests skill extraction, taxonomy normalization, catalog matching, and score ranking.
"""

import unittest
from workflows.resume_matcher import (
    extract_skills_from_text,
    extract_metadata_from_resume,
    match_resume_to_opportunities,
    SKILL_TAXONOMY
)

class TestResumeMatcher(unittest.TestCase):

    def test_extract_skills_from_text(self):
        sample_text = """
        Experienced in Python, PyTorch, and TensorFlow for Deep Learning.
        Built web apps with React.js, Node.js, and PostgreSQL.
        Knowledge of Docker, Kubernetes, and AWS cloud deployment.
        """
        skills = extract_skills_from_text(sample_text)
        expected_subset = ["Python", "PyTorch", "TensorFlow", "Deep Learning", "React", "Node.js", "PostgreSQL", "Docker", "Kubernetes", "AWS"]
        for expected in expected_subset:
            self.assertIn(expected, skills)

    def test_extract_cgpa_and_metadata(self):
        sample = "Student at KLE Tech. CGPA: 8.75 / 10. Major in Computer Science & Engineering."
        meta = extract_metadata_from_resume(sample)
        self.assertEqual(meta["detected_cgpa"], 8.75)
        self.assertIn("Computer Science", meta["detected_branch"])

    def test_match_resume_to_opportunities_ranking(self):
        sample_resume = """
        ANANYA S.
        B.E. Computer Science, CGPA: 8.8
        Skills: Python, PyTorch, Scikit-learn, SQL, Docker, Machine Learning.
        Projects: Built an end-to-end ML model using PyTorch and Docker.
        """
        res = match_resume_to_opportunities(sample_resume, student_usn="1KG21CS045")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(len(res["matches"]), 0)
        
        # Verify descending order of match_percentage
        scores = [m["match_percentage"] for m in res["matches"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Check top match details
        top = res["matches"][0]
        self.assertIn("company_name", top)
        self.assertIn("match_percentage", top)
        self.assertIn("fit_level", top)
        self.assertIn("matched_skills", top)
        self.assertIn("missing_skills", top)
        self.assertGreater(top["match_percentage"], 60.0)

    def test_short_resume_raises_value_error(self):
        with self.assertRaises(ValueError):
            match_resume_to_opportunities("Too short")

if __name__ == "__main__":
    unittest.main()
