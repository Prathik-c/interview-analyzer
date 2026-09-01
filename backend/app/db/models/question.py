import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class QuestionDB(Base):
    __tablename__ = "questions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)  # Sequential 1, 2, 3...
    question_text = Column(Text, nullable=False)
    topic = Column(String(255), default="General")
    difficulty = Column(String(50), default="MEDIUM")  # EASY, MEDIUM, HARD
    source = Column(String(50), default="role")  # resume, role, follow_up, remedial
    strategy = Column(String(50), default="NEW_TOPIC")
    reason = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSessionDB", back_populates="questions")
