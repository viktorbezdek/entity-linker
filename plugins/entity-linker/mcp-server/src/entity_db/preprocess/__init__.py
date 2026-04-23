"""Input text preprocessing — source-type detection and type-specific cleaners."""
from entity_db.preprocess.asr import clean_asr
from entity_db.preprocess.detect import detect_source_type
from entity_db.preprocess.email import clean_email
from entity_db.preprocess.html import clean_html
from entity_db.preprocess.markdown import clean_markdown


def clean(text: str, source_type: str) -> str:
    """Dispatch to the appropriate cleaner for the given source_type."""
    match source_type:
        case "email":
            return clean_email(text)
        case "asr":
            return clean_asr(text)
        case "markdown":
            return clean_markdown(text)
        case "html":
            return clean_html(text)
        case _:
            return text  # plain or unknown — pass through


__all__ = ["clean", "detect_source_type"]
