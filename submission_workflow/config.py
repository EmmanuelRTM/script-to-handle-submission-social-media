"""Typed settings loaded from environment variables. No secrets live in code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


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
    folder_id: str


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
    x: XConfig
    linkedin: LinkedInConfig

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        return cls(
            google=GoogleAuthConfig(
                client_secrets_file=_require(env, "GOOGLE_CLIENT_SECRETS_FILE"),
                token_file=_require(env, "GOOGLE_TOKEN_FILE"),
            ),
            drive=DriveConfig(folder_id=_require(env, "DRIVE_FOLDER_ID")),
            youtube=YouTubeConfig(
                category_id=env.get("YOUTUBE_CATEGORY_ID", "27"),
                publish_delay_days=int(env.get("YOUTUBE_PUBLISH_DELAY_DAYS", "2")),
            ),
            x=XConfig(
                api_key=_require(env, "X_API_KEY"),
                api_secret=_require(env, "X_API_SECRET"),
                access_token=_require(env, "X_ACCESS_TOKEN"),
                access_token_secret=_require(env, "X_ACCESS_TOKEN_SECRET"),
                max_post_chars=int(env.get("X_MAX_POST_CHARS", "210")),
            ),
            linkedin=LinkedInConfig(
                access_token=_require(env, "LINKEDIN_ACCESS_TOKEN"),
                author_urn=_require(env, "LINKEDIN_AUTHOR_URN"),
                version=env.get("LINKEDIN_VERSION", "202608"),
            ),
        )
