from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SpeechMetrics(BaseModel):
    duration_seconds: float = 0.0
    word_count: int = 0
    words_per_minute: int = 0
    filler_word_count: int = 0
    filler_frequency: float = 0.0
    filler_breakdown: Dict[str, int] = Field(default_factory=dict)
    pause_score: int = 80
    speech_score: int = 80

class VideoMetrics(BaseModel):
    face_visibility_score: int = 85
    attention_score: int = 80
    posture_score: int = 82
    stability_score: int = 80
    video_score: int = 82

class QuestionEvaluation(BaseModel):
    question_id: int
    question: str
    score: int
    nlp_score: int
    speech_score: int
    video_score: int
    feedback: str
    transcript: Optional[str] = ""

class MultimodalEvaluation(BaseModel):
    overall_score: int
    nlp_score: int
    speech_score: int
    video_score: int
    summary: str
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    per_question: List[QuestionEvaluation] = Field(default_factory=list)
