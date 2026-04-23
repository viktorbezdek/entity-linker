"""Markdown preprocessor: strip formatting while preserving text content."""
import re

_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_ITALIC_RE = re.compile(r"[*_]{1,3}(.+?)[*_]{1,3}")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


def clean_markdown(text: str) -> str:
    """Strip markdown formatting, preserve text content."""
    text = _CODE_BLOCK_RE.sub("", text)
    text = _HEADING_RE.sub("", text)
    text = _BOLD_ITALIC_RE.sub(r"\1", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text.strip()
