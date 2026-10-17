"""
answer_quality.py — Classifies candidate answer transcripts into:
- "no_speech": empty, filler-only, or echo of the Whisper disfluency prompt.
- "non_answer": deflection, admitting ignorance, or evasive 1-3 word answers.
- "answered": substantive answers (including short technical answers).
"""

import re
import difflib
from typing import Set

# Shared constant for Whisper disfluency prompt (used in speech_service.transcribe_audio)
WHISPER_DISFLUENCY_PROMPT: str = "Umm, uh, hmm, like, you know, I mean, so, basically..."

# Multi-word fillers
MULTI_WORD_FILLERS = ["you know", "i mean"]

# Filler words set
FILLER_WORDS: Set[str] = {
    "um", "uh", "umm", "hmm", "mm", "mmm", "ah", "er", "erm",
    "like", "okay", "ok", "so", "well", "yeah"
}

# Pure acoustic disfluency sounds
ACOUSTIC_FILLERS: Set[str] = {
    "um", "uh", "umm", "hmm", "mm", "mmm", "ah", "er", "erm"
}

# Non-answer exact strings
NON_ANSWER_EXACT: Set[str] = {
    "yes", "no", "ok", "okay", "sure", "maybe", "nothing", "pass", "skip",
    "next", "next question", "idk", "i dont know", "i do not know",
    "not sure", "no idea"
}

# Single words that form non-answers when text is at most 3 words, all from this set
NON_ANSWER_WORDS: Set[str] = {
    "yes", "no", "ok", "okay", "sure", "maybe", "nothing", "pass", "skip",
    "next", "idk"
}

# Regex patterns for admitting ignorance or deflecting
NON_ANSWER_PATTERNS = [
    re.compile(r"sorry,?\s+i\s+(?:don'?t|do\s+not)\s+know", re.IGNORECASE),
    re.compile(r"(?:i'?m|i\s+am)\s+(?:a\s+bit\s+)?new\s+to", re.IGNORECASE),
    re.compile(r"(?:can|could)\s+you\s+(?:give|ask)\s+me\s+(?:any\s+)?(?:another|different|simpler|easier|something|anything)", re.IGNORECASE),
    re.compile(r"(?:can\s+you\s+)?give\s+me\s+.*?\b(?:question|questions)\b\s+(?:on|about|related\s+to)", re.IGNORECASE),
    re.compile(r"ask\s+me\s+(?:something|anything)", re.IGNORECASE),
    re.compile(r"(?:no,?\s+)?i\s+(?:can(?:'?t|not)|am\s+unable\s+to|'m\s+unable\s+to|could\s+not|couldn'?t)\s+(?:explain|answer|do|write|say|describe)(?:\s+(?:the|this|that|it|code|question|answer|problem|concept|topic))?", re.IGNORECASE),
    re.compile(r"i\s+(?:have|had)\s+no\s+idea", re.IGNORECASE),
    re.compile(r"no,?\s+i\s+(?:can(?:'?t|not)|don'?t)", re.IGNORECASE),
]


def normalize_transcript(transcript: str) -> str:
    """Normalize: lowercase, remove punctuation and the characters . … , ? !"""
    if not transcript:
        return ""
    text = transcript.lower()
    # Replace punctuation characters with space, preserving internal apostrophes
    text = re.sub(r"[.…,?!]", " ", text)
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"(?<!\w)'|'(?!\w)", " ", text)
    return " ".join(text.split())


def classify_answer(transcript: str) -> str:
    """
    Classify transcript into 'no_speech', 'non_answer', or 'answered'.

    - 'no_speech': empty after normalizing; or only fillers/stop words remain;
      or transcript is an echo of the Whisper disfluency prompt (ratio > 0.8).
    - 'non_answer': at most 3 words all from non-answer set; or matches ignorance/deflection regexes
      covering at least 60% of the words of the answer (statement ends the thought).
    - 'answered': substantive answers (including short technical answers).
    """
    if not transcript:
        return "no_speech"

    normalized = normalize_transcript(transcript)
    if not normalized:
        return "no_speech"

    # Echo of Whisper disfluency prompt check (difflib SequenceMatcher ratio > 0.8)
    norm_prompt = normalize_transcript(WHISPER_DISFLUENCY_PROMPT)
    ratio_norm = difflib.SequenceMatcher(None, normalized, norm_prompt).ratio()
    ratio_raw = difflib.SequenceMatcher(None, transcript.strip().lower(), WHISPER_DISFLUENCY_PROMPT.lower()).ratio()
    if max(ratio_norm, ratio_raw) > 0.8:
        return "no_speech"

    # Check if only fillers remain
    remainder = normalized
    for mwf in MULTI_WORD_FILLERS:
        remainder = re.sub(r"\b" + re.escape(mwf) + r"\b", " ", remainder)
    words = remainder.split()

    if words and all(w in ACOUSTIC_FILLERS for w in words):
        return "no_speech"

    if not words:
        return "no_speech"

    all_words = normalized.split()
    total_words = len(all_words)

    # Check non-answer exact phrases
    if normalized in NON_ANSWER_EXACT:
        return "non_answer"

    # At most 3 words, all from NON_ANSWER_WORDS
    if total_words <= 3 and all(w in NON_ANSWER_WORDS for w in all_words):
        return "non_answer"

    # Ignorance / deflection regexes
    for pattern in NON_ANSWER_PATTERNS:
        match = pattern.search(normalized)
        if match:
            if total_words <= 3:
                return "non_answer"
            # Require pattern to cover at least 60% of words of the answer (statement ends the thought)
            words_after = len(normalized[match.end():].split())
            coverage = (total_words - words_after) / total_words
            if coverage >= 0.60:
                return "non_answer"

    return "answered"
