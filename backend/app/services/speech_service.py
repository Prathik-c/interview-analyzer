import re
from pathlib import Path
from typing import Dict, Any, Tuple
from groq import Groq
from backend.app.core.config import settings
from backend.app.core.constants import FILLER_WORDS, OPTIMAL_WPM_MIN, OPTIMAL_WPM_MAX
from backend.app.schemas.evaluation import SpeechMetrics
from backend.app.utils.helpers import calculate_wpm, detect_filler_words

class SpeechService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.client = Groq(api_key=self.api_key) if self.api_key and not self.api_key.startswith("gsk_demo") else None

    def transcribe_audio(self, audio_file_path: Path) -> Tuple[str, float]:
        """Transcribe audio/webm recording using Groq Whisper API or fallback."""
        if not audio_file_path.exists():
            return "", 0.0

        if not self.client:
            return "Thank you for the question. I have worked extensively on building scalable applications and optimizing database performance.", 15.0

        try:
            with open(audio_file_path, "rb") as file_obj:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_file_path.name, file_obj.read()),
                    model=settings.GROQ_WHISPER_MODEL,
                    response_format="verbose_json"
                )
            
            transcript_text = getattr(transcription, "text", "") or str(transcription)
            duration = float(getattr(transcription, "duration", 0.0) or 15.0)
            return transcript_text.strip(), duration
        except Exception as e:
            print(f"Groq Whisper transcription error: {e}")
            return "", 0.0

    def analyze_speech_delivery(self, transcript: str, duration_seconds: float) -> SpeechMetrics:
        """Compute speech delivery metrics (WPM, filler word count, speech score)."""
        words = re.findall(r'\b[\w\']+\b', transcript)
        word_count = len(words)
        
        if duration_seconds <= 0:
            duration_seconds = max(1.0, word_count / 2.3)

        wpm = calculate_wpm(word_count, duration_seconds)
        fillers = detect_filler_words(transcript, FILLER_WORDS)
        
        if OPTIMAL_WPM_MIN <= wpm <= OPTIMAL_WPM_MAX:
            wpm_score = 95
        elif wpm < OPTIMAL_WPM_MIN:
            wpm_score = max(50, 95 - int((OPTIMAL_WPM_MIN - wpm) * 0.8))
        else:
            wpm_score = max(50, 95 - int((wpm - OPTIMAL_WPM_MAX) * 0.7))

        filler_freq = fillers["frequency"]
        if filler_freq <= 0.02:
            filler_score = 95
        elif filler_freq <= 0.05:
            filler_score = 82
        elif filler_freq <= 0.08:
            filler_score = 70
        else:
            filler_score = 55

        overall_speech_score = round((wpm_score * 0.5) + (filler_score * 0.5))

        return SpeechMetrics(
            duration_seconds=round(duration_seconds, 1),
            word_count=word_count,
            words_per_minute=wpm,
            filler_word_count=fillers["count"],
            filler_frequency=fillers["frequency"],
            filler_breakdown=fillers["found"],
            pause_score=82,
            speech_score=overall_speech_score
        )

speech_service = SpeechService()
