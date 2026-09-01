"""Canonical immutable occurrence identity helpers; no recurrence evaluation."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class OccurrenceIdentity:
    kind: str
    series_id: str | None
    original_date: date | None
    original_instant: datetime | None
    key: str


def occurrence_identity(
    *,
    event_id: str,
    recurring_series_id: str | None = None,
    original_start: date | datetime | None = None,
) -> OccurrenceIdentity:
    """Build identity from provider IDs and canonical originalStartTime."""

    if not event_id or len(event_id) > 1024:
        raise ValueError("invalid provider event id")
    if recurring_series_id is None:
        if original_start is not None:
            raise ValueError("standalone event cannot have original start")
        return OccurrenceIdentity("standalone", None, None, None, f"event:{event_id}")
    if not recurring_series_id or len(recurring_series_id) > 1024:
        raise ValueError("invalid recurring series id")
    if isinstance(original_start, datetime):
        if original_start.tzinfo is None or original_start.utcoffset() is None:
            raise ValueError("timed original start must be timezone-aware")
        canonical = original_start.isoformat(timespec="microseconds")
        return OccurrenceIdentity(
            "recurring",
            recurring_series_id,
            None,
            original_start,
            f"series:{recurring_series_id}:instant:{canonical}",
        )
    if isinstance(original_start, date):
        return OccurrenceIdentity(
            "recurring",
            recurring_series_id,
            original_start,
            None,
            f"series:{recurring_series_id}:date:{original_start.isoformat()}",
        )
    raise ValueError("recurring event requires canonical original start")
