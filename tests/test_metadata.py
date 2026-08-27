"""Video metadata: title, description (with PPT urls), tags — per whiteboard settings."""
from submission_workflow.youtube.metadata import (
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
    build_video_metadata,
)


def test_title_falls_back_to_video_filename_stem():
    meta = build_video_metadata(video_name="My Great Talk.mp4")
    assert meta.title == "My Great Talk"


def test_settings_override_title_tags_description():
    settings = {"title": "Custom Title", "tags": ["AI", "Cloud"], "description": "Custom desc"}
    meta = build_video_metadata(video_name="v.mp4", settings=settings)
    assert meta.title == "Custom Title"
    assert meta.tags == ["AI", "Cloud"]
    assert meta.description.startswith("Custom desc")


def test_description_includes_ppt_urls():
    meta = build_video_metadata(
        video_name="v.mp4",
        slide_links=["https://drive.google.com/ppt1", "https://drive.google.com/ppt2"],
    )
    assert "https://drive.google.com/ppt1" in meta.description
    assert "https://drive.google.com/ppt2" in meta.description


def test_description_falls_back_to_transcript_excerpt():
    meta = build_video_metadata(video_name="v.mp4", transcript_text="word " * 5000)
    assert len(meta.description) <= MAX_DESCRIPTION_CHARS


def test_title_truncated_to_youtube_limit():
    meta = build_video_metadata(video_name="x" * 300 + ".mp4")
    assert len(meta.title) <= MAX_TITLE_CHARS
