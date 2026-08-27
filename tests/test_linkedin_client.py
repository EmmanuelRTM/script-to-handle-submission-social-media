"""LinkedIn: POST /rest/posts with versioned headers; post id in x-restli-id header."""
from unittest.mock import MagicMock

import pytest

from submission_workflow.config import LinkedInConfig
from submission_workflow.social.linkedin_client import (
    LINKEDIN_POSTS_URL,
    LinkedInApiError,
    LinkedInClient,
)

CONFIG = LinkedInConfig(access_token="tok", author_urn="urn:li:person:abc", version="202608")


def make_session(status=201):
    session = MagicMock()
    response = MagicMock()
    response.status_code = status
    response.headers = {"x-restli-id": "urn:li:share:42"}
    response.text = "li-err"
    session.post.return_value = response
    return session


def test_post_sends_documented_body_and_headers():
    session = make_session()
    post_id = LinkedInClient(CONFIG, session=session).post("my commentary")
    assert post_id == "urn:li:share:42"

    args, kwargs = session.post.call_args
    assert args[0] == LINKEDIN_POSTS_URL
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok"
    assert headers["LinkedIn-Version"] == "202608"
    assert headers["X-Restli-Protocol-Version"] == "2.0.0"
    body = kwargs["json"]
    assert body["author"] == "urn:li:person:abc"
    assert body["commentary"] == "my commentary"
    assert body["visibility"] == "PUBLIC"
    assert body["lifecycleState"] == "PUBLISHED"
    assert body["distribution"]["feedDistribution"] == "MAIN_FEED"
    assert body["isReshareDisabledByAuthor"] is False


def test_non_201_raises_with_body():
    with pytest.raises(LinkedInApiError, match="li-err"):
        LinkedInClient(CONFIG, session=make_session(status=422)).post("x")
