"""Create a post on X: POST https://api.x.com/2/tweets (docs.x.com).

Auth is OAuth 1.0a user context; the created post id is at data.id.
"""
from __future__ import annotations

from requests_oauthlib import OAuth1Session

from submission_workflow.config import XConfig

X_POSTS_URL = "https://api.x.com/2/tweets"


class XApiError(RuntimeError):
    """X API returned a non-success response."""


class XClient:
    def __init__(self, config: XConfig | None = None, session=None):
        if session is None:
            if config is None:
                raise ValueError("XClient needs a config or a preconfigured session")
            session = OAuth1Session(
                client_key=config.api_key,
                client_secret=config.api_secret,
                resource_owner_key=config.access_token,
                resource_owner_secret=config.access_token_secret,
            )
        self._session = session

    def post(self, text: str) -> str:
        response = self._session.post(X_POSTS_URL, json={"text": text})
        if response.status_code != 201:
            raise XApiError(
                f"X post failed ({response.status_code}): {response.text}"
            )
        return response.json()["data"]["id"]
