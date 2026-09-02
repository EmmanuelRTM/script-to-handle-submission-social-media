"""Typed settings loaded from environment variables. No secrets live in code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, TypeVar

T = TypeVar("T")


class MissingConfigError(RuntimeError):
    """A required environment variable is absent or empty."""


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise MissingConfigError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class GoogleAuthConfig:
    client_secrets_file: str
    token_file: str


@dataclass(frozen=True)
class DriveConfig:
    folder_id: str = ""
    parent_folder_id: str = ""  # server mode: every subfolder is one submission


@dataclass(frozen=True)
class YouTubeConfig:
    category_id: str = "27"
    publish_delay_days: int = 2


@dataclass(frozen=True)
class XConfig:
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    max_post_chars: int = 210


@dataclass(frozen=True)
class LinkedInConfig:
    access_token: str
    author_urn: str
    version: str = "202608"


@dataclass(frozen=True)
class Settings:
    google: GoogleAuthConfig
    drive: DriveConfig
    youtube: YouTubeConfig
    x: Optional[XConfig]
    linkedin: Optional[LinkedInConfig]

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, require_social: bool = True
    ) -> "Settings":
        """Load settings. The CLI requires everything; the HTTP server
        (require_social=False) can run upload-only and accepts either
        DRIVE_FOLDER_ID (one submission) or DRIVE_PARENT_FOLDER_ID (one per subfolder)."""
        env = os.environ if env is None else env
        parent_folder_id = env.get("DRIVE_PARENT_FOLDER_ID", "").strip()
        folder_id = env.get("DRIVE_FOLDER_ID", "").strip()
        if not folder_id and not (parent_folder_id and not require_social):
            folder_id = _require(env, "DRIVE_FOLDER_ID")
        return cls(
            google=GoogleAuthConfig(
                client_secrets_file=_require(env, "GOOGLE_CLIENT_SECRETS_FILE"),
                token_file=_require(env, "GOOGLE_TOKEN_FILE"),
            ),
            drive=DriveConfig(folder_id=folder_id, parent_folder_id=parent_folder_id),
            youtube=YouTubeConfig(
                category_id=env.get("YOUTUBE_CATEGORY_ID", "27"),
                publish_delay_days=int(env.get("YOUTUBE_PUBLISH_DELAY_DAYS", "2")),
            ),
            x=_optional(require_social, lambda: XConfig(
                api_key=_require(env, "X_API_KEY"),
                api_secret=_require(env, "X_API_SECRET"),
                access_token=_require(env, "X_ACCESS_TOKEN"),
                access_token_secret=_require(env, "X_ACCESS_TOKEN_SECRET"),
                max_post_chars=int(env.get("X_MAX_POST_CHARS", "210")),
            )),
            linkedin=_optional(require_social, lambda: LinkedInConfig(
                access_token=_require(env, "LINKEDIN_ACCESS_TOKEN"),
                author_urn=_require(env, "LINKEDIN_AUTHOR_URN"),
                version=env.get("LINKEDIN_VERSION", "202608"),
            )),
        )


def _optional(required: bool, build: Callable[[], T]) -> Optional[T]:
    """Build a config block; when not required, a missing variable yields None."""
    try:
        return build()
    except MissingConfigError:
        if required:
            raise
        return None
