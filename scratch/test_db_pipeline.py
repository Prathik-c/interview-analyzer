import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app.core.config import settings
from app.db.session import init_db, SessionLocal
from app.db.models import AssessmentSessionDB, QuestionDB, SubmissionDB, EvaluationDB
from app.storage.session_storage import session_storage
from app.models.session_models import (
    AssessmentSession, QuestionItem, AnswerSubmission,
    SpeechMetrics, VideoMetrics, MultimodalEvaluation, QuestionEvaluation, AssessmentType
)
from app.db.migrate_json import migrate_json_sessions_to_db

def run_db_pipeline_tests():
    print("--- 1. Testing Database Initialization & Connection ---")
    print(f"Target Database URL: {settings.DATABASE_URL}")
    init_db()
    print("Database tables initialized successfully!")

    print("\n--- 2. Testing AssessmentSession DB Save & Read via Storage Repository ---")
    session_id = "test_pg_session_999"
    
    sp_metrics = SpeechMetrics(
        duration_seconds=12.5,
        word_count=28,
        words_per_minute=134,
        filler_word_count=1,
        filler_frequency=0.035,
        filler_breakdown={"like": 1},
        pause_score=85,
        speech_score=88
    )
    
    vi_metrics = VideoMetrics(
        face_visibility_score=95,
        attention_score=88,
        posture_score=90,
        stability_score=92,
        video_score=91
    )

    q1 = QuestionItem(id=1, question="Explain PostgreSQL indexing strategy", topic="Database", source="role")
    q2 = QuestionItem(id=2, question="Describe your experience with FastAPI", topic="FastAPI", source="resume")

    sub1 = AnswerSubmission(
        question_id=1,
        answer_text="B-Tree indexes speed up lookups on indexed columns.",
        transcript="B-Tree indexes speed up lookups on indexed columns.",
        audio_path="uploads/recordings/test/q1.mp3",
        video_path="uploads/recordings/test/q1.webm",
        speech_metrics=sp_metrics,
        video_metrics=vi_metrics
    )

    eval_obj = MultimodalEvaluation(
        overall_score=89,
        nlp_score=88,
        speech_score=88,
        video_score=91,
        summary="Excellent technical performance and clear delivery.",
        strengths=["Deep understanding of indexing", "Strong posture & stability"],
        gaps=["Elaborate further on query plan execution"],
        recommendations=["Practice STAR method"],
        per_question=[
            QuestionEvaluation(
                question_id=1,
                question="Explain PostgreSQL indexing strategy",
                score=89,
                nlp_score=88,
                speech_score=88,
                video_score=91,
                feedback="Clear and accurate explanation.",
                transcript="B-Tree indexes speed up lookups on indexed columns."
            )
        ]
    )

    test_session = AssessmentSession(
        session_id=session_id,
        assessment_type=AssessmentType.INTERVIEW,
        selected_role="Database Architect",
        filename="architect_resume.pdf",
        resume_data={"skills": ["PostgreSQL", "FastAPI", "Python"]},
        questions=[q1, q2],
        submissions={1: sub1},
        evaluation=eval_obj,
        status="completed"
    )

    # Save to Database
    save_success = session_storage.save_session(test_session)
    assert save_success, "DB Session save failed"
    print("AssessmentSession saved to Database successfully!")

    # Read from Database
    loaded_session = session_storage.get_session(session_id)
    assert loaded_session is not None, "Failed to load session from DB"
    assert loaded_session.selected_role == "Database Architect", f"Role mismatch: {loaded_session.selected_role}"
    assert len(loaded_session.questions) == 2, f"Questions count mismatch: {len(loaded_session.questions)}"
    assert 1 in loaded_session.submissions, "Submission 1 missing"
    assert loaded_session.submissions[1].speech_metrics.words_per_minute == 134, "Speech WPM mismatch"
    assert loaded_session.evaluation.overall_score == 89, "Evaluation score mismatch"
    print("Database retrieval and ORM-to-domain mapping verified successfully!")

    print("\n--- 3. Testing Legacy JSON Migration Utility ---")
    migrated = migrate_json_sessions_to_db()
    print(f"JSON Session Migration finished. Processed {migrated} file(s).")

    # Clean up test session from DB
    session_storage.delete_session(session_id)
    print("\nALL POSTGRESQL & SQLALCHEMY DATABASE VERIFICATION TESTS PASSED!")

if __name__ == "__main__":
    run_db_pipeline_tests()
