"""Pre-posts for X (~210 chars, tags, YouTube link) and LinkedIn (message, tags, link)."""
from submission_workflow.social.post_builder import (
    build_linkedin_post,
    build_x_post,
    escape_little_text,
    format_hashtags,
)

URL = "https://www.youtube.com/watch?v=abc123"


def test_hashtags_formatting_strips_spaces():
    assert format_hashtags(["AI", "cloud computing"]) == "#AI #cloudcomputing"


def test_x_post_contains_title_url_and_tags():
    text = build_x_post("New video is live", URL, ["AI"], max_chars=210)
    assert URL in text
    assert "#AI" in text
    assert "New video is live" in text


def test_x_post_respects_max_chars_by_truncating_title():
    text = build_x_post("t" * 500, URL, ["AI", "Cloud"], max_chars=210)
    assert len(text) <= 210
    assert URL in text  # the link must survive truncation
    assert "…" in text


def test_linkedin_post_contains_message_link_and_tags():
    text = build_linkedin_post("Watch my new talk", URL, ["AI", "DevOps"])
    assert "Watch my new talk" in text
    assert URL in text
    assert "#AI" in text and "#DevOps" in text


def test_linkedin_message_is_escaped_for_little_text_format():
    assert escape_little_text("(parens) {braces} #hash") == r"\(parens\) \{braces\} \#hash"
    text = build_linkedin_post("Q&A (part 1)", URL, [])
    assert r"\(part 1\)" in text
