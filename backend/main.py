import json
import shutil
import tempfile
from pathlib import Path

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

@app.get("/", include_in_schema=False)
async def read_root():
    return FileResponse(frontend_dir / "interview.html")


@app.get("/resume", include_in_schema=False)
async def resume_page():
    return FileResponse(frontend_dir / "resume.html")


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
        from ai.resume_extractor import parse_resume

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temporary_file:
            temporary_file.write(file_contents)
            temporary_path = temporary_file.name

        extracted_resume = parse_resume(temporary_path)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Resume extraction failed: {error}") from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)

    saved_resume = {
        "selected_role": selected_role.strip(),
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(file_contents),
        "resume": extracted_resume
    }
    resume_data_path.write_text(json.dumps(saved_resume, indent=2), encoding="utf-8")

    return {
        "message": "Resume extracted and saved",
        "filename": file.filename,
        "accepted": True,
        "selected_role": saved_resume["selected_role"],
        "extracted_terms": extracted_resume.get("skills", []),
        "resume_data": extracted_resume
    }

