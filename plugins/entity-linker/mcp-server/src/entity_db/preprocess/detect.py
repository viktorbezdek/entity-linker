"""Heuristic source-type detection from text content."""
import re

_EMAIL_RE = re.compile(r"^From:\s+\S+@\S+", re.MULTILINE | re.IGNORECASE)
_ASR_RE = re.compile(r"\[\d{2}:\d{2}:\d{2}\]")
_HTML_RE = re.compile(r"<html[\s>]", re.IGNORECASE)
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)


def detect_source_type(text: str) -> str:
    """Return the most likely source type for the given text.

    Priority: email → asr → html → markdown → plain.
    """
    if _EMAIL_RE.search(text):
        return "email"
    if _ASR_RE.search(text):
        return "asr"
    if _HTML_RE.search(text):
        return "html"
    if _MD_HEADING_RE.search(text):
        return "markdown"
    return "plain"
