"""Compose the X and LinkedIn pre-post texts from the video metadata."""
from __future__ import annotations

from typing import Sequence

# Reserved characters of LinkedIn's "little text format" — literal use in the
# Posts API commentary field must be backslash-escaped.
LITTLE_TEXT_RESERVED = "\\|{}@[]()<>#*_~"
ELLIPSIS = "…"


def format_hashtags(tags: Sequence[str]) -> str:
    return " ".join("#" + tag.replace(" ", "") for tag in tags if tag)


def escape_little_text(text: str) -> str:
    return "".join("\\" + ch if ch in LITTLE_TEXT_RESERVED else ch for ch in text)


def build_x_post(title: str, url: str, tags: Sequence[str], max_chars: int = 210) -> str:
    hashtags = format_hashtags(tags)
    tail = "\n" + url + ("\n" + hashtags if hashtags else "")
    room = max_chars - len(tail)
    if len(title) > room:
        title = title[: max(room - 1, 0)].rstrip() + ELLIPSIS
    return title + tail


def build_linkedin_post(message: str, url: str, tags: Sequence[str]) -> str:
    parts = [escape_little_text(message), "Watch: " + url]
    hashtags = format_hashtags(tags)
    if hashtags:
        parts.append(hashtags)
    return "\n\n".join(parts)
