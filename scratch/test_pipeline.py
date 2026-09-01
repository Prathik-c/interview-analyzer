import os
import sys

# Ensure backend package importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal, init_db
from backend.app.services.auth_service import auth_service
from backend.app.schemas.auth import UserRegisterRequest, UserLoginRequest
from backend.app.services.interview_service import interview_service
from backend.app.services.adaptive_engine import adaptive_engine
from backend.app.storage.session_storage import session_storage

def run_tests():
    print("=== STARTING PHASE 1 FULL END-TO-END PIPELINE VERIFICATION ===")
    init_db()
    db: Session = SessionLocal()

    # 1. Test Authentication
    print("\n[TEST 1] User Registration & Login")
    test_email = "testuser_phase1@example.com"
    # Cleanup previous test user if exists
    from backend.app.db.models.user import UserDB
    existing = db.query(UserDB).filter(UserDB.email == test_email).first()
    if existing:
        db.delete(existing)
        db.commit()

    reg_req = UserRegisterRequest(name="Test User", email=test_email, password="securepassword123")
    user = auth_service.register_user(db, reg_req)
    assert user.email == test_email
    print(f"[OK] Registered user: {user.name} ({user.id})")

    login_req = UserLoginRequest(email=test_email, password="securepassword123")
    token_resp = auth_service.login_user(db, login_req)
    assert token_resp.access_token is not None
    print(f"[OK] Login successful. JWT token generated.")

    # 2. Test Session Creation & Question 1 Generation
    print("\n[TEST 2] Resume Upload & Adaptive Session Initialization (Question 1)")
    pdf_bytes = b"%PDF-1.4 sample PDF resume content for Python FastAPI Developer"
    session = interview_service.create_interview_session(
        selected_role="Software Engineer",
        filename="test_resume.pdf",
        pdf_content=pdf_bytes,
        user_id=user.id
    )
    assert session.session_id is not None
    assert len(session.questions) == 1
    q1 = session.questions[0]
    print(f"[OK] Session initialized ({session.session_id})")
    print(f"[OK] Question 1 generated: [{q1.topic} - {q1.difficulty}] {q1.question}")

    # 3. Test Multimodal Answer Submission for Question 1
    print("\n[TEST 3] Answer Submission & Multimodal Analysis Pipeline (Q1)")
    sample_webm = b"RIFF....WEBM sample bytes for recording"
    ans_res = interview_service.process_answer_submission(
        session_id=session.session_id,
        question_id=1,
        user_id=user.id,
        answer_text="I have 3 years of experience using Python, FastAPI, and PostgreSQL to build scalable REST APIs.",
        recording_bytes=sample_webm
    )
    assert ans_res["accepted"] is True
    assert ans_res["transcript"] is not None
    print(f"[OK] Q1 Answer processed!")
    print(f"  - Per-Question Score: {ans_res['per_question_score']}/100")
    print(f"  - Speech Metrics: WPM {ans_res['speech_metrics']['words_per_minute']}, Score {ans_res['speech_metrics']['speech_score']}")
    print(f"  - Video Metrics: Posture {ans_res['video_metrics']['posture_score']}%, Score {ans_res['video_metrics']['video_score']}")
    print(f"  - NLP Evaluation: Score {ans_res['nlp_score']}/100")

    # 4. Test Adaptive AI Engine Decision for Question 2
    print("\n[TEST 4] Adaptive AI Engine (Question 2 Generation)")
    q2_info = ans_res.get("next_question")
    assert q2_info is not None
    print(f"[OK] Adaptive Engine generated Question 2:")
    print(f"  - Strategy: {q2_info['strategy']}")
    print(f"  - Target Topic: {q2_info['topic']}")
    print(f"  - Difficulty: {q2_info['difficulty']}")
    print(f"  - Reason: {q2_info['reason']}")
    print(f"  - Question 2 Text: {q2_info['question']}")

    # 5. Answer Question 2 & Verify Question 3 Generation
    print("\n[TEST 5] Answer Submission Q2 -> Question 3 Generation")
    ans_res_q2 = interview_service.process_answer_submission(
        session_id=session.session_id,
        question_id=2,
        user_id=user.id,
        answer_text="Idempotency means making multiple identical requests has the same effect as making a single request. GET, PUT, and DELETE are idempotent.",
        recording_bytes=sample_webm
    )
    q3_info = ans_res_q2.get("next_question")
    assert q3_info is not None
    print(f"[OK] Question 3 generated adaptively: [{q3_info['topic']}] {q3_info['question']}")

    # 6. Final Report Evaluation & PostgreSQL Persistence Check
    print("\n[TEST 6] Final Multimodal Report Evaluation & DB Persistence")
    completed_session = interview_service.evaluate_session(session.session_id, user_id=user.id)
    assert completed_session.status == "completed"
    assert completed_session.evaluation is not None
    eval_report = completed_session.evaluation
    print(f"[OK] Final Report generated successfully!")
    print(f"  - Overall Score: {eval_report.overall_score}/100")
    print(f"  - NLP Technical Score: {eval_report.nlp_score}/100")
    print(f"  - Speech Score: {eval_report.speech_score}/100")
    print(f"  - Video Score: {eval_report.video_score}/100")
    print(f"  - Summary: {eval_report.summary}")

    # Verify session reload from Database
    reloaded = session_storage.get_session(session.session_id)
    assert reloaded is not None
    assert reloaded.evaluation.overall_score == eval_report.overall_score
    print("[OK] DB Persistence verified: Reloaded session from Database matches memory object!")


    db.close()
    print("\n=== ALL PHASE 1 PIPELINE TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
