"""Tests for preprocess module — clean() dispatch and detect_source_type()."""
from entity_db.preprocess import clean, detect_source_type

# ── detect_source_type ────────────────────────────────────────────────────────


def test_detect_email() -> None:
    text = "From: alice@example.com\nTo: bob@example.com\nSubject: Meeting\n\nHello"
    assert detect_source_type(text) == "email"


def test_detect_asr() -> None:
    text = "[00:00:05] Speaker 1: Hello everyone\n[00:00:10] Speaker 2: Hi"
    assert detect_source_type(text) == "asr"


def test_detect_html() -> None:
    text = "<html><body><p>Hello world</p></body></html>"
    assert detect_source_type(text) == "html"


def test_detect_markdown() -> None:
    text = "# Meeting Notes\n\n## Attendees\n\n- Viktor\n- Tomas"
    assert detect_source_type(text) == "markdown"


def test_detect_plain_fallback() -> None:
    text = "Just some plain text with no special markers."
    assert detect_source_type(text) == "plain"


# ── clean dispatch ────────────────────────────────────────────────────────────


def test_clean_email_strips_headers() -> None:
    text = "From: alice@example.com\nTo: bob@example.com\nSubject: Test\n\nHello Stefan"
    result = clean(text, "email")
    assert "From:" not in result
    assert "Stefan" in result


def test_clean_email_strips_signature() -> None:
    text = "Let's meet\n\n-- \nStefan Weber\nGroupon"
    result = clean(text, "email")
    assert "Stefan Weber" not in result
    assert "Let's meet" in result


def test_clean_email_strips_quoted_reply() -> None:
    text = "Sure, let's do it.\n\n> On Mon, Alice wrote:\n> Hi there"
    result = clean(text, "email")
    assert "> " not in result
    assert "Sure" in result


def test_clean_asr_strips_timestamps() -> None:
    text = "[00:00:05] Hello everyone [00:01:00] How are you"
    result = clean(text, "asr")
    assert "[00:" not in result
    assert "Hello" in result


def test_clean_markdown_strips_headings() -> None:
    text = "# Title\n\nSome content here"
    result = clean(text, "markdown")
    assert "# " not in result
    assert "content" in result


def test_clean_html_extracts_text() -> None:
    text = "<html><body><p>Hello <b>Stefan</b></p></body></html>"
    result = clean(text, "html")
    assert "<" not in result
    assert "Stefan" in result


def test_clean_plain_passthrough() -> None:
    text = "Hello Viktor, how are you?"
    result = clean(text, "plain")
    assert result == text


def test_clean_unknown_type_passthrough() -> None:
    text = "Some text"
    result = clean(text, "unknown_type")
    assert result == text
