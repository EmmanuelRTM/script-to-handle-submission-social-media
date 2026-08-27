"""Create a post on LinkedIn via the versioned Posts API.

Per learn.microsoft.com/linkedin (Posts API): POST https://api.linkedin.com/rest/posts
with LinkedIn-Version (YYYYMM) and X-Restli-Protocol-Version: 2.0.0 headers.
A 201 response carries the post id in the x-restli-id header.
"""
from __future__ import annotations

import requests

from submission_workflow.config import LinkedInConfig

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"


class LinkedInApiError(RuntimeError):
    """LinkedIn API returned a non-success response."""


class LinkedInClient:
    def __init__(self, config: LinkedInConfig, session=None):
        self._config = config
        self._session = session or requests.Session()

    def post(self, commentary: str) -> str:
        response = self._session.post(
            LINKEDIN_POSTS_URL,
            headers={
                "Authorization": f"Bearer {self._config.access_token}",
                "LinkedIn-Version": self._config.version,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            json={
                "author": self._config.author_urn,
                "commentary": commentary,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
        )
        if response.status_code != 201:
            raise LinkedInApiError(
                f"LinkedIn post failed ({response.status_code}): {response.text}"
            )
        return response.headers["x-restli-id"]
