import json
from pathlib import Path
from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal, init_db
from backend.app.db.models import (
    AssessmentSessionDB, QuestionDB, SubmissionDB, RecordingDB,
    SpeechAnalysisDB, VideoAnalysisDB, NLPEvaluationDB, FinalEvaluationDB
)
from backend.app.schemas.interview import AssessmentSession, AnswerSubmission
from backend.app.schemas.question import QuestionItem
from backend.app.schemas.evaluation import SpeechMetrics, VideoMetrics, MultimodalEvaluation, QuestionEvaluation
from backend.app.core.constants import AssessmentType

class SessionStorage:
    """Repository handling assessment session persistence via SQLAlchemy ORM (PostgreSQL/SQLite)."""
    
    def __init__(self, storage_dir: Path = settings.DATA_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            init_db()
        except Exception as e:
            print(f"Warning: Database initialization error: {e}")

    def get_session(self, session_id: str) -> Optional[AssessmentSession]:
        """Fetch session from DB via session_id."""
        db: Session = SessionLocal()
        try:
            db_session = db.query(AssessmentSessionDB).filter(
                AssessmentSessionDB.session_id == session_id
            ).first()
            if db_session:
                return self._orm_to_domain(db_session)
        finally:
            db.close()

        # Fallback load from legacy JSON audit file if DB record missing
        json_file = self.storage_dir / f"{session_id}.json"
        if json_file.exists():
            try:
                raw_data = json.loads(json_file.read_text(encoding="utf-8"))
                return AssessmentSession(**raw_data)
            except Exception as e:
                print(f"JSON legacy load error for {session_id}: {e}")
        return None

    def save_session(self, session: AssessmentSession) -> bool:
        """Persist assessment session to Database & write JSON backup."""
        # 1. Write JSON file audit backup
        try:
            json_file = self.storage_dir / f"{session.session_id}.json"
            json_file.write_text(json.dumps(session.model_dump(mode="json"), indent=2), encoding="utf-8")
        except Exception as e:
            print(f"JSON backup save warning: {e}")

        # 2. Persist to Database (PostgreSQL / SQLite ORM)
        db: Session = SessionLocal()
        try:
            db_session = db.query(AssessmentSessionDB).filter(AssessmentSessionDB.session_id == session.session_id).first()
            if not db_session:
                db_session = AssessmentSessionDB(
                    session_id=session.session_id,
                    user_id=session.user_id,
                    assessment_type=session.assessment_type,
                    selected_role=session.selected_role,
                    filename=session.filename,
                    resume_data=session.resume_data,
                    status=session.status,
                    current_question_number=session.current_question_number,
                    state_data=session.state_data
                )
                db.add(db_session)
                db.flush()

            if session.user_id:
                db_session.user_id = session.user_id
            db_session.selected_role = session.selected_role
            db_session.filename = session.filename
            db_session.resume_data = session.resume_data
            db_session.status = session.status
            db_session.current_question_number = session.current_question_number
            db_session.state_data = session.state_data

            # Sync Questions
            db.query(QuestionDB).filter(QuestionDB.session_id == db_session.id).delete()
            for q in session.questions:
                db_q = QuestionDB(
                    session_id=db_session.id,
                    question_id=q.id,
                    question_text=q.question,
                    topic=q.topic,
                    difficulty=q.difficulty or "MEDIUM",
                    source=q.source or "role",
                    strategy=q.strategy or "NEW_TOPIC",
                    reason=q.reason
                )
                db.add(db_q)

            # Sync Submissions
            db.query(SubmissionDB).filter(SubmissionDB.session_id == db_session.id).delete()
            for q_id, sub in session.submissions.items():
                db_sub = SubmissionDB(
                    session_id=db_session.id,
                    question_id=q_id,
                    answer_text=sub.answer_text,
                    transcript=sub.transcript,
                    audio_path=sub.audio_path,
                    video_path=sub.video_path,
                    speech_metrics=sub.speech_metrics.model_dump() if sub.speech_metrics else None,
                    video_metrics=sub.video_metrics.model_dump() if sub.video_metrics else None
                )
                db.add(db_sub)

                # Sync granular recordings metadata if path present
                if sub.video_path:
                    db_rec = db.query(RecordingDB).filter(
                        RecordingDB.session_id == db_session.id,
                        RecordingDB.question_id == q_id
                    ).first()
                    if not db_rec:
                        db_rec = RecordingDB(
                            session_id=db_session.id,
                            question_id=q_id,
                            file_path=sub.video_path,
                            file_type="webm",
                            duration=sub.speech_metrics.duration_seconds if sub.speech_metrics else 0.0
                        )
                        db.add(db_rec)

                # Sync granular Speech Analysis
                if sub.speech_metrics:
                    db_sp = db.query(SpeechAnalysisDB).filter(
                        SpeechAnalysisDB.session_id == db_session.id,
                        SpeechAnalysisDB.question_id == q_id
                    ).first()
                    if not db_sp:
                        db_sp = SpeechAnalysisDB(
                            session_id=db_session.id,
                            question_id=q_id,
                            wpm=sub.speech_metrics.words_per_minute,
                            filler_count=sub.speech_metrics.filler_word_count,
                            filler_frequency=sub.speech_metrics.filler_frequency,
                            speech_score=sub.speech_metrics.speech_score,
                            metrics_json=sub.speech_metrics.model_dump()
                        )
                        db.add(db_sp)

                # Sync granular Video Analysis
                if sub.video_metrics:
                    db_vi = db.query(VideoAnalysisDB).filter(
                        VideoAnalysisDB.session_id == db_session.id,
                        VideoAnalysisDB.question_id == q_id
                    ).first()
                    if not db_vi:
                        db_vi = VideoAnalysisDB(
                            session_id=db_session.id,
                            question_id=q_id,
                            face_visibility_score=sub.video_metrics.face_visibility_score,
                            attention_score=sub.video_metrics.attention_score,
                            posture_score=sub.video_metrics.posture_score,
                            stability_score=sub.video_metrics.stability_score,
                            video_score=sub.video_metrics.video_score,
                            metrics_json=sub.video_metrics.model_dump()
                        )
                        db.add(db_vi)

            # Sync Evaluation
            if session.evaluation:
                db.query(FinalEvaluationDB).filter(FinalEvaluationDB.session_id == db_session.id).delete()
                eval_obj = session.evaluation
                db_eval = FinalEvaluationDB(
                    session_id=db_session.id,
                    overall_score=eval_obj.overall_score,
                    nlp_score=eval_obj.nlp_score,
                    speech_score=eval_obj.speech_score,
                    video_score=eval_obj.video_score,
                    summary=eval_obj.summary,
                    strengths=eval_obj.strengths,
                    gaps=eval_obj.gaps,
                    recommendations=eval_obj.recommendations,
                    per_question=[pq.model_dump() for pq in eval_obj.per_question]
                )
                db.add(db_eval)

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"DB session save error: {e}")
            return False
        finally:
            db.close()

    def _orm_to_domain(self, db_session: AssessmentSessionDB) -> AssessmentSession:
        """Convert SQLAlchemy ORM DB object into domain AssessmentSession."""
        questions = [
            QuestionItem(
                id=q.question_id,
                question=q.question_text,
                topic=q.topic,
                difficulty=q.difficulty or "MEDIUM",
                source=q.source or "role",
                strategy=q.strategy or "NEW_TOPIC",
                reason=q.reason
            )
            for q in sorted(db_session.questions, key=lambda x: x.question_id)
        ]

        submissions = {}
        for sub in db_session.submissions:
            sp_metrics = SpeechMetrics(**sub.speech_metrics) if sub.speech_metrics else SpeechMetrics()
            vi_metrics = VideoMetrics(**sub.video_metrics) if sub.video_metrics else VideoMetrics()

            submissions[sub.question_id] = AnswerSubmission(
                question_id=sub.question_id,
                answer_text=sub.answer_text,
                transcript=sub.transcript,
                audio_path=sub.audio_path,
                video_path=sub.video_path,
                speech_metrics=sp_metrics,
                video_metrics=vi_metrics
            )

        evaluation = None
        if db_session.evaluation:
            e = db_session.evaluation
            pq_list = [QuestionEvaluation(**item) for item in (e.per_question or [])]
            evaluation = MultimodalEvaluation(
                overall_score=e.overall_score,
                nlp_score=e.nlp_score,
                speech_score=e.speech_score,
                video_score=e.video_score,
                summary=e.summary or "",
                strengths=e.strengths or [],
                gaps=e.gaps or [],
                recommendations=e.recommendations or [],
                per_question=pq_list
            )

        return AssessmentSession(
            session_id=db_session.session_id,
            user_id=db_session.user_id,
            assessment_type=AssessmentType(db_session.assessment_type) if db_session.assessment_type in AssessmentType.__members__ else AssessmentType.INTERVIEW,
            selected_role=db_session.selected_role,
            filename=db_session.filename,
            resume_data=db_session.resume_data,
            questions=questions,
            submissions=submissions,
            evaluation=evaluation,
            status=db_session.status,
            current_question_number=db_session.current_question_number or 1,
            state_data=db_session.state_data or {},
            created_at=db_session.created_at.isoformat() if db_session.created_at else None
        )

session_storage = SessionStorage()
