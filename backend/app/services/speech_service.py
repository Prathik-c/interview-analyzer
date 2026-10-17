"""
speech_service.py — Speech-to-text transcription + delivery analysis.

Transcription:  Groq Whisper (whisper-large-v3-turbo by default).
Pause detection: Audio-energy-based via pydub (fallback: transcript-only estimates).
Word timestamps: Captured from Groq verbose_json if the SDK exposes them.
"""

import re
import math
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

from groq import Groq
from backend.app.core.config import settings
from backend.app.core.constants import FILLER_WORDS, OPTIMAL_WPM_MIN, OPTIMAL_WPM_MAX
from backend.app.schemas.evaluation import SpeechMetrics, PauseEvent
from backend.app.utils.helpers import calculate_wpm, detect_filler_words

logger = logging.getLogger("speech_service")

# ── Configurable thresholds ────────────────────────────────────────────────────
# Gap (in seconds) between words above which we count it as a "pause"
SHORT_PAUSE_THRESHOLD_S: float = 0.5
LONG_PAUSE_THRESHOLD_S:  float = 2.0

# Audio energy threshold for silence detection (0–255 RMS, pydub)
SILENCE_THRESHOLD_DBFS: float = -40.0   # dBFS below which a segment is "silent"
MIN_SILENCE_LEN_MS:     int   = 500     # minimum silence length in ms to count as a pause

# WPM reference range (from settings, with defaults)
WPM_MIN = OPTIMAL_WPM_MIN  # 120
WPM_MAX = OPTIMAL_WPM_MAX  # 170


# ── Audio-energy pause detection (requires pydub + ffmpeg) ────────────────────
def _detect_pauses_audio(audio_path: Path) -> List[PauseEvent]:
    """
    Detect silence/pause intervals in an audio file using pydub's
    energy-based silence detection with relative threshold (audio.dBFS - 16).
    """
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_silence
    except ImportError:
        logger.info("pydub not installed — audio pause detection unavailable.")
        return []

    try:
        audio = AudioSegment.from_file(str(audio_path))

        # Relative threshold: audio.dBFS - 16 dB (handles noisy / varied mics)
        if audio.dBFS == float("-inf") or math.isinf(audio.dBFS):
            return []
        rel_silence_thresh = max(-60.0, audio.dBFS - 16.0)

        silence_ranges = detect_silence(
            audio,
            min_silence_len=MIN_SILENCE_LEN_MS,
            silence_thresh=rel_silence_thresh
        )

        events = []
        for start_ms, end_ms in silence_ranges:
            dur_s = round((end_ms - start_ms) / 1000.0, 2)
            if dur_s >= SHORT_PAUSE_THRESHOLD_S:
                events.append(PauseEvent(
                    start_seconds=round(start_ms / 1000.0, 2),
                    end_seconds=round(end_ms / 1000.0, 2),
                    duration_seconds=dur_s,
                    is_long_pause=(dur_s >= LONG_PAUSE_THRESHOLD_S)
                ))
        return events

    except Exception as e:
        logger.warning(f"Audio pause detection error: {e}")
        return []


def _extract_word_timestamps(transcription_obj) -> Optional[List[Dict[str, Any]]]:
    """
    Attempt to extract word-level timestamps from a Groq verbose_json response.
    Checks both direct .words and segment-nested .words.
    """
    # 1. Direct words attribute
    words = getattr(transcription_obj, "words", None)
    if words and isinstance(words, list) and len(words) > 0:
        first = words[0]
        if isinstance(first, dict) and "word" in first:
            return words
        if hasattr(first, "word") and hasattr(first, "start") and hasattr(first, "end"):
            return [{"word": getattr(w, "word", ""), "start": float(w.start), "end": float(w.end)} for w in words]

    # 2. Segment-nested words attribute
    segments = getattr(transcription_obj, "segments", None)
    if segments and isinstance(segments, list):
        collected = []
        for seg in segments:
            seg_words = getattr(seg, "words", None) if not isinstance(seg, dict) else seg.get("words")
            if seg_words and isinstance(seg_words, list):
                for w in seg_words:
                    if isinstance(w, dict) and "word" in w:
                        collected.append(w)
                    elif hasattr(w, "word") and hasattr(w, "start") and hasattr(w, "end"):
                        collected.append({"word": getattr(w, "word", ""), "start": float(w.start), "end": float(w.end)})
        if collected:
            return collected

    return None


