import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class SubmissionDB(Base):
    __tablename__ = "answers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    answer_text = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    transcription_status = Column(String(50), default="COMPLETED")
    audio_path = Column(String(512), nullable=True)
    video_path = Column(String(512), nullable=True)
    speech_metrics = Column(JSON, nullable=True)
    video_metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSessionDB", back_populates="submissions")
