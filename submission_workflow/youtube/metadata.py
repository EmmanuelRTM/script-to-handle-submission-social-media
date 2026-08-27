"""Build the video's title, description (incl. PPT links), and tags.

Optional overrides come from a settings.json in the Drive folder:
{"title": ..., "description": ..., "tags": [...], "ppt_urls": [...]}
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import List, Mapping, Optional, Sequence

MAX_TITLE_CHARS = 100
MAX_DESCRIPTION_CHARS = 5000
TRANSCRIPT_EXCERPT_CHARS = 1500


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    description: str
    tags: List[str]
    category_id: str


def build_video_metadata(
    video_name: str,
    settings: Optional[Mapping] = None,
    transcript_text: Optional[str] = None,
    slide_links: Sequence[str] = (),
    category_id: str = "27",
) -> VideoMetadata:
    settings = settings or {}
    title = (settings.get("title") or PurePosixPath(video_name).stem)[:MAX_TITLE_CHARS]

    parts: List[str] = []
    if settings.get("description"):
        parts.append(str(settings["description"]))
    elif transcript_text:
        parts.append(transcript_text[:TRANSCRIPT_EXCERPT_CHARS].rstrip())

    ppt_urls = list(settings.get("ppt_urls", [])) + [u for u in slide_links if u]
    if ppt_urls:
        parts.append("Slides:\n" + "\n".join(f"- {url}" for url in ppt_urls))

    description = "\n\n".join(parts)[:MAX_DESCRIPTION_CHARS]
    tags = [str(t) for t in settings.get("tags", [])]
    return VideoMetadata(title=title, description=description, tags=tags, category_id=category_id)
