from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.core.config import settings

db_url = settings.DATABASE_URL

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI Dependency for database session lifecycle management."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables."""
    from backend.app.db.models import (
        UserDB, AssessmentSessionDB, ResumeDB, QuestionDB, SubmissionDB,
        RecordingDB, SpeechAnalysisDB, VideoAnalysisDB, NLPEvaluationDB, FinalEvaluationDB
    )
    Base.metadata.create_all(bind=engine)
