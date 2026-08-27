"""Compute the scheduled launch time for a private upload.

YouTube Data API: status.publishAt is RFC3339 and may only be set while
status.privacyStatus is "private" (youtube.v3 discovery document).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def compute_publish_at(now: datetime, days: int = 2) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    publish_at = now.astimezone(timezone.utc) + timedelta(days=days)
    return publish_at.strftime("%Y-%m-%dT%H:%M:%SZ")
