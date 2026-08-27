"""Read a submission folder from Google Drive: video, transcript, PPTs, settings."""
from __future__ import annotations

import io
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload

from submission_workflow.models import DriveFile, Submission

SLIDE_MIME_TYPES = frozenset({
    "application/vnd.google-apps.presentation",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
})
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
TRANSCRIPT_SUFFIXES = (".txt", ".srt", ".vtt")
SETTINGS_FILENAME = "settings.json"
LIST_FIELDS = "files(id, name, mimeType, webViewLink)"


class NoVideoError(RuntimeError):
    """The folder does not contain any video file."""


class DriveClient:
    def __init__(self, service):
        self._service = service

    def find_submission(self, folder_id: str) -> Submission:
        response = self._service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields=LIST_FIELDS,
            pageSize=100,
        ).execute()
        files = [
            DriveFile(
                id=f["id"],
                name=f["name"],
                mime_type=f["mimeType"],
                web_view_link=f.get("webViewLink", ""),
            )
            for f in response.get("files", [])
        ]

        video = next((f for f in files if f.mime_type.startswith("video/")), None)
        if video is None:
            raise NoVideoError(f"No video file found in Drive folder {folder_id}")
        transcript = next((f for f in files if self._is_transcript(f)), None)
        slides = tuple(f for f in files if f.mime_type in SLIDE_MIME_TYPES)
        settings_file = next((f for f in files if f.name == SETTINGS_FILENAME), None)
        return Submission(video=video, transcript=transcript, slides=slides,
                          settings_file=settings_file)

    @staticmethod
    def _is_transcript(f: DriveFile) -> bool:
        if f.name == SETTINGS_FILENAME:
            return False
        return (
            f.mime_type in ("text/plain", GOOGLE_DOC_MIME)
            or f.name.lower().endswith(TRANSCRIPT_SUFFIXES)
        )

    def download_binary(self, file: DriveFile, dest_dir: Path) -> str:
        dest = Path(dest_dir) / file.name
        request = self._service.files().get_media(fileId=file.id)
        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return str(dest)

    def download_text(self, file: DriveFile) -> str:
        if file.mime_type == GOOGLE_DOC_MIME:
            request = self._service.files().export_media(
                fileId=file.id, mimeType="text/plain"
            )
        else:
            request = self._service.files().get_media(fileId=file.id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue().decode("utf-8", errors="replace")
