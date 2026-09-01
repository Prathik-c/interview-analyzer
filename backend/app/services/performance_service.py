import numpy as np
from typing import Dict, Any, List
from backend.app.core.config import settings
from backend.app.schemas.interview import AssessmentSession
from backend.app.schemas.evaluation import (
    MultimodalEvaluation, QuestionEvaluation, SpeechMetrics, VideoMetrics
)
from backend.app.services.nlp_service import nlp_service

class PerformanceService:
    def calculate_per_question_score(self, nlp_score: int, speech_score: int, video_score: int) -> int:
        """Centralized per-question scoring formula using configured weights."""
        weighted = (
            (nlp_score * settings.WEIGHT_NLP) +
            (speech_score * settings.WEIGHT_SPEECH) +
            (video_score * settings.WEIGHT_VIDEO)
        )
        return round(weighted)

    def generate_multimodal_report(self, session: AssessmentSession) -> MultimodalEvaluation:
        """Combine NLP, Speech, and Video metrics into a final multimodal evaluation report."""
        # 1. Run Groq NLP evaluation on overall session transcript
        nlp_res = nlp_service.evaluate_interview_transcript(
            job_title=session.selected_role,
            resume_data=session.resume_data or {},
            questions=session.questions,
            submissions=session.submissions
        )

        nlp_overall = int(nlp_res.get("overall_score", 80))
        if nlp_overall <= 10:
            nlp_overall = nlp_overall * 10

        speech_scores = []
        video_scores = []
        per_question_evals: List[QuestionEvaluation] = []

        raw_per_q = {item["question_id"]: item for item in nlp_res.get("per_question", [])}

        for q in session.questions:
            sub = session.submissions.get(q.id)
            sp_metrics = sub.speech_metrics if (sub and sub.speech_metrics) else SpeechMetrics()
            vi_metrics = sub.video_metrics if (sub and sub.video_metrics) else VideoMetrics()

            sp_score = sp_metrics.speech_score
            vi_score = vi_metrics.video_score

            speech_scores.append(sp_score)
            video_scores.append(vi_score)

            nlp_q = raw_per_q.get(q.id, {})
            q_nlp_score = int(nlp_q.get("score", nlp_overall))
            if q_nlp_score <= 10:
                q_nlp_score = q_nlp_score * 10

            combined_q_score = self.calculate_per_question_score(q_nlp_score, sp_score, vi_score)

            per_question_evals.append(QuestionEvaluation(
                question_id=q.id,
                question=q.question,
                score=combined_q_score,
                nlp_score=q_nlp_score,
                speech_score=sp_score,
                video_score=vi_score,
                feedback=nlp_q.get("feedback", "Solid technical answer."),
                transcript=sub.transcript if sub else ""
            ))

        avg_speech = int(np.mean(speech_scores)) if speech_scores else 80
        avg_video = int(np.mean(video_scores)) if video_scores else 82

        # Final Overall Score formula: 50% NLP + 25% Speech + 25% Video
        overall_final = round(
            (nlp_overall * settings.WEIGHT_NLP) +
            (avg_speech * settings.WEIGHT_SPEECH) +
            (avg_video * settings.WEIGHT_VIDEO)
        )

        return MultimodalEvaluation(
            overall_score=overall_final,
            nlp_score=nlp_overall,
            speech_score=avg_speech,
            video_score=avg_video,
            summary=nlp_res.get("summary", "Complete multimodal interview evaluation."),
            strengths=nlp_res.get("strengths", []),
            gaps=nlp_res.get("gaps", []),
            recommendations=nlp_res.get("recommendations", []),
            per_question=per_question_evals
        )

performance_service = PerformanceService()
