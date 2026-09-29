from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from pydantic import BaseModel, Field
from backend.app.services.interview_service import interview_service
from backend.app.storage.session_storage import session_storage
from backend.app.api.deps import get_current_user_optional, get_current_user
from backend.app.db.models.user import UserDB
from backend.app.core.constants import JOB_ROLES

router = APIRouter()

@router.get("/interview/roles")
async def get_roles():
    """Retrieve list of supported interview roles."""
    return {"roles": JOB_ROLES}

@router.get("/interview/history")
async def get_user_interview_history(
    current_user: UserDB = Depends(get_current_user)
):
    """Retrieve authenticated user's interview history with performance summaries."""
    sessions = session_storage.get_user_sessions(current_user.id)
    return {"sessions": sessions}

class InterviewStartRequest(BaseModel):
    selected_role: str = Field(min_length=1, max_length=100)

class InterviewAnswerRequest(BaseModel):
    session_id: str
    question_id: int
    answer: Optional[str] = ""

@router.post("/interview/start")
async def start_interview(
    req: InterviewStartRequest,
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    """Start an interview session without PDF upload (fallback)."""
    user_id = current_user.id if current_user else None
    # Create empty resume content placeholder
    session = interview_service.create_interview_session(
        selected_role=req.selected_role,
        filename="manual_start.pdf",
        pdf_content=b"%PDF-1.4 sample empty pdf content",
        user_id=user_id
    )
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "selected_role": session.selected_role,
        "question": session.questions[0].model_dump() if session.questions else None
    }

@router.post("/interview/answer")
async def save_interview_answer(
    request: InterviewAnswerRequest,
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    user_id = current_user.id if current_user else None
    res = interview_service.process_answer_submission(
        session_id=request.session_id,
        question_id=request.question_id,
        user_id=user_id,
        answer_text=request.answer
    )
    return res

@router.post("/interview/{session_id}/recording")
@router.post("/interview/{session_id}/answer")
async def upload_question_recording(
    session_id: str,
    question_id: int = Form(...),
    video: Optional[UploadFile] = File(None),
    answer: Optional[str] = Form(None),
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    user_id = current_user.id if current_user else None
    rec_bytes = None
    if video:
        rec_bytes = await video.read()

    if not rec_bytes and not answer:
        raise HTTPException(status_code=400, detail="Either video recording file or text answer is required.")

    try:
        res = interview_service.process_answer_submission(
            session_id=session_id,
            question_id=question_id,
            user_id=user_id,
            answer_text=answer or "",
            recording_bytes=rec_bytes
        )
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process answer recording: {e}") from e

@router.get("/interview/session/{session_id}")
async def get_interview_session(
    session_id: str,
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    session = session_storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if current_user and session.user_id and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this interview session.")

    answers_list = []
    for q_id, sub in session.submissions.items():
        answers_list.append({
            "question_id": q_id,
            "answer": sub.transcript or sub.answer_text or "",
            "speech_metrics": sub.speech_metrics.model_dump() if sub.speech_metrics else None,
            "video_metrics": sub.video_metrics.model_dump() if sub.video_metrics else None
        })

    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "assessment_type": session.assessment_type,
        "selected_role": session.selected_role,
        "filename": session.filename,
        "questions": [q.model_dump() for q in session.questions],
        "answers": answers_list,
        "evaluation": session.evaluation.model_dump() if session.evaluation else None,
        "status": session.status,
        "current_question_number": session.current_question_number,
        "state_data": session.state_data
    }
