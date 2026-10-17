from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PauseEvent(BaseModel):
    """Represents a detected pause or silence interval in the audio."""
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    is_long_pause: bool = False  # exceeds configurable long-pause threshold


class SpeechMetrics(BaseModel):
    # Core timing
    duration_seconds: float = 0.0
    word_count: int = 0
    words_per_minute: int = 0

    # Filler detection
    filler_word_count: int = 0
    filler_frequency: float = 0.0
    filler_breakdown: Dict[str, int] = Field(default_factory=dict)

    # Pause analysis
    pause_count: int = 0
    long_pause_count: int = 0
    total_pause_duration: float = 0.0
    average_pause_duration: float = 0.0
    longest_pause_seconds: float = 0.0
    pause_events: List[PauseEvent] = Field(default_factory=list)

    # Inter-word gap statistics (populated when word timestamps are available)
    has_word_timestamps: bool = False
    median_inter_word_gap_ms: Optional[float] = None
    mean_inter_word_gap_ms: Optional[float] = None
    long_gap_count: Optional[int] = None
    longest_gap_ms: Optional[float] = None

    # Delivery patterns (optional, clearly labelled)
    speaking_rate_category: str = "normal"  # "slow" / "normal" / "fast"
    delivery_pattern_notes: List[str] = Field(default_factory=list)

    # Warnings about confidence / data quality
    analysis_warnings: List[str] = Field(default_factory=list)
    analysis_method: str = "transcript_only"  # "transcript_only" / "audio_energy" / "word_timestamps"

    # Scores (computed, not hardcoded; None when signal not measured)
    pause_score: Optional[int] = None
    speech_score: Optional[int] = None


class VideoMetrics(BaseModel):
    # Detection coverage
    frames_sampled: int = 0
    frames_with_face: int = 0
    face_detection_rate: float = 0.0   # 0.0–1.0
    pose_detection_rate: float = 0.0   # 0.0–1.0 (MediaPipe, if used)

    # Observable signals (None when signal not measured)
    face_visibility_score: Optional[int] = None
    attention_score: Optional[int] = None
    posture_score: Optional[int] = None
    stability_score: Optional[int] = None
    movement_variation: Optional[float] = None   # upper-body movement StdDev
    head_movement_variation: Optional[float] = None

    # Analysis metadata
    video_analysis_enabled: bool = True
    analysis_method: str = "unavailable"  # "haar_cascade" / "mediapipe_pose" / "unavailable"
    analysis_warnings: List[str] = Field(default_factory=list)

    # Delivery pattern notes (observable, not diagnostic)
    delivery_pattern_notes: List[str] = Field(default_factory=list)
    posture_unavailable_reason: Optional[str] = None

    video_score: Optional[int] = None


class QuestionEvaluation(BaseModel):
    question_id: int
    question: str
    score: Optional[int] = None
    nlp_score: Optional[int] = None
    speech_score: Optional[int] = None
    video_score: Optional[int] = None
    duration_seconds: Optional[float] = None
    modalities_used: List[str] = Field(default_factory=list)
    feedback: str
    transcript: Optional[str] = ""
    transcription_status: Optional[str] = "no_recording"   # "ok" / "empty" / "failed" / "no_recording"

    # Structured evaluator output (local layer)
    structured_score: Optional[int] = None
    technical_correctness: Optional[int] = None
    relevance_score: Optional[int] = None
    completeness_score: Optional[int] = None
    covered_concepts: Optional[List[str]] = None
    missing_concepts: Optional[List[str]] = None
    misconceptions: Optional[List[str]] = None
    major_misconception: Optional[bool] = None
    needs_followup: Optional[bool] = None
    reasoning_summary: Optional[str] = None
    evaluation_method: Optional[str] = None   # "groq_only" / "local_only" / "combined"
    pause_count: Optional[int] = None
    long_pause_count: Optional[int] = None
    longest_pause_seconds: Optional[float] = None
    filler_word_count: Optional[int] = None
    filler_breakdown: Dict[str, int] = Field(default_factory=dict)


class MultimodalEvaluation(BaseModel):
    overall_score: Optional[int] = None
    nlp_score: Optional[int] = None
    speech_score: Optional[int] = None
    video_score: Optional[int] = None
    modalities_used: List[str] = Field(default_factory=list)
    summary: str
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    per_question: List[QuestionEvaluation] = Field(default_factory=list)

    # Aggregated speech delivery across interview
    avg_wpm: Optional[int] = None
    total_filler_count: Optional[int] = None
    total_pause_count: Optional[int] = None
    total_long_pause_count: Optional[int] = None
    longest_pause_seconds: Optional[float] = None
    filler_breakdown: Dict[str, int] = Field(default_factory=dict)
    delivery_pattern_notes: List[str] = Field(default_factory=list)

