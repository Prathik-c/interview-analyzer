import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI()
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
load_dotenv(frontend_dir.parent / ".env")
resume_data_path = frontend_dir.parent / "resume_data.json"

app.mount("/assets", StaticFiles(directory=frontend_dir), name="frontend-assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


class InterviewStartRequest(BaseModel):
    selected_role: str = Field(min_length=1, max_length=100)


class InterviewAnswerRequest(BaseModel):
    session_id: str = Field(min_length=1)
    question_id: int
    answer: str = Field(max_length=5000)

@app.get("/", include_in_schema=False)
async def read_root():
    return FileResponse(frontend_dir / "interview.html")


@app.get("/resume", include_in_schema=False)
async def resume_page():
    return FileResponse(frontend_dir / "resume.html")


@app.get("/interview", include_in_schema=False)
async def interview_page():
    return FileResponse(frontend_dir / "questions.html")


@app.get("/results", include_in_schema=False)
async def results_page():
    return FileResponse(frontend_dir / "results.html")


@app.post("/api/interview/start")
async def start_interview(request: InterviewStartRequest):
    return {
        "message": "Interview session ready",
        "selected_role": request.selected_role
    }


@app.post("/api/interview/resume")
@app.post("/parse-resume")
async def upload_resume(
    file: UploadFile = File(...),
    selected_role: str = Form(...)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Please upload a PDF resume.")
    if not selected_role.strip():
        raise HTTPException(status_code=400, detail="A selected job role is required.")

    file_contents = await file.read()
    if not file_contents:
        raise HTTPException(status_code=400, detail="The uploaded resume is empty.")

    temporary_path = None
    try:
        from ai.resume_extractor import generate_initial_questions, parse_resume

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temporary_file:
            temporary_file.write(file_contents)
            temporary_path = temporary_file.name

        extracted_resume = parse_resume(temporary_path)
        questions = generate_initial_questions(selected_role.strip(), extracted_resume)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Resume extraction failed: {error}") from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)

    saved_resume = {
        "session_id": str(uuid4()),
        "selected_role": selected_role.strip(),
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(file_contents),
        "resume": extracted_resume,
        "questions": questions,
        "answers": []
    }
    resume_data_path.write_text(json.dumps(saved_resume, indent=2), encoding="utf-8")

    return {
        "message": "Resume extracted and saved",
        "filename": file.filename,
        "accepted": True,
        "selected_role": saved_resume["selected_role"],
        "session_id": saved_resume["session_id"],
        "questions": questions,
        "extracted_terms": extracted_resume.get("skills", []),
        "resume_data": extracted_resume
    }


@app.get("/api/interview/session/{session_id}")
async def get_interview_session(session_id: str):
    if not resume_data_path.exists():
        raise HTTPException(status_code=404, detail="Interview session not found.")

    saved_resume = json.loads(resume_data_path.read_text(encoding="utf-8"))
    if saved_resume.get("session_id") != session_id:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    return {
        "session_id": session_id,
        "selected_role": saved_resume.get("selected_role"),
        "questions": saved_resume.get("questions", []),
        "answers": saved_resume.get("answers", []),
        "evaluation": saved_resume.get("evaluation")
    }


@app.post("/api/interview/answer")
async def save_interview_answer(request: InterviewAnswerRequest):
    if not resume_data_path.exists():
        raise HTTPException(status_code=404, detail="Interview session not found.")

    saved_resume = json.loads(resume_data_path.read_text(encoding="utf-8"))
    if saved_resume.get("session_id") != request.session_id:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    question = next(
        (item for item in saved_resume.get("questions", []) if item.get("id") == request.question_id),
        None
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")

    answers = saved_resume.setdefault("answers", [])
    saved_answer = next(
        (item for item in answers if item.get("question_id") == request.question_id),
        None
    )
    if saved_answer is None:
        answers.append({"question_id": request.question_id, "answer": request.answer})
    else:
        saved_answer["answer"] = request.answer

    resume_data_path.write_text(json.dumps(saved_resume, indent=2), encoding="utf-8")
    return {"accepted": True, "question_id": request.question_id}


@app.post("/api/interview/evaluate")
async def evaluate_interview(session_id: str):
    if not resume_data_path.exists():
        raise HTTPException(status_code=404, detail="Interview session not found.")

    saved_resume = json.loads(resume_data_path.read_text(encoding="utf-8"))
    if saved_resume.get("session_id") != session_id:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    questions = saved_resume.get("questions", [])
    answers = saved_resume.get("answers", [])
    if not questions or len(answers) < len(questions):
        raise HTTPException(status_code=400, detail="Answer every question before finishing.")

    try:
        from ai.resume_extractor import generate_evaluation

        evaluation = generate_evaluation(
            saved_resume["selected_role"], saved_resume["resume"], questions, answers
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Evaluation failed: {error}") from error

    saved_resume["evaluation"] = evaluation
    resume_data_path.write_text(json.dumps(saved_resume, indent=2), encoding="utf-8")
    return {"accepted": True, "session_id": session_id, "evaluation": evaluation}

