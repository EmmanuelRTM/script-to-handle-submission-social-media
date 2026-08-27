"""Orchestrates: Drive submission -> scheduled YouTube upload -> social pre-posts.

Collaborators are injected (drive client, uploader, social clients) so each can
be tested and replaced independently.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from submission_workflow.social.post_builder import build_linkedin_post, build_x_post
from submission_workflow.youtube.metadata import build_video_metadata
from submission_workflow.youtube.schedule import compute_publish_at

WATCH_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class WorkflowResult:
    video_id: str
    watch_url: str
    publish_at: str
    x_post: str
    linkedin_post: str
    x_post_id: Optional[str] = None
    linkedin_post_id: Optional[str] = None


class SubmissionWorkflow:
    def __init__(
        self,
        drive,
        uploader,
        x_client=None,
        linkedin_client=None,
        *,
        publish_delay_days: int = 2,
        category_id: str = "27",
        x_max_chars: int = 210,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._drive = drive
        self._uploader = uploader
        self._x_client = x_client
        self._linkedin_client = linkedin_client
        self._publish_delay_days = publish_delay_days
        self._category_id = category_id
        self._x_max_chars = x_max_chars
        self._now_fn = now_fn

    def run(self, folder_id: str, work_dir: Path, publish_social: bool = False) -> WorkflowResult:
        submission = self._drive.find_submission(folder_id)
        video_path = self._drive.download_binary(submission.video, work_dir)

        transcript_text = (
            self._drive.download_text(submission.transcript) if submission.transcript else None
        )
        settings = (
            json.loads(self._drive.download_text(submission.settings_file))
            if submission.settings_file else None
        )
        metadata = build_video_metadata(
            video_name=submission.video.name,
            settings=settings,
            transcript_text=transcript_text,
            slide_links=[s.web_view_link for s in submission.slides],
            category_id=self._category_id,
        )

        publish_at = compute_publish_at(self._now_fn(), days=self._publish_delay_days)
        video_id = self._uploader.upload(video_path, metadata, publish_at)
        watch_url = WATCH_URL_TEMPLATE.format(video_id=video_id)

        x_post = build_x_post(metadata.title, watch_url, metadata.tags, self._x_max_chars)
        linkedin_post = build_linkedin_post(metadata.title, watch_url, metadata.tags)

        x_post_id = linkedin_post_id = None
        if publish_social:
            if self._x_client:
                x_post_id = self._x_client.post(x_post)
            if self._linkedin_client:
                linkedin_post_id = self._linkedin_client.post(linkedin_post)

        return WorkflowResult(
            video_id=video_id,
            watch_url=watch_url,
            publish_at=publish_at,
            x_post=x_post,
            linkedin_post=linkedin_post,
            x_post_id=x_post_id,
            linkedin_post_id=linkedin_post_id,
        )
