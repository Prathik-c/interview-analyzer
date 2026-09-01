from fastapi import HTTPException, UploadFile

def validate_resume_file(file: UploadFile, content: bytes):
    """Validate uploaded resume file extension and non-empty content."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF resumes (.pdf) are supported."
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded resume file is empty."
        )
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=400,
            detail="Resume file size exceeds maximum limit of 10MB."
        )
