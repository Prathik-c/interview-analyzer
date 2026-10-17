"""
test_structured_evaluator.py — Unit tests for LocalStructuredEvaluator.

Verifies:
1. Concept matching and synonym mapping
2. Negation-aware misconception detection
3. Evasion detection
4. Anti-length-bias behavior
5. Required output keys and structure
"""

import unittest
from backend.app.schemas.question import QuestionItem
from backend.app.services.structured_evaluator import structured_evaluator, LocalStructuredEvaluator


class TestStructuredEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = LocalStructuredEvaluator()

    def test_evasion_detection(self):
        """Answers that say 'I don't know' or similar evasion should score very low."""
        q = QuestionItem(
            id=1,
            question="What is the difference between a process and a thread?",
            expected_concepts=["process", "thread", "shared memory", "isolation"]
        )
        res = self.evaluator.evaluate("Software Engineer", q, "I don't know, I have no idea about this.")
        self.assertLessEqual(res["structured_score"], 20)
        self.assertLessEqual(res["relevance_score"], 20)
        self.assertEqual(res["structured_method"], "local_only")
        self.assertEqual(res["evaluation_method"], "local_only")  # backward-compat

    def test_concept_matching_and_synonyms(self):
        """Expected concepts should be recognized through synonyms or exact matches."""
        q = QuestionItem(
            id=2,
            question="Explain database indexing and primary keys.",
            expected_concepts=["primary key", "unique constraint", "b-tree", "fast lookup"]
        )
        answer = "A primary key provides a unique constraint and uses a b-tree for fast lookup and rapid retrieval of rows."
        res = self.evaluator.evaluate("Backend Engineer", q, answer)
        
        self.assertIn("primary key", res["covered_concepts"])
        self.assertIn("b-tree", res["covered_concepts"])
        self.assertGreaterEqual(res["technical_correctness"], 70)
        self.assertGreaterEqual(res["structured_score"], 60)

    def test_negation_aware_misconceptions_not_triggered(self):
        """Asserting 'Primary keys cannot be null' should NOT trigger a primary_key_null misconception."""
        q = QuestionItem(
            id=3,
            question="Can a primary key contain null values?",
            expected_concepts=["primary key", "unique", "not null"]
        )
        # Correct statement with negation:
        correct_answer = "A primary key uniquely identifies rows and cannot be null under relational database constraints."
        res = self.evaluator.evaluate("Backend Engineer", q, correct_answer)
        
        # Check misconceptions does not contain primary key null misconception
        self.assertFalse(res["major_misconception"])
        self.assertNotIn("Claiming primary key can be null", " ".join(res["misconceptions"]))

    def test_misconception_detected_when_asserted(self):
        """Asserting 'A primary key can easily be null' SHOULD trigger a misconception."""
        q = QuestionItem(
            id=4,
            question="Can a primary key have null values?",
            expected_concepts=["primary key", "unique", "null"]
        )
        wrong_answer = "Yes, a primary key can be null in standard SQL databases whenever an ID is missing."
        res = self.evaluator.evaluate("Backend Engineer", q, wrong_answer)
        
        self.assertTrue(res["major_misconception"])
        self.assertLessEqual(res["structured_score"], 50)
        self.assertTrue(len(res["misconceptions"]) > 0)

    def test_anti_length_bias(self):
        """A concise accurate answer should achieve a solid score and not be penalized excessively for brevity."""
        q = QuestionItem(
            id=5,
            question="What is an index in SQL?",
            expected_concepts=["b-tree", "lookup speed", "data structure"]
        )
        concise_good = "An index is a b-tree data structure that speeds up query lookup."
        res = self.evaluator.evaluate("Backend Engineer", q, concise_good)
        
        self.assertGreaterEqual(res["technical_correctness"], 60)
        self.assertGreaterEqual(res["relevance_score"], 65)

    def test_all_expected_fields_present(self):
        """Verify the output format satisfies all multimodal evaluation requirements."""
        q = QuestionItem(
            id=6,
            question="How do REST and GraphQL differ?",
            expected_concepts=["endpoints", "overfetching", "schema"]
        )
        answer = "REST uses fixed endpoints whereas GraphQL avoids overfetching with a strict schema query."
        res = self.evaluator.evaluate("Fullstack Engineer", q, answer)
        
        expected_keys = [
            "technical_correctness",
            "relevance_score",
            "completeness_score",
            "structured_score",
            "covered_concepts",
            "partial_concepts",
            "missing_concepts",
            "misconceptions",
            "major_misconception",
            "needs_followup",
            "reasoning_summary",
            "evidence",
            "evaluation_method",
        ]
        for key in expected_keys:
            self.assertIn(key, res, f"Expected key '{key}' not found in structured evaluator result.")
        # Step G: structured_method is the canonical key; evaluation_method kept for back-compat
        self.assertEqual(res["structured_method"], "local_only")
        self.assertEqual(res["evaluation_method"], "local_only")


if __name__ == "__main__":
    unittest.main()
