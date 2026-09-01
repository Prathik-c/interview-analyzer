import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class SpeechAnalysisDB(Base):
    __tablename__ = "speech_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    wpm = Column(Integer, default=0)
    filler_count = Column(Integer, default=0)
    filler_frequency = Column(Float, default=0.0)
    speech_score = Column(Integer, default=80)
    metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSessionDB", back_populates="speech_analyses")
