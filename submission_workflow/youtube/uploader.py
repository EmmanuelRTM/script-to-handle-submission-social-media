"""Resumable upload of a video, private with a scheduled publishAt.

Per the YouTube Data API discovery document, publishAt can only be set while
privacyStatus is "private": the video stays unlisted from the public until the
scheduled time, which is the review window this workflow relies on.
"""
from __future__ import annotations

from googleapiclient.http import MediaFileUpload

from submission_workflow.youtube.metadata import VideoMetadata


class YouTubeUploader:
    def __init__(self, service):
        self._service = service

    def upload(self, video_path: str, metadata: VideoMetadata, publish_at: str) -> str:
        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = self._service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        return response["id"]