def _compute_inter_word_gaps(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate inter-word gap statistics from word-level timestamps.
    gap = next_word_start - previous_word_end  (in seconds)
    """
    gaps_ms = []
    for i in range(1, len(words)):
        prev_end   = words[i - 1].get("end", 0.0)
        next_start = words[i].get("start", 0.0)
        gap_s = next_start - prev_end
        if gap_s >= 0:
            gaps_ms.append(gap_s * 1000.0)

    if not gaps_ms:
        return {}

    sorted_gaps = sorted(gaps_ms)
    n = len(sorted_gaps)
    median = sorted_gaps[n // 2] if n % 2 == 1 else (sorted_gaps[n // 2 - 1] + sorted_gaps[n // 2]) / 2
    mean   = sum(sorted_gaps) / n
    long_gap_threshold_ms = SHORT_PAUSE_THRESHOLD_S * 1000
    long_gap_count = sum(1 for g in gaps_ms if g >= long_gap_threshold_ms)

    return {
        "median_inter_word_gap_ms": round(median, 1),
        "mean_inter_word_gap_ms":   round(mean, 1),
        "long_gap_count":           long_gap_count,
        "longest_gap_ms":           round(max(gaps_ms), 1)
    }


# ── Speaking rate interpretation ───────────────────────────────────────────────
def _classify_wpm(wpm: int) -> str:
    if wpm == 0:
        return "no_speech"
    if wpm < WPM_MIN:
        return "slow"
    if wpm > WPM_MAX:
        return "fast"
    return "normal"


class SpeechService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.client = (
            Groq(api_key=self.api_key)
            if self.api_key and not self.api_key.startswith("gsk_demo")
            else None
        )
        if not self.client:
            logger.warning(
                "Groq client not configured — transcription unavailable. "
                "Set GROQ_API_KEY in .env to enable Whisper transcription."
            )

    def transcribe_audio(self, audio_file_path: Path) -> Tuple[str, float, Optional[List[Dict]]]:
        """
        Transcribe audio using Groq Whisper with word timestamp granularities and natural disfluency prompting.

        Returns:
            (transcript_text, duration_seconds, word_timestamps_or_None)
        """
        if not audio_file_path.exists():
            logger.warning(f"Audio file not found: {audio_file_path}")
            return "", 0.0, None

        if not self.client:
            return "", 0.0, None

        # Natural disfluency prompt prevents Whisper from silently stripping fillers like um/uh/hmm
        disfluency_prompt = "Umm, uh, hmm, like, you know, I mean, so, basically..."

        try:
            with open(audio_file_path, "rb") as f:
                audio_bytes = f.read()

            try:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_file_path.name, audio_bytes),
                    model=settings.GROQ_WHISPER_MODEL,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"],
                    prompt=disfluency_prompt
                )
            except Exception as initial_err:
                logger.warning(
                    f"Whisper call with timestamp_granularities failed: {initial_err}. Retrying without granularities..."
                )
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_file_path.name, audio_bytes),
                    model=settings.GROQ_WHISPER_MODEL,
                    response_format="verbose_json",
                    prompt=disfluency_prompt
                )

            transcript_text = getattr(transcription, "text", "") or ""
            duration = float(getattr(transcription, "duration", 0.0) or 0.0)
            word_timestamps = _extract_word_timestamps(transcription)

            if word_timestamps:
                logger.info(f"Word-level timestamps available: {len(word_timestamps)} words")
            else:
                logger.info("Word-level timestamps not available from this Groq response.")

            return transcript_text.strip(), duration, word_timestamps

        except Exception as e:
            logger.error(f"Groq Whisper transcription error: {e}")
            return "", 0.0, None

    def analyze_speech_delivery(
        self,
        transcript: str,
        duration_seconds: float,
        audio_path: Optional[Path] = None,
        word_timestamps: Optional[List[Dict]] = None
    ) -> SpeechMetrics:
        """
        Compute speech delivery metrics with accurate word-gap pause detection,
        energy fallback, and weight renormalization when pauses cannot be measured.
        """
        analysis_warnings: List[str] = []
        delivery_notes: List[str] = []
        analysis_method = "transcript_only"

        # ── Word-level metrics ────────────────────────────────────────────────
        words = re.findall(r"\b[\w']+\b", transcript)
        word_count = len(words)

        if duration_seconds <= 0:
            if word_count > 0:
                duration_seconds = max(1.0, word_count / 2.3)  # rough estimate
                analysis_warnings.append("Audio duration unavailable — WPM is an estimate.")
            else:
                duration_seconds = 0.0

        wpm = calculate_wpm(word_count, duration_seconds) if duration_seconds > 0 else 0
        fillers = detect_filler_words(transcript, FILLER_WORDS)
        rate_category = _classify_wpm(wpm)

        # WPM interpretation note
        ref_range = f"{WPM_MIN}–{WPM_MAX} WPM"
        if rate_category == "slow" and wpm > 0:
            delivery_notes.append(
                f"Speaking rate ({wpm} WPM) is below conversational reference range ({ref_range}). "
                "This may reflect careful articulation, technical explanation, or language pacing."
            )
        elif rate_category == "fast":
            delivery_notes.append(
                f"Speaking rate ({wpm} WPM) is above conversational reference range ({ref_range}). "
                "Consider whether clarity was maintained."
            )

        # ── Inter-word gap stats & Pause Events from Word Timestamps ──────────
        inter_word_stats: Dict[str, Any] = {}
        has_word_timestamps = False
        pause_events: List[PauseEvent] = []

        if word_timestamps and len(word_timestamps) > 1:
            has_word_timestamps = True
            analysis_method = "word_timestamps"
            inter_word_stats = _compute_inter_word_gaps(word_timestamps)

            # Build PauseEvent objects directly from inter-word gaps
            for i in range(1, len(word_timestamps)):
                prev_end = float(word_timestamps[i - 1].get("end", 0.0) or 0.0)
                next_start = float(word_timestamps[i].get("start", 0.0) or 0.0)
                gap_s = round(next_start - prev_end, 2)
                if gap_s >= SHORT_PAUSE_THRESHOLD_S:
                    pause_events.append(PauseEvent(
                        start_seconds=round(prev_end, 2),
                        end_seconds=round(next_start, 2),
                        duration_seconds=gap_s,
                        is_long_pause=(gap_s >= LONG_PAUSE_THRESHOLD_S)
                    ))

        # ── Audio Energy Fallback / Supplement without double counting ────────
        energy_events: List[PauseEvent] = []
        if audio_path and audio_path.exists():
            energy_events = _detect_pauses_audio(audio_path)

        if not has_word_timestamps:
            if energy_events:
                pause_events = energy_events
                analysis_method = "audio_energy"
                analysis_warnings.append(
                    "Pause events are estimated from audio energy analysis, not exact word-to-word gaps."
                )
            elif audio_path and audio_path.exists():
                analysis_warnings.append(
                    "Audio pause detection did not detect silences or audio was silent."
                )
            else:
                analysis_warnings.append(
                    "No audio file provided. Pause data unavailable; only WPM and filler counts are shown."
                )
        else:
            # Word timestamps were used. Include any non-overlapping audio energy pauses
            for ev in energy_events:
                overlaps = any(
                    not (ev.end_seconds <= p.start_seconds or ev.start_seconds >= p.end_seconds)
                    for p in pause_events
                )
                if not overlaps and ev.duration_seconds >= SHORT_PAUSE_THRESHOLD_S:
                    pause_events.append(ev)
            pause_events.sort(key=lambda p: p.start_seconds)

        # ── Aggregate pause stats ─────────────────────────────────────────────
        has_pause_data = has_word_timestamps or bool(energy_events)
        pause_count = len(pause_events)
        long_pause_count = sum(1 for p in pause_events if p.is_long_pause)
        total_pause_dur = sum(p.duration_seconds for p in pause_events)
        avg_pause_dur = (total_pause_dur / pause_count) if pause_count > 0 else 0.0
        longest_pause = max((p.duration_seconds for p in pause_events), default=0.0)

        # ── Speech score (from observable measurements) ───────────────────────
        if word_count == 0:
            # No verbal speech signal measured — return None rather than a fabricated score
            return SpeechMetrics(
                duration_seconds=round(duration_seconds, 1),
                word_count=0,
                words_per_minute=0,
                filler_word_count=0,
                filler_frequency=0.0,
                filler_breakdown={},
                pause_count=pause_count,
                long_pause_count=long_pause_count,
                total_pause_duration=round(total_pause_dur, 2),
                average_pause_duration=round(avg_pause_dur, 2),
                longest_pause_seconds=round(longest_pause, 2),
                pause_events=pause_events[:20],
                has_word_timestamps=has_word_timestamps,
                speaking_rate_category="no_speech",
                delivery_pattern_notes=delivery_notes,
                analysis_warnings=analysis_warnings + (["No speech recognized in audio."] if "No speech recognized in audio." not in analysis_warnings else []),
                analysis_method=analysis_method if analysis_method != "transcript_only" else "unavailable",
                pause_score=None,
                speech_score=None
            )

        # WPM component
        if WPM_MIN <= wpm <= WPM_MAX:
            wpm_score = 95
        elif wpm == 0:
            wpm_score = 0
        elif wpm < WPM_MIN:
            wpm_score = max(40, 95 - int((WPM_MIN - wpm) * 0.8))
        else:
            wpm_score = max(40, 95 - int((wpm - WPM_MAX) * 0.7))

        # Filler component
        filler_freq = fillers["frequency"]
        if filler_freq <= 0.02:
            filler_score = 95
        elif filler_freq <= 0.05:
            filler_score = 82
        elif filler_freq <= 0.08:
            filler_score = 70
        else:
            filler_score = 55

        # Pause component
        pause_score_component: Optional[int] = None
        if has_pause_data:
            if pause_count > 0:
                pause_ratio = long_pause_count / max(1, pause_count)
                if pause_ratio > 0.5:
                    pause_score_component = 65
                    delivery_notes.append(
                        "More than half of detected pauses were longer than 2 seconds. "
                        "This may reflect deeper thinking or hesitation."
                    )
                elif pause_ratio > 0.25:
                    pause_score_component = 80
                else:
                    pause_score_component = 92
            else:
                # Measured without hesitation pauses
                pause_score_component = 95

            # Standard weighted score: 50% WPM, 30% Fillers, 20% Pauses
            overall_speech_score = round(
                (wpm_score * 0.50) + (filler_score * 0.30) + (pause_score_component * 0.20)
            )
        else:
            # When there is NO pause data: pause_score is None, renormalize (WPM 50 / fillers 30 -> 100%)
            pause_score_component = None
            analysis_warnings.append("Pause data could not be measured — pause score excluded.")
            overall_speech_score = round(
                (wpm_score * (50.0 / 80.0)) + (filler_score * (30.0 / 80.0))
            )

        return SpeechMetrics(
            duration_seconds=round(duration_seconds, 1),
            word_count=word_count,
            words_per_minute=wpm,
            filler_word_count=fillers["count"],
            filler_frequency=fillers["frequency"],
            filler_breakdown=fillers["found"],
            pause_count=pause_count,
            long_pause_count=long_pause_count,
            total_pause_duration=round(total_pause_dur, 2),
            average_pause_duration=round(avg_pause_dur, 2),
            longest_pause_seconds=round(longest_pause, 2),
            pause_events=pause_events[:20],
            has_word_timestamps=has_word_timestamps,
            median_inter_word_gap_ms=inter_word_stats.get("median_inter_word_gap_ms"),
            mean_inter_word_gap_ms=inter_word_stats.get("mean_inter_word_gap_ms"),
            long_gap_count=inter_word_stats.get("long_gap_count"),
            longest_gap_ms=inter_word_stats.get("longest_gap_ms"),
            speaking_rate_category=rate_category,
            delivery_pattern_notes=delivery_notes,
            analysis_warnings=analysis_warnings,
            analysis_method=analysis_method,
            pause_score=pause_score_component,
            speech_score=overall_speech_score
        )


speech_service = SpeechService()
