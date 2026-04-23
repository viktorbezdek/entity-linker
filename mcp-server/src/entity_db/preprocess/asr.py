"""ASR preprocessor: strip timestamps, speaker labels, and filler tokens."""
import re

_TIMESTAMP_RE = re.compile(r"\[\d{2}:\d{2}(?::\d{2})?\]")
_SPEAKER_LABEL_RE = re.compile(r"^(?:Speaker\s+\d+|[A-Z][a-zA-Z\s]+):\s*", re.MULTILINE)
_FILLER_RE = re.compile(r"\b(um+|uh+|hmm+|er+|ah+)\b", re.IGNORECASE)


def clean_asr(text: str) -> str:
    """Strip ASR timestamps, speaker labels, and filler tokens."""
    text = _TIMESTAMP_RE.sub("", text)
    text = _SPEAKER_LABEL_RE.sub("", text)
    text = _FILLER_RE.sub("", text)
    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)
    return text.strip()
