"""Closed code-owned Calendar event and field catalogs."""

from types import MappingProxyType

ORDINARY_EVENT_TYPE = "default"
SPECIAL_EVENT_LABELS = MappingProxyType(
    {
        "focus_time": "Focus time",
        "out_of_office": "Out of office",
        "working_location": "Working location",
        "birthday": "Birthday",
    }
)
EVENT_TYPES = frozenset({ORDINARY_EVENT_TYPE, *SPECIAL_EVENT_LABELS})

# CP102 may request no field outside this exact catalog without a new review.
APPROVED_EVENT_FIELDS = frozenset(
    {
        "id",
        "status",
        "eventType",
        "summary",
        "visibility",
        "etag",
        "updated",
        "recurringEventId",
        "originalStartTime.date",
        "originalStartTime.dateTime",
        "originalStartTime.timeZone",
        "start.date",
        "start.dateTime",
        "start.timeZone",
        "end.date",
        "end.dateTime",
        "end.timeZone",
    }
)
APPROVED_COLLECTION_FIELDS = frozenset({"items", "nextPageToken"})


def event_label(event_type: str, *, private: bool, ordinary_title: str) -> str:
    """Return minimized display text or fail closed for an unknown type."""

    if event_type not in EVENT_TYPES:
        raise ValueError("unsupported calendar event type")
    if private:
        return "Busy"
    if event_type != ORDINARY_EVENT_TYPE:
        return SPECIAL_EVENT_LABELS[event_type]
    title = ordinary_title.strip()
    if not title or len(title) > 500 or len(title.encode("utf-8")) > 2000:
        raise ValueError("calendar title is outside the approved bounds")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in title):
        raise ValueError("calendar title contains a control character")
    return title
