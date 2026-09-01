"""Pure closed Calendar catalog and recurrence identity tests."""

from datetime import UTC, date, datetime

import pytest

from app.calendar.catalog import APPROVED_EVENT_FIELDS, EVENT_TYPES, event_label
from app.calendar.identity import occurrence_identity


def test_closed_event_types_and_minimized_labels() -> None:
    assert {
        "default",
        "focus_time",
        "out_of_office",
        "working_location",
        "birthday",
    } == EVENT_TYPES
    assert event_label("default", private=True, ordinary_title="secret") == "Busy"
    assert (
        event_label("focus_time", private=False, ordinary_title="ignored")
        == "Focus time"
    )
    with pytest.raises(ValueError):
        event_label("provider_future_type", private=False, ordinary_title="unsafe")


def test_projection_catalog_excludes_sensitive_fields() -> None:
    excluded = {
        "description",
        "location",
        "attendees",
        "organizer",
        "creator",
        "conferenceData",
        "attachments",
        "reminders",
        "extendedProperties",
        "recurrence",
        "hangoutLink",
    }
    assert APPROVED_EVENT_FIELDS.isdisjoint(excluded)


def test_occurrence_identity_is_stable_across_current_time_changes() -> None:
    original = datetime(2026, 8, 31, 10, tzinfo=UTC)
    first = occurrence_identity(
        event_id="instance-a", recurring_series_id="series-a", original_start=original
    )
    moved = occurrence_identity(
        event_id="modified-instance",
        recurring_series_id="series-a",
        original_start=original,
    )
    assert first.key == moved.key
    assert occurrence_identity(event_id="single").key != first.key
    assert (
        occurrence_identity(
            event_id="all-day",
            recurring_series_id="series-a",
            original_start=date(2026, 8, 31),
        ).key
        != first.key
    )
    with pytest.raises(ValueError):
        occurrence_identity(
            event_id="bad",
            recurring_series_id="series",
            original_start=datetime(2026, 8, 31, 10),
        )
