from uuid import uuid4
from pathlib import Path
from typing import Optional, Dict, Any
from backend.app.schemas.interview import AssessmentSession, AnswerSubmission
from backend.app.schemas.question import QuestionItem
from backend.app.core.constants import AssessmentType
from backend.app.storage.session_storage import session_storage
from backend.app.storage.file_storage import file_storage
from backend.app.services.resume_service import resume_service
from backend.app.services.question_service import question_service
from backend.app.services.audio_service import audio_service
from backend.app.services.speech_service import speech_service
from backend.app.services.video_service import video_service
from backend.app.services.nlp_service import nlp_service
from backend.app.services.adaptive_engine import adaptive_engine
from backend.app.services.performance_service import performance_service
from fastapi import HTTPException, status

class InterviewService:
    def create_interview_session(
        self,
        selected_role: str,
        filename: str,
        pdf_content: bytes,
        user_id: Optional[str] = None
    ) -> AssessmentSession:
        """Process resume PDF, generate Question 1, and initialize isolated session with user ownership."""
        session_id = str(uuid4())
        
        # 1. Save uploaded resume file to disk
        file_path = file_storage.save_resume(session_id, filename, pdf_content)
        
        # 2. Extract structured resume JSON
        extracted_resume = resume_service.process_resume(file_path)
        
        # 3. Generate initial Question 1
        q1 = question_service.generate_initial_question(selected_role, extracted_resume)
        
        # 4. Create and persist session object
        session = AssessmentSession(
            session_id=session_id,
            user_id=user_id,
            assessment_type=AssessmentType.INTERVIEW,
            selected_role=selected_role.strip(),
            filename=filename,
            resume_data=extracted_resume,
            questions=[q1],
            submissions={},
            status="active",
            current_question_number=1,
            state_data={
                "candidate_skill_map": {
                    skill: {"estimated_level": "INTERMEDIATE", "confidence": 0.50}
                    for skill in extracted_resume.get("skills", [])[:5]
                },
                "topics_tested": [q1.topic],
                "strengths": [],
                "knowledge_gaps": [],
                "difficulty_progression": [q1.difficulty or "EASY"]
            }
        )
        session_storage.save_session(session)
        return session

    def process_answer_submission(
        self,
        session_id: str,
        question_id: int,
        user_id: Optional[str] = None,
        answer_text: Optional[str] = "",
        recording_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Full Adaptive Multimodal Answer Pipeline:
        WebM -> Storage -> Whisper STT -> Speech Metrics -> Video Posture -> Groq NLP -> Score -> Adaptive Engine -> Next Question
        """
        session = session_storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Interview session {session_id} not found.")

        # Validate User Ownership
        if user_id and session.user_id and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied: You do not own this interview session.")

        current_q = next((q for q in session.questions if q.id == question_id), None)
        if not current_q:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found in session.")

        submission = session.submissions.get(question_id) or AnswerSubmission(question_id=question_id)
        
        if answer_text:
            submission.answer_text = answer_text
            submission.transcript = answer_text

        if recording_bytes:
            # 1. Save WebM recording
            rec_path = file_storage.save_recording(session_id, question_id, recording_bytes, file_extension="webm")
            submission.video_path = str(rec_path)
            
            # 2. Extract audio & run Speech-to-Text via Groq Whisper
            audio_path = audio_service.extract_audio_from_webm(rec_path)
            submission.audio_path = str(audio_path)
            
            stt_transcript, duration = speech_service.transcribe_audio(audio_path)
            if stt_transcript:
                submission.transcript = stt_transcript
            elif not submission.transcript:
                submission.transcript = submission.answer_text or ""

            # 3. Speech Delivery Metrics (WPM, filler word count)
            submission.speech_metrics = speech_service.analyze_speech_delivery(
                submission.transcript or "", duration_seconds=duration
            )

            # 4. OpenCV / MediaPipe Video Posture & Attention Analysis
            submission.video_metrics = video_service.analyze_video_recording(rec_path)

        # 5. Single-Question NLP Technical Evaluation
        nlp_eval = nlp_service.evaluate_single_answer(
            job_title=session.selected_role,
            question=current_q,
            transcript=submission.transcript or "",
            resume_context=session.resume_data or {}
        )

        sp_score = submission.speech_metrics.speech_score if submission.speech_metrics else 80
        vi_score = submission.video_metrics.video_score if submission.video_metrics else 82
        nlp_score = nlp_eval.get("combined_nlp_score", nlp_eval.get("overall_nlp_score", 80))

        # Calculate Per-Question Score (50% NLP, 25% Speech, 25% Video)
        per_q_score = performance_service.calculate_per_question_score(nlp_score, sp_score, vi_score)

        session.submissions[question_id] = submission

        # Update candidate state tracking
        state_data = session.state_data or {}
        strengths = state_data.get("strengths", [])
        strengths.extend(nlp_eval.get("strengths", []))
        gaps = state_data.get("knowledge_gaps", [])
        gaps.extend(nlp_eval.get("knowledge_gaps", []))
        topics = state_data.get("topics_tested", [])
        if current_q.topic and current_q.topic not in topics:
            topics.append(current_q.topic)
        diff_prog = state_data.get("difficulty_progression", [])
        diff_prog.append(current_q.difficulty or "MEDIUM")

        if nlp_eval.get("major_misconception"):
            misconceptions = state_data.get("misconceptions_detected", [])
            misconceptions.append({
                "question_id": question_id,
                "question": current_q.question,
                "needs_followup": nlp_eval.get("needs_followup", True)
            })
            state_data["misconceptions_detected"] = misconceptions

        state_data["strengths"] = list(set(strengths))
        state_data["knowledge_gaps"] = list(set(gaps))
        state_data["topics_tested"] = topics
        state_data["difficulty_progression"] = diff_prog
        session.state_data = state_data

        # 6. Adaptive Engine Decision for Next Question
        next_question_item = None
        max_questions = 5  # 5 questions total adaptively generated

        if question_id < max_questions:
            decision = adaptive_engine.decide_next_question(
                session_id=session_id,
                role=session.selected_role,
                resume_context=session.resume_data or {},
                current_question={"id": current_q.id, "text": current_q.question, "topic": current_q.topic},
                transcript=submission.transcript or "",
                nlp_score=nlp_score,
                speech_score=sp_score,
                video_score=vi_score,
                technical_strengths=nlp_eval.get("strengths", []),
                knowledge_gaps=nlp_eval.get("knowledge_gaps", []),
                mentioned_topics=nlp_eval.get("topics_detected", []),
                difficulty_level=current_q.difficulty or "MEDIUM",
                question_number=question_id
            )

            next_q_id = question_id + 1
            next_question_item = QuestionItem(
                id=next_q_id,
                question=decision.next_question,
                topic=decision.target_topic,
                difficulty=decision.next_difficulty,
                source=decision.question_strategy.lower(),
                strategy=decision.question_strategy,
                reason=decision.reason
            )

            # Check if next question already added
            existing_next = next((q for q in session.questions if q.id == next_q_id), None)
            if existing_next:
                session.questions[next_q_id - 1] = next_question_item
            else:
                session.questions.append(next_question_item)

            session.current_question_number = next_q_id

        session_storage.save_session(session)

        return {
            "accepted": True,
            "session_id": session_id,
            "question_id": question_id,
            "transcript": submission.transcript,
            "per_question_score": per_q_score,
            "nlp_score": nlp_score,
            "speech_metrics": submission.speech_metrics.model_dump() if submission.speech_metrics else None,
            "video_metrics": submission.video_metrics.model_dump() if submission.video_metrics else None,
            "nlp_evaluation": nlp_eval,
            "is_last_question": (question_id >= max_questions),
            "next_question": next_question_item.model_dump() if next_question_item else None
        }

    def evaluate_session(self, session_id: str, user_id: Optional[str] = None) -> AssessmentSession:
        """Generate final multimodal performance report and complete session."""
        session = session_storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Interview session {session_id} not found.")

        if user_id and session.user_id and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied: You do not own this interview session.")

        evaluation = performance_service.generate_multimodal_report(session)
        session.evaluation = evaluation
        session.status = "completed"
        session_storage.save_session(session)
        return session

interview_service = InterviewService()
