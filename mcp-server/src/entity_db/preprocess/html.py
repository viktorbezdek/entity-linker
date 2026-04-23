"""HTML preprocessor: extract visible text content."""
import re

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ENTITY_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;")


def clean_html(text: str) -> str:
    """Strip HTML tags and extract plain text."""
    text = _SCRIPT_STYLE_RE.sub("", text)
    text = _TAG_RE.sub(" ", text)
    text = _ENTITY_RE.sub(" ", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()
