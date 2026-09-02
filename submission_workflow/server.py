"""HTTP API + static host for the Submission Publisher WebMCP front-end.

Run:  uvicorn submission_workflow.server:app --port 8000
Then open http://localhost:8000/submission-publisher/ (when WEBMCP_DIR is set).

Endpoints (contract shared with webmcps/submission-publisher/adapters.js):
  GET  /api/health
  GET  /api/submissions
  POST /api/submissions/{folder_id}/youtube   {title, description, tags, publishAt}
  POST /api/submissions/{folder_id}/social    {x?, linkedin?}

Why one server: WebMCP tools are only visible to the page's own origin, and a Chrome
origin-trial token is bound to an origin, so the page and its API are served
together. If ORIGIN_TRIAL_TOKEN is set it is sent as the `Origin-Trial` response
header on HTML (developer.chrome.com/docs/web-platform/origin-trials).

Real Google/X/LinkedIn clients are built lazily on the first API call so the
server starts (and serves the page) before OAuth has been completed.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from submission_workflow.drive.client import NoVideoError
from submission_workflow.models import DriveFolder
from submission_workflow.social.linkedin_client import LinkedInApiError
from submission_workflow.social.x_client import XApiError
from submission_workflow.workflow import WATCH_URL_TEMPLATE
from submission_workflow.youtube.metadata import (
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
    VideoMetadata,
)

MIN_LEAD_TIME = timedelta(minutes=15)


# ---------------------------------------------------------------- services --
@dataclass
class Services:
    """The collaborators the API needs; injected so tests can pass mocks."""

    drive: object
    uploader: object
    x_client: object = None
    linkedin_client: object = None
    folder_id: str = ""
    parent_folder_id: str = ""
    category_id: str = "27"
    work_dir: Path = Path("out")
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


class LazyServices:
    """Build the real Services on first use (OAuth happens then, not at import)."""

    def __init__(self, factory: Callable[[], Services]):
        self._factory = factory
        self._services: Optional[Services] = None
        self._lock = threading.Lock()

    def get(self) -> Services:
        with self._lock:
            if self._services is None:
                try:
                    self._services = self._factory()
                except Exception as err:  # missing .env values, client_secrets.json, OAuth refusal…
                    raise HTTPException(
                        503, f"Backend not configured: {err}. See submission-publisher/next-steps.html"
                    ) from err
            return self._services


def build_services_from_env() -> Services:
    from googleapiclient.discovery import build

    from submission_workflow.config import Settings
    from submission_workflow.drive.client import DriveClient
    from submission_workflow.google_auth import get_credentials
    from submission_workflow.social.linkedin_client import LinkedInClient
    from submission_workflow.social.x_client import XClient
    from submission_workflow.youtube.uploader import YouTubeUploader

    settings = Settings.from_env(require_social=False)
    creds = get_credentials(settings.google.client_secrets_file, settings.google.token_file)
    return Services(
        drive=DriveClient(build("drive", "v3", credentials=creds)),
        uploader=YouTubeUploader(build("youtube", "v3", credentials=creds)),
        x_client=XClient(settings.x) if settings.x else None,
        linkedin_client=LinkedInClient(settings.linkedin) if settings.linkedin else None,
        folder_id=settings.drive.folder_id,
        parent_folder_id=settings.drive.parent_folder_id,
        category_id=settings.youtube.category_id,
        work_dir=Path(os.environ.get("WORK_DIR", "out")),
    )


# ------------------------------------------------------------- request bodies --
class YouTubeUploadBody(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARS)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_CHARS)
    tags: list[str] = Field(default_factory=list)
    publishAt: str = Field(description="RFC 3339 UTC, e.g. 2026-09-04T14:00:00Z")


class SocialBody(BaseModel):
    x: Optional[str] = None
    linkedin: Optional[str] = None


def parse_publish_at(value: str, now: datetime) -> str:
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise HTTPException(400, f"publishAt must be RFC 3339, got {value!r}") from err
    if when.tzinfo is None:
        raise HTTPException(400, "publishAt must include a timezone (use Z for UTC)")
    when = when.astimezone(timezone.utc)
    if when < now + MIN_LEAD_TIME:
        raise HTTPException(400, "publishAt must be at least 15 minutes in the future")
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------- app --
def create_app(
    services: Services | LazyServices | None = None,
    *,
    webmcp_dir: str | None = None,
    origin_trial_token: str | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    lazy = services if isinstance(services, LazyServices) else LazyServices(
        (lambda: services) if services is not None else build_services_from_env
    )
    app = FastAPI(title="Submission Publisher API", version="1.0")

    if cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=cors_origins,
            allow_methods=["GET", "POST"], allow_headers=["content-type"],
        )

    if origin_trial_token:
        @app.middleware("http")
        async def add_origin_trial_header(request: Request, call_next):
            response = await call_next(request)
            if response.headers.get("content-type", "").startswith("text/html"):
                response.headers["Origin-Trial"] = origin_trial_token
            return response

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "submission-publisher"}

    @app.get("/api/submissions")
    def list_submissions():
        s = lazy.get()
        if s.parent_folder_id:
            folders = s.drive.list_submission_folders(s.parent_folder_id)
        elif s.folder_id:
            folders = [s.drive.get_folder(s.folder_id)]
        else:
            raise HTTPException(500, "Set DRIVE_PARENT_FOLDER_ID or DRIVE_FOLDER_ID")
        return [_describe(s, f) for f in folders]

    @app.post("/api/submissions/{folder_id}/youtube")
    def upload_to_youtube(folder_id: str, body: YouTubeUploadBody):
        s = lazy.get()
        publish_at = parse_publish_at(body.publishAt, s.now_fn())
        try:
            submission = s.drive.find_submission(folder_id)
        except NoVideoError as err:
            raise HTTPException(404, str(err)) from err
        work_dir = s.work_dir / folder_id
        work_dir.mkdir(parents=True, exist_ok=True)
        video_path = s.drive.download_binary(submission.video, work_dir)
        metadata = VideoMetadata(
            title=body.title.strip(), description=body.description,
            tags=[t.strip() for t in body.tags if t.strip()], category_id=s.category_id,
        )
        video_id = s.uploader.upload(video_path, metadata, publish_at)
        return {
            "videoId": video_id,
            "watchUrl": WATCH_URL_TEMPLATE.format(video_id=video_id),
            "publishAt": publish_at,
            "privacyStatus": "private",
        }

    @app.post("/api/submissions/{folder_id}/social")
    def publish_social(folder_id: str, body: SocialBody):
        s = lazy.get()
        if not body.x and not body.linkedin:
            raise HTTPException(400, "Provide x and/or linkedin text")
        if body.x and s.x_client is None:
            raise HTTPException(503, "X is not configured (X_API_KEY … in .env)")
        if body.linkedin and s.linkedin_client is None:
            raise HTTPException(503, "LinkedIn is not configured (LINKEDIN_ACCESS_TOKEN … in .env)")
        result: dict[str, str] = {}
        try:
            if body.x:
                result["xPostId"] = s.x_client.post(body.x)
            if body.linkedin:
                result["linkedinPostId"] = s.linkedin_client.post(body.linkedin)
        except (XApiError, LinkedInApiError) as err:
            # Partial success is reported so the page can show what did go out.
            raise HTTPException(502, detail={"message": str(err), "published": result}) from err
        return result

    if webmcp_dir:
        app.mount("/", StaticFiles(directory=webmcp_dir, html=True), name="webmcp")
    return app


def _describe(s: Services, folder: DriveFolder) -> dict:
    """Shape consumed by webmcps/submission-publisher (adapters.js)."""
    try:
        sub = s.drive.find_submission(folder.id)
    except NoVideoError:
        return {"id": folder.id, "folderName": folder.name, "video": None, "transcript": None,
                "slides": [], "settings": None, "error": "No video file in this folder"}
    transcript = None
    if sub.transcript:
        transcript = {"id": sub.transcript.id, "name": sub.transcript.name,
                      "text": s.drive.download_text(sub.transcript)}
    settings = None
    if sub.settings_file:
        try:
            settings = json.loads(s.drive.download_text(sub.settings_file))
        except json.JSONDecodeError:
            settings = None
    return {
        "id": folder.id,
        "folderName": folder.name,
        "video": {"id": sub.video.id, "name": sub.video.name, "mimeType": sub.video.mime_type},
        "transcript": transcript,
        "slides": [{"id": f.id, "name": f.name, "webViewLink": f.web_view_link} for f in sub.slides],
        "settings": settings,
    }


def _from_env() -> FastAPI:
    cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:8080").split(",") if o.strip()]
    return create_app(
        webmcp_dir=os.environ.get("WEBMCP_DIR") or None,
        origin_trial_token=os.environ.get("ORIGIN_TRIAL_TOKEN") or None,
        cors_origins=cors,
    )


app = _from_env()
