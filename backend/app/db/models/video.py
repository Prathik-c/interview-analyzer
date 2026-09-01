import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class VideoAnalysisDB(Base):
    __tablename__ = "video_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    face_visibility_score = Column(Integer, default=85)
    attention_score = Column(Integer, default=80)
    posture_score = Column(Integer, default=82)
    stability_score = Column(Integer, default=80)
    video_score = Column(Integer, default=82)
    metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSessionDB", back_populates="video_analyses")
