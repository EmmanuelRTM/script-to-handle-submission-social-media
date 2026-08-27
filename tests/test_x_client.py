"""X: POST https://api.x.com/2/tweets with {"text": ...}; id returned at data.id."""
from unittest.mock import MagicMock

import pytest

from submission_workflow.social.x_client import X_POSTS_URL, XApiError, XClient


def make_session(status=201, payload=None):
    session = MagicMock()
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload or {"data": {"id": "111"}}
    response.text = "err-body"
    session.post.return_value = response
    return session


def test_post_sends_text_to_official_endpoint():
    session = make_session()
    post_id = XClient(session=session).post("hello world")
    assert post_id == "111"
    session.post.assert_called_once_with(X_POSTS_URL, json={"text": "hello world"})


def test_non_201_raises_with_body():
    with pytest.raises(XApiError, match="err-body"):
        XClient(session=make_session(status=403)).post("hello")
