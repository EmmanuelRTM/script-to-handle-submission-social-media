"""Scheduled launch time: private upload that goes public N days later (RFC3339)."""
from datetime import datetime, timezone

from submission_workflow.youtube.schedule import compute_publish_at


def test_publish_at_is_two_days_out_rfc3339():
    now = datetime(2026, 8, 27, 12, 30, 0, tzinfo=timezone.utc)
    assert compute_publish_at(now, days=2) == "2026-08-29T12:30:00Z"


def test_naive_datetime_treated_as_utc():
    now = datetime(2026, 1, 1, 0, 0, 0)
    assert compute_publish_at(now, days=2) == "2026-01-03T00:00:00Z"


def test_custom_delay():
    now = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
    assert compute_publish_at(now, days=7) == "2026-09-03T12:00:00Z"
