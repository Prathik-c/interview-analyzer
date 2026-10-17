import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class NLPEvaluationDB(Base):
    __tablename__ = "nlp_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    technical_score = Column(Integer, default=80)
    relevance_score = Column(Integer, default=85)
    depth_score = Column(Integer, default=75)
    clarity_score = Column(Integer, default=80)
    strengths = Column(JSON, nullable=True)
    knowledge_gaps = Column(JSON, nullable=True)
    topics_detected = Column(JSON, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSessionDB", back_populates="nlp_evaluations")

class FinalEvaluationDB(Base):
    __tablename__ = "final_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    overall_score = Column(Integer, nullable=True)
    nlp_score = Column(Integer, nullable=True)
    speech_score = Column(Integer, nullable=True)
    video_score = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    strengths = Column(JSON, nullable=True)
    gaps = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    per_question = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSessionDB", back_populates="evaluation")
