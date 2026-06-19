"""Price utilities — shared helpers for cents/dollars conversion."""

from typing import Optional


def cents_to_dollars(cents: Optional[int]) -> Optional[float]:
    """Convert integer cents to float dollars. Returns None if input is None."""
    if cents is None:
        return None
    return round(cents / 100.0, 2)
