from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# US Eastern timezone
ET = ZoneInfo("US/Eastern")
UTC = timezone.utc


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an ISO date string to a timezone-aware datetime.

    Handles:
    - ISO format strings with Z suffix
    - ISO format strings with +00:00 offset
    - ISO format strings with microseconds
    - None input (returns None)
    """
    if date_str is None:
        return None

    # Handle Z suffix
    if date_str.endswith("Z") or date_str.endswith("z"):
        date_str = date_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(date_str)
        # Attach UTC if no timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def day_key_et(dt: datetime | None = None) -> str:
    """Return the ET date key (YYYY-MM-DD) for a given datetime.

    If dt is None or timezone-naive, uses current ET time.
    """
    if dt is None or dt.tzinfo is None:
        dt = datetime.now(ET)
    return dt.astimezone(ET).strftime("%Y-%m-%d")


def same_et_day(dt1: datetime, dt2: datetime) -> bool:
    """Check if two datetimes fall on the same ET calendar day."""
    return day_key_et(dt1) == day_key_et(dt2)


def calculate_progress(
    expires_at: datetime,
    now: datetime | None = None,
    start_at: datetime | None = None,
) -> float:
    """Calculate how far the event has progressed from start to expiry.

    Returns a value 0.0-100.0 representing the percentage of time elapsed.

    If start_at is None, uses the midpoint between now and expires_at
    as the start (assumes the event started before now).

    Clamps to [0.0, 100.0].
    """
    if now is None:
        now = datetime.now(UTC)

    # Ensure timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    total_seconds = (expires_at - (start_at or now)).total_seconds()
    remaining_seconds = (expires_at - now).total_seconds()

    if total_seconds <= 0:
        return 100.0

    progress = (1.0 - (remaining_seconds / total_seconds)) * 100.0
    return max(0.0, min(100.0, progress))
