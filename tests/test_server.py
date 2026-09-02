"""HTTP API for the WebMCP front-end: contract, validation, lazy services."""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from submission_workflow.drive.client import NoVideoError
from submission_workflow.models import DriveFile, DriveFolder, Submission
from submission_workflow.server import Services, create_app
from submission_workflow.social.x_client import XApiError

NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
VIDEO = DriveFile(id="v1", name="talk.mp4", mime_type="video/mp4", web_view_link="http://v")
TRANSCRIPT = DriveFile(id="t1", name="transcript.txt", mime_type="text/plain")
SLIDES = DriveFile(id="p1", name="deck.pptx", mime_type="application/vnd.ms-powerpoint",
                   web_view_link="https://drive.google.com/deck")
SETTINGS = DriveFile(id="s1", name="settings.json", mime_type="application/json")


def make_client(tmp_path, *, x_client=None, linkedin_client=None, parent="parent1", **kw):
    drive = MagicMock()
    drive.list_submission_folders.return_value = [DriveFolder("f1", "2026-09-01 Talk"),
                                                  DriveFolder("f2", "Empty folder")]
    drive.get_folder.return_value = DriveFolder("f1", "2026-09-01 Talk")

    def find(folder_id):
        if folder_id == "f2":
            raise NoVideoError("No video file found in Drive folder f2")
        return Submission(video=VIDEO, transcript=TRANSCRIPT, slides=(SLIDES,), settings_file=SETTINGS)
    drive.find_submission.side_effect = find
    drive.download_text.side_effect = lambda f: (
        json.dumps({"title": "Custom", "tags": ["AI"]}) if f.name == "settings.json" else "words"
    )
    drive.download_binary.side_effect = lambda f, d: str(Path(d) / f.name)
    uploader = MagicMock()
    uploader.upload.return_value = "vid123"
    services = Services(drive=drive, uploader=uploader, x_client=x_client,
                        linkedin_client=linkedin_client, parent_folder_id=parent,
                        work_dir=tmp_path, now_fn=lambda: NOW)
    return TestClient(create_app(services, **kw)), drive, uploader


def test_health_works_without_touching_services(tmp_path):
    client = TestClient(create_app(lambda: (_ for _ in ()).throw(RuntimeError("no creds"))))
    assert client.get("/api/health").json() == {"ok": True, "service": "submission-publisher"}


def test_unconfigured_backend_explains_itself(tmp_path):
    from submission_workflow.server import LazyServices

    def factory():
        raise FileNotFoundError("client_secrets.json")
    client = TestClient(create_app(LazyServices(factory)))
    r = client.get("/api/submissions")
    assert r.status_code == 503
    assert "client_secrets.json" in r.json()["detail"] and "next-steps.html" in r.json()["detail"]


def test_list_submissions_matches_front_end_contract(tmp_path):
    client, _, _ = make_client(tmp_path)
    body = client.get("/api/submissions").json()
    assert body[0] == {
        "id": "f1", "folderName": "2026-09-01 Talk",
        "video": {"id": "v1", "name": "talk.mp4", "mimeType": "video/mp4"},
        "transcript": {"id": "t1", "name": "transcript.txt", "text": "words"},
        "slides": [{"id": "p1", "name": "deck.pptx", "webViewLink": "https://drive.google.com/deck"}],
        "settings": {"title": "Custom", "tags": ["AI"]},
    }
    assert body[1]["video"] is None and "No video" in body[1]["error"]


def test_no_folder_configured_gives_guidance(tmp_path):
    client, _, _ = make_client(tmp_path, parent="")
    r = client.get("/api/submissions")
    assert r.status_code == 500 and "DRIVE_PARENT_FOLDER_ID" in r.json()["detail"]


def test_upload_uses_reviewed_metadata_and_schedules_private(tmp_path):
    client, drive, uploader = make_client(tmp_path)
    r = client.post("/api/submissions/f1/youtube", json={
        "title": "  Reviewed title ", "description": "desc", "tags": ["A", " ", "B"],
        "publishAt": "2026-09-03T12:00:00Z",
    })
    assert r.status_code == 200, r.text
    assert r.json() == {"videoId": "vid123", "watchUrl": "https://www.youtube.com/watch?v=vid123",
                        "publishAt": "2026-09-03T12:00:00Z", "privacyStatus": "private"}
    path, meta, publish_at = uploader.upload.call_args.args
    assert path.endswith("f1/talk.mp4") and publish_at == "2026-09-03T12:00:00Z"
    assert meta.title == "Reviewed title" and meta.tags == ["A", "B"] and meta.category_id == "27"


@pytest.mark.parametrize("publish_at,msg", [
    ("2026-09-01T12:05:00Z", "15 minutes"),
    ("2026-09-03T12:00:00", "timezone"),
    ("soon", "RFC 3339"),
])
def test_upload_rejects_bad_publish_at(tmp_path, publish_at, msg):
    client, _, uploader = make_client(tmp_path)
    r = client.post("/api/submissions/f1/youtube",
                    json={"title": "t", "publishAt": publish_at})
    assert r.status_code == 400 and msg in r.json()["detail"]
    uploader.upload.assert_not_called()


def test_upload_validates_title_length(tmp_path):
    client, _, _ = make_client(tmp_path)
    r = client.post("/api/submissions/f1/youtube",
                    json={"title": "x" * 101, "publishAt": "2026-09-03T12:00:00Z"})
    assert r.status_code == 422


def test_upload_404_when_folder_has_no_video(tmp_path):
    client, _, _ = make_client(tmp_path)
    r = client.post("/api/submissions/f2/youtube",
                    json={"title": "t", "publishAt": "2026-09-03T12:00:00Z"})
    assert r.status_code == 404


def test_social_publishes_only_requested_platforms(tmp_path):
    x, li = MagicMock(), MagicMock()
    x.post.return_value = "888"
    li.post.return_value = "urn:li:share:9"
    client, _, _ = make_client(tmp_path, x_client=x, linkedin_client=li)
    r = client.post("/api/submissions/f1/social", json={"linkedin": "hello"})
    assert r.json() == {"linkedinPostId": "urn:li:share:9"}
    x.post.assert_not_called()
    li.post.assert_called_once_with("hello")


def test_social_503_when_platform_not_configured(tmp_path):
    client, _, _ = make_client(tmp_path)
    r = client.post("/api/submissions/f1/social", json={"x": "hi"})
    assert r.status_code == 503 and "X is not configured" in r.json()["detail"]
    assert client.post("/api/submissions/f1/social", json={}).status_code == 400


def test_social_reports_partial_success_on_api_error(tmp_path):
    x, li = MagicMock(), MagicMock()
    x.post.return_value = "888"
    li.post.side_effect = XApiError("boom")
    client, _, _ = make_client(tmp_path, x_client=x, linkedin_client=li)
    r = client.post("/api/submissions/f1/social", json={"x": "a", "linkedin": "b"})
    assert r.status_code == 502
    assert r.json()["detail"] == {"message": "boom", "published": {"xPostId": "888"}}


def test_origin_trial_header_only_on_html(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    (site / "index.html").write_text("<!doctype html><title>t</title>")
    client, _, _ = make_client(tmp_path, webmcp_dir=str(site), origin_trial_token="TOKEN123")
    assert client.get("/").headers["origin-trial"] == "TOKEN123"
    assert "origin-trial" not in client.get("/api/health").headers


def test_cors_allows_dev_front_end(tmp_path):
    client, _, _ = make_client(tmp_path, cors_origins=["http://localhost:8080"])
    r = client.options("/api/submissions", headers={
        "Origin": "http://localhost:8080", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:8080"
