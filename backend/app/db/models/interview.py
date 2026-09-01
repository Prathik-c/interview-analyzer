import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class AssessmentSessionDB(Base):
    __tablename__ = "interview_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    assessment_type = Column(String(50), default="INTERVIEW", nullable=False)
    selected_role = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    resume_data = Column(JSON, nullable=True)
    status = Column(String(50), default="active")  # active | completed | failed
    current_question_number = Column(Integer, default=1)
    state_data = Column(JSON, nullable=True)  # candidate skill map, topics tested, strengths, gaps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("UserDB", back_populates="sessions")
    resume = relationship("ResumeDB", back_populates="session", uselist=False, cascade="all, delete-orphan")
    questions = relationship("QuestionDB", back_populates="session", cascade="all, delete-orphan")
    submissions = relationship("SubmissionDB", back_populates="session", cascade="all, delete-orphan")
    recordings = relationship("RecordingDB", back_populates="session", cascade="all, delete-orphan")
    speech_analyses = relationship("SpeechAnalysisDB", back_populates="session", cascade="all, delete-orphan")
    video_analyses = relationship("VideoAnalysisDB", back_populates="session", cascade="all, delete-orphan")
    nlp_evaluations = relationship("NLPEvaluationDB", back_populates="session", cascade="all, delete-orphan")
    evaluation = relationship("FinalEvaluationDB", back_populates="session", uselist=False, cascade="all, delete-orphan")
