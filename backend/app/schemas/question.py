from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class QuestionItem(BaseModel):
    id: int
    question: str
    topic: Optional[str] = "General"
    difficulty: Optional[str] = "MEDIUM"  # EASY, MEDIUM, HARD
    source: Optional[str] = "role"  # resume | role | follow_up | remedial
    strategy: Optional[str] = "NEW_TOPIC"
    reason: Optional[str] = None
    expected_concepts: Optional[List[str]] = Field(default_factory=list)

class AdaptiveEngineDecision(BaseModel):
    next_difficulty: str = "MEDIUM"
    question_strategy: str = "NEW_TOPIC"
    target_topic: str = "Technical"
    reason: str = ""
    next_question: str = ""
