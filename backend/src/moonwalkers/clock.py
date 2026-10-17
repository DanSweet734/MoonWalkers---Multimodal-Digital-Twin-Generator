"""Time helpers. Components take a ``clock`` argument so tests can fix the time."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The current time, timezone-aware, in UTC."""
    return datetime.now(UTC)
