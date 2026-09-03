import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.calendar import sync
from app.calendar.google import (
    EVENT_TYPES,
    FIELDS,
    CalendarTransportError,
    HttpxCalendarTransport,
)
from app.models.calendar import CalendarSyncRun


def _event(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "event-1",
        "status": "confirmed",
        "eventType": "default",
        "summary": "Planning",
        "visibility": "default",
        "etag": '"one"',
        "updated": "2026-09-03T10:00:00Z",
        "start": {
            "dateTime": "2026-09-04T10:00:00+03:00",
            "timeZone": "Asia/Jerusalem",
        },
        "end": {"dateTime": "2026-09-04T11:00:00+03:00", "timeZone": "Asia/Jerusalem"},
    }
    value.update(changes)
    return value


def _run() -> CalendarSyncRun:
    return CalendarSyncRun(
        id=uuid.uuid4(),
        account_revision_id=uuid.uuid4(),
        calendar_identity_id=uuid.uuid4(),
        project_id=None,
        window_start=datetime(2026, 8, 4, tzinfo=UTC),
        window_end=datetime(2026, 11, 2, tzinfo=UTC),
        trigger_kind="manual",
    )


def test_transport_uses_exact_get_path_query_and_projection() -> None:
    request_seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_seen
        request_seen = request
        return httpx.Response(200, json={"items": [], "nextPageToken": "opaque"})

    transport = HttpxCalendarTransport()
    transport._client.close()
    transport._client = httpx.Client(
        base_url="https://www.googleapis.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    page = transport.events(
        "fake-access",
        "team/a@example.com",
        datetime(2026, 8, 4, tzinfo=UTC),
        datetime(2026, 11, 2, tzinfo=UTC),
    )
    assert page.next_page_token == "opaque"
    assert request_seen is not None and request_seen.method == "GET"
    assert request_seen.url.raw_path.split(b"?", 1)[0] == (
        b"/calendar/v3/calendars/team%2Fa%40example.com/events"
    )
    query = request_seen.url.params
    assert query.get("singleEvents") == "true"
    assert query.get("showDeleted") == "false"
    assert query.get("orderBy") == "startTime"
    assert query.get("maxResults") == "250"
    assert query.get_list("eventTypes") == list(EVENT_TYPES)
    assert query.get("fields") == FIELDS
    assert "syncToken" not in query and "q" not in query
    assert "nextSyncToken" not in FIELDS


@pytest.mark.parametrize("status", ["cancelled", None])
def test_cancelled_or_minimal_event_fails_closed(status: object) -> None:
    item = {"id": "event-1"} if status is None else _event(status=status)
    with pytest.raises(CalendarTransportError):
        sync._normalized(item, _run(), datetime.now(UTC))


def test_moved_recurring_occurrence_uses_original_start_identity() -> None:
    item = _event(
        recurringEventId="series-1",
        originalStartTime={"dateTime": "2026-09-04T09:00:00+03:00"},
    )
    first = sync._normalized(item, _run(), datetime.now(UTC))
    item["start"] = {"dateTime": "2026-09-05T10:00:00+03:00"}
    item["end"] = {"dateTime": "2026-09-05T11:00:00+03:00"}
    moved = sync._normalized(item, _run(), datetime.now(UTC))
    assert first.occurrence_key == moved.occurrence_key
    assert first.content_hash != moved.content_hash


def test_all_day_and_private_special_minimization() -> None:
    item = _event(
        eventType="focusTime",
        visibility="private",
        summary="secret",
        start={"date": "2026-09-04"},
        end={"date": "2026-09-05"},
    )
    event = sync._normalized(item, _run(), datetime.now(UTC))
    assert event.all_day is True
    assert event.title == "Busy"
    assert event.start_instant is None


def test_blank_ordinary_summary_is_rejected_without_fabrication() -> None:
    with pytest.raises(CalendarTransportError):
        sync._normalized(_event(summary="  "), _run(), datetime.now(UTC))


@pytest.mark.parametrize("event_type", ["fromGmail", "futureType"])
def test_unapproved_event_type_fails_closed(event_type: str) -> None:
    with pytest.raises(CalendarTransportError):
        sync._normalized(_event(eventType=event_type), _run(), datetime.now(UTC))


def test_ambiguous_timezone_only_instant_is_rejected() -> None:
    with pytest.raises(CalendarTransportError):
        sync._normalized(
            _event(
                start={
                    "dateTime": "2026-11-01T01:30:00",
                    "timeZone": "America/New_York",
                },
                end={"dateTime": "2026-11-01T02:30:00", "timeZone": "America/New_York"},
            ),
            _run(),
            datetime.now(UTC),
        )
