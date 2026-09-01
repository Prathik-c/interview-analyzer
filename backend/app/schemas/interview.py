from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.app.core.constants import AssessmentType
from backend.app.schemas.question import QuestionItem
from backend.app.schemas.evaluation import SpeechMetrics, VideoMetrics, MultimodalEvaluation

class AnswerSubmission(BaseModel):
    question_id: int
    answer_text: Optional[str] = ""
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    transcript: Optional[str] = ""
    speech_metrics: Optional[SpeechMetrics] = Field(default_factory=SpeechMetrics)
    video_metrics: Optional[VideoMetrics] = Field(default_factory=VideoMetrics)

class AssessmentSession(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    assessment_type: AssessmentType = AssessmentType.INTERVIEW
    selected_role: str
    filename: Optional[str] = None
    resume_data: Optional[Dict[str, Any]] = None
    questions: List[QuestionItem] = Field(default_factory=list)
    submissions: Dict[int, AnswerSubmission] = Field(default_factory=dict)
    evaluation: Optional[MultimodalEvaluation] = None
    status: str = "active"
    current_question_number: int = 1
    state_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: Optional[str] = None
