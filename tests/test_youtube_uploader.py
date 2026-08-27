"""Upload must be private with a scheduled publishAt (docs: publishAt requires private)."""
from unittest.mock import MagicMock, patch

from submission_workflow.youtube.metadata import VideoMetadata
from submission_workflow.youtube.uploader import YouTubeUploader

META = VideoMetadata(title="T", description="D", tags=["a"], category_id="27")


@patch("submission_workflow.youtube.uploader.MediaFileUpload")
def test_upload_builds_scheduled_private_request(mock_media):
    service = MagicMock()
    request = service.videos.return_value.insert.return_value
    request.next_chunk.return_value = (None, {"id": "vid123"})

    video_id = YouTubeUploader(service).upload("/tmp/v.mp4", META, "2026-08-29T12:00:00Z")

    assert video_id == "vid123"
    kwargs = service.videos.return_value.insert.call_args.kwargs
    assert kwargs["part"] == "snippet,status"
    body = kwargs["body"]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-08-29T12:00:00Z"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert body["snippet"] == {"title": "T", "description": "D", "tags": ["a"], "categoryId": "27"}
    mock_media.assert_called_once_with("/tmp/v.mp4", chunksize=-1, resumable=True)


@patch("submission_workflow.youtube.uploader.MediaFileUpload")
def test_upload_loops_until_response(mock_media):
    service = MagicMock()
    request = service.videos.return_value.insert.return_value
    request.next_chunk.side_effect = [(MagicMock(), None), (None, {"id": "vid9"})]
    assert YouTubeUploader(service).upload("/tmp/v.mp4", META, "2026-08-29T12:00:00Z") == "vid9"
    assert request.next_chunk.call_count == 2
