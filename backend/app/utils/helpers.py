import re
from typing import List, Dict, Any

def calculate_wpm(word_count: int, duration_seconds: float) -> int:
    """Calculate words per minute (WPM)."""
    if duration_seconds <= 0:
        return 0
    minutes = duration_seconds / 60.0
    return round(word_count / minutes)

def detect_filler_words(text: str, filler_list: List[str]) -> Dict[str, Any]:
    """Detect filler word count and frequency in text."""
    if not text:
        return {"count": 0, "frequency": 0.0, "found": {}}

    lower_text = text.lower()
    total_words = len(re.findall(r'\b[\w\']+\b', lower_text))
    if total_words == 0:
        return {"count": 0, "frequency": 0.0, "found": {}}

    found = {}
    total_fillers = 0

    for filler in filler_list:
        pattern = r'\b' + re.escape(filler.lower()) + r'\b'
        matches = len(re.findall(pattern, lower_text))
        if matches > 0:
            found[filler] = matches
            total_fillers += matches

    freq = round(total_fillers / total_words, 3)
    return {
        "count": total_fillers,
        "frequency": freq,
        "found": found
    }
