import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root directory (backend/app/core -> project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Explicitly load .env file from project root
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

class Settings:
    PROJECT_NAME: str = os.getenv("APP_TITLE", "AI-Powered Multimodal Interview Performance Analyser")
    ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Security / JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-in-production-interview-analyser-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # API Keys & LLM Models
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_LLM_MODEL: str = os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-120b")
    GROQ_WHISPER_MODEL: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

    # Database Configuration (PostgreSQL with SQLite fallback)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./interview.db")

    # Directory Paths
    BASE_DIR: Path = BASE_DIR
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data/sessions")
    UPLOAD_DIR: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
    RESUMES_DIR: Path = UPLOAD_DIR / "resumes"
    RECORDINGS_DIR: Path = UPLOAD_DIR / "recordings"

    # Multimodal Evaluation Weights (Must total 1.0)
    WEIGHT_NLP: float = float(os.getenv("WEIGHT_NLP", "0.50"))
    WEIGHT_SPEECH: float = float(os.getenv("WEIGHT_SPEECH", "0.25"))
    WEIGHT_VIDEO: float = float(os.getenv("WEIGHT_VIDEO", "0.25"))

    # Local Structured Evaluation Settings (Zero-Cost Local Layer)
    STRUCTURED_EVALUATION_ENABLED: bool = os.getenv("STRUCTURED_EVALUATION_ENABLED", "true").lower() == "true"
    STRUCTURED_EVALUATION_WEIGHT: float = float(os.getenv("STRUCTURED_EVALUATION_WEIGHT", "0.25"))

    def __init__(self):
        # Validate evaluation weights sum to 1.0
        total_weight = round(self.WEIGHT_NLP + self.WEIGHT_SPEECH + self.WEIGHT_VIDEO, 2)
        if total_weight != 1.0:
            print(f"Warning: Evaluation weights sum to {total_weight}, expected 1.0")

    def ensure_directories(self):
        """Ensure all required runtime directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        self.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
