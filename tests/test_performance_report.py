"""
test_performance_report.py — Unit tests for PerformanceService.generate_multimodal_report.

Verifies:
1. Per-question nlp_score comes from stored nlp_evaluation (combined_nlp_score / overall_nlp_score),
   NOT from the holistic LLM output.
2. Overall NLP score is the mean of stored per-answer scores.
3. No score is inflated to 100 or 50 by the old `<= 10 → * 10` rule.
4. When nlp_evaluation is missing for one answer, its nlp_score is None and the
   overall is the mean of the remaining four.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.interview import AssessmentSession, AnswerSubmission
from backend.app.schemas.question import QuestionItem
from backend.app.services.performance_service import PerformanceService

# Scores that proved the original bug: LLM returned 10/10/5/5/5 (got inflated),
# while stored combined_nlp_score was the truth.
STORED_SCORES = [18, 15, 9, 16, 12]

# Holistic LLM response that used to poison the report
MOCK_NLP_RES = {
    "overall_score": 10,            # would have become 100
    "summary": "mocked summary",
    "strengths": ["s1"],
    "gaps": ["g1"],
    "recommendations": ["r1"],
    "per_question": [
        {"question_id": i, "score": s, "feedback": f"lf{i}"}
        for i, s in zip(range(1, 6), [10, 10, 5, 5, 5])   # would have become 100,100,50,50,50
    ],
}


def _make_session(stored_scores, skip_q_id=None) -> AssessmentSession:
    """Build a minimal text-only session with given per-question stored NLP scores.

    skip_q_id: if set, that question's submission will have nlp_evaluation=None.
    """
    questions = [
        QuestionItem(
            id=i,
            question=f"Question {i}?",
            topic="Python",
            difficulty="MEDIUM",
        )
        for i in range(1, 6)
    ]

    submissions = {}
    for i, score in zip(range(1, 6), stored_scores):
        nlp_eval = None if i == skip_q_id else {
            "combined_nlp_score": score,
            "overall_nlp_score": score,
            "evaluation_method": "combined",
            "feedback": f"stored feedback {i}",
        }
        submissions[i] = AnswerSubmission(
            question_id=i,
            answer_text=f"answer {i}",
            transcript=f"transcript {i}",
            transcription_status="ok" if nlp_eval else "no_recording",
            # text-only: no audio/video paths, so speech/video metrics are skipped
            speech_metrics=None,
            video_metrics=None,
            nlp_evaluation=nlp_eval,
        )

    return AssessmentSession(
        session_id="test-perf-001",
        selected_role="Software Engineer",
        questions=questions,
        submissions=submissions,
        status="active",
    )


class TestPerformanceReport(unittest.TestCase):

    def setUp(self):
        self.svc = PerformanceService()

    def _run_report(self, session):
        """Run generate_multimodal_report with mocked NLP service."""
        with patch(
            "backend.app.services.performance_service.nlp_service.evaluate_interview_transcript",
            return_value=MOCK_NLP_RES,
        ):
            return self.svc.generate_multimodal_report(session)

    # ── Case 1: All 5 submissions have nlp_evaluation ────────────────────────

    def test_per_question_nlp_scores_come_from_stored(self):
        """nlp_score for each question must match stored combined_nlp_score."""
        session = _make_session(STORED_SCORES)
        report = self._run_report(session)

        actual = [pq.nlp_score for pq in report.per_question]
        self.assertEqual(actual, STORED_SCORES,
                         f"Expected {STORED_SCORES}, got {actual}")

    def test_no_score_inflated_to_100_or_50(self):
        """The old <=10 → *10 bug must not exist; no score should be 100 or 50."""
        session = _make_session(STORED_SCORES)
        report = self._run_report(session)

        for pq in report.per_question:
            self.assertNotEqual(pq.nlp_score, 100,
                                f"Q{pq.question_id} nlp_score is 100 (inflation bug)")
            self.assertNotEqual(pq.nlp_score, 50,
                                f"Q{pq.question_id} nlp_score is 50 (inflation bug)")
        self.assertNotEqual(report.nlp_score, 100, "Overall NLP is 100 (inflation bug)")

    def test_overall_nlp_is_mean_of_stored_scores(self):
        """Overall NLP score must be mean(STORED_SCORES) = 14."""
        expected_mean = round(sum(STORED_SCORES) / len(STORED_SCORES))   # 14
        session = _make_session(STORED_SCORES)
        report = self._run_report(session)

        self.assertEqual(report.nlp_score, expected_mean,
                         f"Expected overall NLP={expected_mean}, got {report.nlp_score}")

    def test_feedback_comes_from_stored_nlp_evaluation(self):
        """feedback must prefer stored nlp_evaluation.feedback over LLM fallback."""
        session = _make_session(STORED_SCORES)
        report = self._run_report(session)

        for pq in report.per_question:
            self.assertIn("stored feedback", pq.feedback,
                          f"Q{pq.question_id} feedback came from LLM, expected stored: {pq.feedback!r}")

    # ── Case 2: One submission has nlp_evaluation=None ───────────────────────

    def test_missing_nlp_evaluation_gives_none_score(self):
        """A submission without nlp_evaluation must yield nlp_score=None."""
        SKIP_Q = 3   # Q3 will have nlp_evaluation=None
        session = _make_session(STORED_SCORES, skip_q_id=SKIP_Q)
        report = self._run_report(session)

        q3 = next(pq for pq in report.per_question if pq.question_id == SKIP_Q)
        self.assertIsNone(q3.nlp_score,
                          f"Q{SKIP_Q} should have nlp_score=None, got {q3.nlp_score}")

    def test_overall_nlp_excludes_missing_answer(self):
        """Overall NLP must be mean of the 4 answers that DO have scores."""
        SKIP_Q = 3
        remaining = [s for i, s in zip(range(1, 6), STORED_SCORES) if i != SKIP_Q]
        expected_mean = round(sum(remaining) / len(remaining))  # mean(18,15,16,12) = 15
        session = _make_session(STORED_SCORES, skip_q_id=SKIP_Q)
        report = self._run_report(session)

        self.assertEqual(report.nlp_score, expected_mean,
                         f"Expected overall NLP={expected_mean}, got {report.nlp_score}")


if __name__ == "__main__":
    unittest.main()
