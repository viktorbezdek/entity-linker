"""Email preprocessor: strip headers, signatures, and quoted replies."""
import re

_HEADER_RE = re.compile(
    r"^(From|To|Cc|Bcc|Subject|Date|Reply-To|Message-ID|MIME-Version|Content-Type"
    r"|In-Reply-To|References):.*$\n?",
    re.MULTILINE | re.IGNORECASE,
)
_SIGNATURE_RE = re.compile(r"\n-- \n.*", re.DOTALL)
_QUOTED_REPLY_RE = re.compile(r"^>.*$\n?", re.MULTILINE)
_ON_DATE_WROTE_RE = re.compile(
    r"On .+wrote:\s*$.*",
    re.DOTALL | re.MULTILINE,
)


def clean_email(text: str) -> str:
    """Strip email headers (a), signatures (b), and quoted replies (c)."""
    # (a) Strip header block at top
    text = _HEADER_RE.sub("", text)

    # (b) Strip RFC 3676 signature block (double newline + "-- ")
    text = _SIGNATURE_RE.sub("", text)

    # (c) Strip quoted-reply lines starting with ">"
    text = _QUOTED_REPLY_RE.sub("", text)

    # (c) Strip "On DATE, NAME wrote:" blocks
    text = _ON_DATE_WROTE_RE.sub("", text)

    return text.strip()
