"""Drive folder holds the submission: video + transcript + PPTs (+ optional settings.json)."""
from unittest.mock import MagicMock

import pytest

from submission_workflow.drive.client import DriveClient, NoVideoError


def make_service(files):
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {"files": files}
    return service


FILES = [
    {"id": "1", "name": "talk.mp4", "mimeType": "video/mp4", "webViewLink": "http://v"},
    {"id": "2", "name": "transcript.txt", "mimeType": "text/plain", "webViewLink": "http://t"},
    {"id": "3", "name": "slides.pptx",
     "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
     "webViewLink": "http://p1"},
    {"id": "4", "name": "deck", "mimeType": "application/vnd.google-apps.presentation",
     "webViewLink": "http://p2"},
    {"id": "5", "name": "settings.json", "mimeType": "application/json", "webViewLink": "http://s"},
]


def test_find_submission_classifies_files():
    client = DriveClient(make_service(FILES))
    sub = client.find_submission("folder1")
    assert sub.video.id == "1"
    assert sub.transcript.id == "2"
    assert [s.id for s in sub.slides] == ["3", "4"]
    assert sub.settings_file.id == "5"


def test_find_submission_queries_the_folder():
    service = make_service(FILES)
    DriveClient(service).find_submission("folder1")
    kwargs = service.files.return_value.list.call_args.kwargs
    assert "'folder1' in parents" in kwargs["q"]
    assert "trashed=false" in kwargs["q"]


def test_missing_video_raises():
    client = DriveClient(make_service([FILES[1]]))
    with pytest.raises(NoVideoError):
        client.find_submission("folder1")


def test_transcript_and_settings_optional():
    client = DriveClient(make_service([FILES[0]]))
    sub = client.find_submission("folder1")
    assert sub.transcript is None
    assert sub.settings_file is None
    assert sub.slides == ()


def test_list_submission_folders_queries_subfolders_of_parent():
    from unittest.mock import MagicMock
    from submission_workflow.drive.client import DriveClient
    service = MagicMock()
    service.files().list().execute.return_value = {"files": [
        {"id": "f1", "name": "A"}, {"id": "f2", "name": "B"}]}
    folders = DriveClient(service).list_submission_folders("parent1")
    assert [(f.id, f.name) for f in folders] == [("f1", "A"), ("f2", "B")]
    q = service.files().list.call_args.kwargs["q"]
    assert "'parent1' in parents" in q and "vnd.google-apps.folder" in q and "trashed=false" in q


def test_get_folder_returns_name():
    from unittest.mock import MagicMock
    from submission_workflow.drive.client import DriveClient
    service = MagicMock()
    service.files().get().execute.return_value = {"id": "f1", "name": "Talk"}
    f = DriveClient(service).get_folder("f1")
    assert (f.id, f.name) == ("f1", "Talk")
