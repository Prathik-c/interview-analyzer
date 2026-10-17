import logging
import numpy as np
from typing import Dict, Any, List, Optional
from backend.app.schemas.interview import AssessmentSession, AnswerSubmission
from backend.app.schemas.evaluation import (
    MultimodalEvaluation, QuestionEvaluation, SpeechMetrics, VideoMetrics
)
from backend.app.services.nlp_service import nlp_service

logger = logging.getLogger("performance_service")


class PerformanceService:

    # ── Text-only detection ─────────────────────────────────────────────────

    @staticmethod
    def _is_text_only(sub: Optional[AnswerSubmission]) -> bool:
        """True when no real audio/video data exists for this submission.

        Decision is based on real evidence (paths + measured metrics), NOT the
        transcription_status string alone (which may be stale from a reload bug).
        """
        if sub is None:
            return True

        # Real evidence checks
        has_audio_file = bool(sub.audio_path)
        has_video_file = bool(sub.video_path)

        if not has_audio_file and not has_video_file:
            return True

        sp = sub.speech_metrics
        vi = sub.video_metrics

        speech_has_data = (sp is not None) and (sp.duration_seconds > 0 or sp.word_count > 0)
        video_has_data = (vi is not None) and (vi.frames_sampled > 0)

        # A file path exists but metrics show zero data: treat as text-only
        if not speech_has_data and not video_has_data:
            return True

        return False

    # ── Scoring ─────────────────────────────────────────────────────────────

    def calculate_per_question_score(
        self,
        nlp_score: Optional[int],
        speech_score: Optional[int] = None,
        video_score: Optional[int] = None,
        text_only: bool = False,
    ) -> Optional[int]:
        """Honest composite scoring formula with dynamic renormalization.

        Rules:
        - If all 3 present: NLP 50%, Speech 25%, Video 25%.
        - If video missing: NLP 67%, Speech 33% (renormalized 50/75, 25/75).
        - If speech missing: NLP 67%, Video 33% (renormalized 50/75, 25/75).
        - If both speech and video missing (or text_only): NLP 100%.
        - If NLP also missing: overall score is None.
        """
        if nlp_score is None:
            return None

        if text_only or (speech_score is None and video_score is None):
            return int(round(float(nlp_score)))

        has_speech = speech_score is not None
        has_video = video_score is not None

        if has_speech and has_video:
            return int(round(nlp_score * 0.50 + speech_score * 0.25 + video_score * 0.25))
        elif has_speech and not has_video:
            return int(round(nlp_score * (50.0 / 75.0) + speech_score * (25.0 / 75.0)))
        elif has_video and not has_speech:
            return int(round(nlp_score * (50.0 / 75.0) + video_score * (25.0 / 75.0)))
        else:
            return int(round(float(nlp_score)))

    def generate_multimodal_report(self, session: AssessmentSession) -> MultimodalEvaluation:
        """Combine NLP, Speech, and Video metrics into a final multimodal evaluation report."""
        # 1. Run Groq NLP evaluation on overall session transcript
        nlp_res = nlp_service.evaluate_interview_transcript(
            job_title=session.selected_role,
            resume_data=session.resume_data or {},
            questions=session.questions,
            submissions=session.submissions
        )

        nlp_scores: List[int] = []   # per-answer NLP scores, filled in the loop below

        speech_scores: List[int] = []
        video_scores: List[int] = []
        per_question_evals: List[QuestionEvaluation] = []

        all_wpm: List[int] = []
        total_fillers = 0
        total_pauses = 0
        total_long_pauses = 0
        longest_pause_overall = 0.0
        combined_filler_breakdown: Dict[str, int] = {}
        all_delivery_notes: List[str] = []

        raw_per_q = {item["question_id"]: item for item in nlp_res.get("per_question", [])}

        for q in session.questions:
            sub = session.submissions.get(q.id)
            sp_metrics = sub.speech_metrics if (sub and sub.speech_metrics) else None
            vi_metrics = sub.video_metrics  if (sub and sub.video_metrics)  else None

            text_only = self._is_text_only(sub)

            sp_score = sp_metrics.speech_score if (sp_metrics and not text_only) else None
            vi_score = vi_metrics.video_score if (vi_metrics and not text_only) else None

            q_modalities = []
            if sp_score is not None:
                speech_scores.append(sp_score)
                q_modalities.append("speech")
            if vi_score is not None:
                video_scores.append(vi_score)
                q_modalities.append("video")

            # Aggregate delivery notes & speech stats from real measurements
            if sp_metrics and not text_only:
                if sp_metrics.words_per_minute > 0:
                    all_wpm.append(sp_metrics.words_per_minute)
                total_fillers += sp_metrics.filler_word_count
                total_pauses  += sp_metrics.pause_count
                total_long_pauses += getattr(sp_metrics, "long_pause_count", 0)
                if (getattr(sp_metrics, "longest_pause_seconds", 0.0) or 0.0) > longest_pause_overall:
                    longest_pause_overall = sp_metrics.longest_pause_seconds or 0.0
                for f_word, count in (sp_metrics.filler_breakdown or {}).items():
                    combined_filler_breakdown[f_word] = combined_filler_breakdown.get(f_word, 0) + count
                all_delivery_notes.extend(sp_metrics.delivery_pattern_notes or [])

            if vi_metrics and not text_only:
                all_delivery_notes.extend(vi_metrics.delivery_pattern_notes or [])

            nlp_q = raw_per_q.get(q.id, {})
            sub_nlp = (sub.nlp_evaluation or {}) if sub else {}
            stored = sub_nlp.get("combined_nlp_score")
            if stored is None:
                stored = sub_nlp.get("overall_nlp_score")
            q_nlp_score = int(round(stored)) if isinstance(stored, (int, float)) else None
            if q_nlp_score is not None:
                nlp_scores.append(q_nlp_score)

            if q_nlp_score is not None:
                q_modalities.insert(0, "nlp")

            combined_q_score = self.calculate_per_question_score(
                q_nlp_score, sp_score, vi_score, text_only=text_only
            )

            # Step G: pull evaluation_method from the persisted nlp_evaluation dict.
            # Do NOT re-run structured_evaluator when nlp_evaluation is missing.
            sub_nlp = (sub.nlp_evaluation or {}) if sub else {}
            if sub_nlp:
                evaluation_method = sub_nlp.get("evaluation_method", "not available")
            else:
                evaluation_method = "not available"

            per_question_evals.append(QuestionEvaluation(
                question_id=q.id,
                question=q.question,
                score=combined_q_score,
                nlp_score=q_nlp_score,
                speech_score=sp_score,
                video_score=vi_score,
                modalities_used=q_modalities,
                feedback=sub_nlp.get("feedback") or nlp_q.get("feedback") or "No feedback available.",
                transcript=sub.transcript if sub else "",
                transcription_status=getattr(sub, "transcription_status", "no_recording") if sub else "no_recording",
                structured_score=sub_nlp.get("structured_score"),
                technical_correctness=sub_nlp.get("technical_correctness") or sub_nlp.get("structured_evaluation", {}).get("technical_correctness") if sub_nlp else None,
                covered_concepts=sub_nlp.get("covered_concepts", []),
                missing_concepts=sub_nlp.get("missing_concepts", []),
                misconceptions=sub_nlp.get("misconceptions", []),
                major_misconception=sub_nlp.get("major_misconception"),
                needs_followup=sub_nlp.get("needs_followup"),
                reasoning_summary=sub_nlp.get("reasoning_summary", ""),
                evaluation_method=evaluation_method,
                duration_seconds=round(sp_metrics.duration_seconds, 1) if (sp_metrics and sp_metrics.duration_seconds) else None,
                pause_count=sp_metrics.pause_count if sp_metrics else None,
                long_pause_count=sp_metrics.long_pause_count if sp_metrics else None,
                longest_pause_seconds=sp_metrics.longest_pause_seconds if sp_metrics else None,
                filler_word_count=sp_metrics.filler_word_count if sp_metrics else None,
                filler_breakdown=sp_metrics.filler_breakdown if sp_metrics else {},
            ))

        # ── Overall NLP: mean of stored per-answer scores (EDIT 3) ──────────
        nlp_overall = int(round(float(np.mean(nlp_scores)))) if nlp_scores else None

        # ── Overall score renormalization ────────────────────────────────────
        avg_speech = int(round(float(np.mean(speech_scores)))) if speech_scores else None
        avg_video  = int(round(float(np.mean(video_scores))))  if video_scores  else None

        modalities_overall = []
        if nlp_overall is not None:
            modalities_overall.append("nlp")
        if avg_speech is not None:
            modalities_overall.append("speech")
        if avg_video is not None:
            modalities_overall.append("video")

        overall_final = self.calculate_per_question_score(
            nlp_score=nlp_overall,
            speech_score=avg_speech,
            video_score=avg_video,
            text_only=(not speech_scores and not video_scores)
        )

        avg_wpm = int(round(float(np.mean(all_wpm)))) if all_wpm else None
        unique_notes = list(dict.fromkeys(all_delivery_notes))

        return MultimodalEvaluation(
            overall_score=overall_final,
            nlp_score=nlp_overall,
            speech_score=avg_speech,
            video_score=avg_video,
            modalities_used=modalities_overall,
            summary=nlp_res.get("summary", "Complete multimodal interview evaluation."),
            strengths=nlp_res.get("strengths", []),
            gaps=nlp_res.get("gaps", []),
            recommendations=nlp_res.get("recommendations", []),
            per_question=per_question_evals,
            avg_wpm=avg_wpm,
            total_filler_count=total_fillers if speech_scores else None,
            total_pause_count=total_pauses if speech_scores else None,
            total_long_pause_count=total_long_pauses if speech_scores else None,
            longest_pause_seconds=round(longest_pause_overall, 2) if speech_scores else None,
            filler_breakdown=combined_filler_breakdown if speech_scores else {},
            delivery_pattern_notes=unique_notes
        )


performance_service = PerformanceService()
