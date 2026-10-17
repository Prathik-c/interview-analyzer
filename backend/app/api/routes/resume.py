from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from backend.app.utils.validators import validate_resume_file
from backend.app.services.interview_service import interview_service
from backend.app.api.deps import get_current_user_optional
from backend.app.db.models.user import UserDB

router = APIRouter()

@router.post("/resume/upload")
@router.post("/interview/resume")
@router.post("/parse-resume")
async def upload_resume(
    file: UploadFile = File(...),
    selected_role: str = Form(...),
    current_user: Optional[UserDB] = Depends(get_current_user_optional)
):
    if not selected_role or not selected_role.strip():
        raise HTTPException(status_code=400, detail="A selected job role is required.")

    content = await file.read()
    validate_resume_file(file, content)

    try:
        user_id = current_user.id if current_user else None
        from fastapi.concurrency import run_in_threadpool
        session = await run_in_threadpool(
            interview_service.create_interview_session,
            selected_role=selected_role,
            filename=file.filename or "resume.pdf",
            pdf_content=content,
            user_id=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Resume processing failed: {e}") from e

    questions_dict = [q.model_dump() for q in session.questions]
    return {
        "message": "Resume extracted and session initialized successfully.",
        "filename": file.filename,
        "accepted": True,
        "selected_role": session.selected_role,
        "session_id": session.session_id,
        "user_id": session.user_id,
        "questions": questions_dict,
        "first_question": questions_dict[0] if questions_dict else None,
        "extracted_terms": session.resume_data.get("skills", []) if session.resume_data else [],
        "resume_data": session.resume_data
    }
