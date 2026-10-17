"""
tests/test_answer_quality.py — Unit tests for answer quality classification and zero-score handling.
"""

import unittest
from unittest.mock import MagicMock

from backend.app.services.answer_quality import (
    classify_answer,
    WHISPER_DISFLUENCY_PROMPT,
)
from backend.app.services.nlp_service import NLPService
from backend.app.schemas.question import QuestionItem


class TestAnswerQuality(unittest.TestCase):
    """Test classification of answer transcripts into no_speech, non_answer, or answered."""

    def test_classify_answer_exact_transcripts(self):
        cases = [
            ("...", "no_speech"),
            ("Mm, um, um,", "no_speech"),
            ("", "no_speech"),
            (WHISPER_DISFLUENCY_PROMPT, "no_speech"),
            ("Yes.", "non_answer"),
            ("No.", "non_answer"),
            ("Sorry, I don't know the answer.", "non_answer"),
            ("Can you give me any questions related to OS or CN?", "non_answer"),
            (
                "So the thing is I am a bit new to rag. Could you ask me anything simpler question than this?",
                "non_answer",
            ),
            ("TCP is connection oriented", "answered"),
            ("O(n log n)", "answered"),
            ("Normalization scales pixel values to 0 to 1", "answered"),
            ("Yes, because a process has its own address space", "answered"),
            ("No, I cannot explain the code.", "non_answer"),
            (
                "I cannot say that TCP is connectionless, it is connection oriented",
                "answered",
            ),
        ]

        for transcript, expected in cases:
            with self.subTest(transcript=transcript):
                actual = classify_answer(transcript)
                self.assertEqual(
                    actual,
                    expected,
                    f"classify_answer({transcript!r}) returned {actual!r}, expected {expected!r}",
                )

    def test_evaluate_single_answer_non_answer_mocked_groq(self):
        """Mocked test that evaluate_single_answer returns combined_nlp_score 0 for 'No.' without calling Groq."""
        nlp_svc = NLPService()
        mock_client = MagicMock()
        nlp_svc.client = mock_client

        question = QuestionItem(
            id=1,
            question="Can you explain how indexing works in PostgreSQL?",
            topic="Databases",
        )

        res = nlp_svc.evaluate_single_answer(
            job_title="Backend Developer",
            question=question,
            transcript="No.",
            resume_context={},
        )

        self.assertEqual(res["combined_nlp_score"], 0)
        self.assertEqual(res["overall_nlp_score"], 0)
        self.assertEqual(res["technical_score"], 0)
        self.assertEqual(res["relevance_score"], 0)
        self.assertEqual(res["depth_score"], 0)
        self.assertEqual(res["clarity_score"], 0)
        self.assertEqual(res["evaluation_method"], "rule_based")
        self.assertEqual(res["feedback"], "The question was not answered.")

        # Ensure Groq client was never invoked
        mock_client.chat.completions.create.assert_not_called()

    def test_evaluate_single_answer_no_speech_mocked_groq(self):
        """Mocked test that evaluate_single_answer returns combined_nlp_score 0 for '...' without calling Groq."""
        nlp_svc = NLPService()
        mock_client = MagicMock()
        nlp_svc.client = mock_client

        question = QuestionItem(
            id=1,
            question="What is dependency injection?",
            topic="Software Design",
        )

        res = nlp_svc.evaluate_single_answer(
            job_title="Software Engineer",
            question=question,
            transcript="...",
            resume_context={},
        )

        self.assertEqual(res["combined_nlp_score"], 0)
        self.assertEqual(res["evaluation_method"], "rule_based")
        self.assertEqual(res["feedback"], "No speech was detected for this answer.")

        # Ensure Groq client was never invoked
        mock_client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
