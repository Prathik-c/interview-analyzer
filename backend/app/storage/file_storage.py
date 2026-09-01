from pathlib import Path
from backend.app.core.config import settings

class FileStorage:
    def __init__(self, upload_dir: Path = settings.UPLOAD_DIR):
        self.upload_dir = upload_dir
        self.resumes_dir = settings.RESUMES_DIR
        self.recordings_dir = settings.RECORDINGS_DIR
        
        self.resumes_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def save_resume(self, session_id: str, filename: str, content: bytes) -> Path:
        """Save uploaded PDF resume to disk under uploads/resumes/{session_id}_{filename}."""
        safe_filename = filename.replace(" ", "_")
        target_path = self.resumes_dir / f"{session_id}_{safe_filename}"
        target_path.write_bytes(content)
        return target_path

    def save_recording(self, session_id: str, question_id: int, content: bytes, file_extension: str = "webm") -> Path:
        """Save candidate answer recording to disk under uploads/recordings/{session_id}_q{question_id}.webm."""
        target_path = self.recordings_dir / f"{session_id}_q{question_id}.{file_extension}"
        target_path.write_bytes(content)
        return target_path

file_storage = FileStorage()
