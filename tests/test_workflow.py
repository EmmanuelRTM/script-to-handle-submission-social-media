"""End-to-end orchestration: Drive -> scheduled YouTube upload -> X/LinkedIn pre-posts."""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from submission_workflow.models import DriveFile, Submission
from submission_workflow.workflow import SubmissionWorkflow

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
VIDEO = DriveFile(id="v1", name="My Talk.mp4", mime_type="video/mp4", web_view_link="http://v")
TRANSCRIPT = DriveFile(id="t1", name="transcript.txt", mime_type="text/plain", web_view_link="")
SLIDES = DriveFile(id="p1", name="slides.pptx", mime_type="application/vnd.ms-powerpoint",
                   web_view_link="https://drive.google.com/slides1")


def make_workflow(submission, x_client=None, linkedin_client=None):
    drive = MagicMock()
    drive.find_submission.return_value = submission
    drive.download_binary.return_value = "/tmp/work/My Talk.mp4"
    drive.download_text.side_effect = lambda f: (
        json.dumps({"title": "Custom Title", "tags": ["AI"]})
        if f.name == "settings.json" else "transcript words"
    )
    uploader = MagicMock()
    uploader.upload.return_value = "vid123"
    wf = SubmissionWorkflow(
        drive=drive, uploader=uploader, x_client=x_client, linkedin_client=linkedin_client,
        publish_delay_days=2, category_id="27", x_max_chars=210, now_fn=lambda: NOW,
    )
    return wf, drive, uploader


def test_run_uploads_scheduled_and_builds_pre_posts(tmp_path):
    sub = Submission(video=VIDEO, transcript=TRANSCRIPT, slides=(SLIDES,))
    wf, drive, uploader = make_workflow(sub)

    result = wf.run("folder1", work_dir=tmp_path)

    drive.download_binary.assert_called_once_with(VIDEO, tmp_path)
    _, meta, publish_at = uploader.upload.call_args.args
    assert publish_at == "2026-08-29T12:00:00Z"
    assert meta.title == "My Talk"
    assert "https://drive.google.com/slides1" in meta.description

    assert result.video_id == "vid123"
    assert result.watch_url == "https://www.youtube.com/watch?v=vid123"
    assert result.publish_at == "2026-08-29T12:00:00Z"
    assert result.watch_url in result.x_post
    assert len(result.x_post) <= 210
    assert result.watch_url in result.linkedin_post


def test_settings_json_in_folder_overrides_metadata(tmp_path):
    settings_file = DriveFile(id="s1", name="settings.json", mime_type="application/json",
                              web_view_link="")
    sub = Submission(video=VIDEO, settings_file=settings_file)
    wf, _, uploader = make_workflow(sub)

    result = wf.run("folder1", work_dir=tmp_path)

    _, meta, _ = uploader.upload.call_args.args
    assert meta.title == "Custom Title"
    assert meta.tags == ["AI"]
    assert "#AI" in result.x_post


def test_social_clients_not_called_without_publish_flag(tmp_path):
    x, li = MagicMock(), MagicMock()
    wf, _, _ = make_workflow(Submission(video=VIDEO), x_client=x, linkedin_client=li)
    result = wf.run("folder1", work_dir=tmp_path, publish_social=False)
    x.post.assert_not_called()
    li.post.assert_not_called()
    assert result.x_post_id is None and result.linkedin_post_id is None


def test_publish_social_posts_the_pre_posts(tmp_path):
    x, li = MagicMock(), MagicMock()
    x.post.return_value = "888"
    li.post.return_value = "urn:li:share:9"
    wf, _, _ = make_workflow(Submission(video=VIDEO), x_client=x, linkedin_client=li)

    result = wf.run("folder1", work_dir=tmp_path, publish_social=True)

    x.post.assert_called_once_with(result.x_post)
    li.post.assert_called_once_with(result.linkedin_post)
    assert result.x_post_id == "888"
    assert result.linkedin_post_id == "urn:li:share:9"
