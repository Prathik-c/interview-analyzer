from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from backend.app.services.interview_service import interview_service
from backend.app.storage.session_storage import session_storage
from backend.app.api.deps import get_current_user_optional
from backend.app.db.models.user import UserDB

router = APIRouter()

@router.post("/interview/evaluate")
async def evaluate_interview(
    session_id: str = Query(...),
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    session = session_storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if current_user and session.user_id and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this interview session.")

    if not session.questions:
        raise HTTPException(status_code=400, detail="Session contains no questions.")

    user_id = current_user.id if current_user else None
    try:
        updated_session = interview_service.evaluate_session(session_id, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Multimodal evaluation failed: {e}") from e

    return {
        "accepted": True,
        "session_id": session_id,
        "evaluation": updated_session.evaluation.model_dump() if updated_session.evaluation else {}
    }

@router.get("/results/{session_id}")
async def get_results(
    session_id: str,
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    session = session_storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if current_user and session.user_id and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this interview session.")

    if not session.evaluation:
        # Run evaluation if session completed but evaluation not cached
        user_id = current_user.id if current_user else None
        session = interview_service.evaluate_session(session_id, user_id=user_id)

    return {
        "session_id": session_id,
        "selected_role": session.selected_role,
        "evaluation": session.evaluation.model_dump() if session.evaluation else {}
    }
