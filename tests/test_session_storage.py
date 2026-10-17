import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uuid
from backend.app.schemas.interview import AssessmentSession, AnswerSubmission
from backend.app.schemas.question import QuestionItem
from backend.app.schemas.evaluation import SpeechMetrics, VideoMetrics
from backend.app.storage.session_storage import session_storage


def test_session_storage_roundtrip():
    session_id = str(uuid.uuid4())
    q1 = QuestionItem(
        id=1,
        question="Explain why normalization of pixel values is important.",
        topic="Computer Vision",
        difficulty="EASY"
    )

    speech_metrics = SpeechMetrics(
        duration_seconds=12.5,
        word_count=30,
        words_per_minute=144,
        filler_word_count=1,
        pause_count=2,
        speech_score=88
    )

    video_metrics = VideoMetrics(
        frames_sampled=25,
        pose_detection_rate=0.92,
        video_score=85,
        analysis_method="mediapipe_pose"
    )

    nlp_eval = {
        "evaluation_method": "combined",
        "overall_nlp_score": 70,
        "combined_nlp_score": 66,
        "structured_score": 60,
        "evaluation_status": "ok",
        "evaluation_error": None,
        "feedback": "Clear answer with sound reasoning.",
        "technical_score": 75,
        "relevance_score": 80
    }

    sub1 = AnswerSubmission(
        question_id=1,
        answer_text="Normalization scales pixels to stable ranges.",
        transcript="Normalization scales pixels to stable ranges.",
        transcription_status="ok",
        audio_path="uploads/recordings/sample.mp3",
        video_path="uploads/recordings/sample.webm",
        speech_metrics=speech_metrics,
        video_metrics=video_metrics,
        nlp_evaluation=nlp_eval
    )

    session = AssessmentSession(
        session_id=session_id,
        user_id=None,
        selected_role="Software Engineer",
        questions=[q1],
        submissions={1: sub1},
        status="active"
    )

    # 1. Save session
    saved_ok = session_storage.save_session(session)
    assert saved_ok, "save_session failed"

    # 2. Fresh reload from database
    reloaded = session_storage.get_session(session_id)
    assert reloaded is not None, "get_session returned None"
    assert 1 in reloaded.submissions, "Question 1 submission missing after reload"

    reloaded_sub = reloaded.submissions[1]

    # Compare fields and collect diffs
    diffs = []
    if reloaded_sub.transcription_status != sub1.transcription_status:
        diffs.append(f"transcription_status: expected {sub1.transcription_status!r}, got {reloaded_sub.transcription_status!r}")
    if reloaded_sub.audio_path != sub1.audio_path:
        diffs.append(f"audio_path: expected {sub1.audio_path!r}, got {reloaded_sub.audio_path!r}")
    if reloaded_sub.video_path != sub1.video_path:
        diffs.append(f"video_path: expected {sub1.video_path!r}, got {reloaded_sub.video_path!r}")
    if reloaded_sub.transcript != sub1.transcript:
        diffs.append(f"transcript: expected {sub1.transcript!r}, got {reloaded_sub.transcript!r}")
    if reloaded_sub.answer_text != sub1.answer_text:
        diffs.append(f"answer_text: expected {sub1.answer_text!r}, got {reloaded_sub.answer_text!r}")
    if reloaded_sub.nlp_evaluation != sub1.nlp_evaluation:
        diffs.append(f"nlp_evaluation: expected {sub1.nlp_evaluation!r}, got {reloaded_sub.nlp_evaluation!r}")
    if reloaded_sub.speech_metrics.model_dump() != sub1.speech_metrics.model_dump():
        diffs.append("speech_metrics mismatch")
    if reloaded_sub.video_metrics.model_dump() != sub1.video_metrics.model_dump():
        diffs.append("video_metrics mismatch")

    if diffs:
        msg = "Session roundtrip mismatch:\n  " + "\n  ".join(diffs)
        print(msg)
        raise AssertionError(msg)

    print("Session roundtrip test passed!")


if __name__ == "__main__":
    test_session_storage_roundtrip()
