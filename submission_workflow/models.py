"""Domain models shared across the workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    web_view_link: str = ""


@dataclass(frozen=True)
class DriveFolder:
    id: str
    name: str


@dataclass(frozen=True)
class Submission:
    """One Drive folder's contents: the video plus its supporting files."""

    video: DriveFile
    transcript: Optional[DriveFile] = None
    slides: Tuple[DriveFile, ...] = field(default_factory=tuple)
    settings_file: Optional[DriveFile] = None
