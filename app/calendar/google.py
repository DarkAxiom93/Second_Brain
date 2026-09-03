"""Closed, bounded, GET-only Google Calendar events transport."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

CALENDAR_HOST = "www.googleapis.com"
MAX_RESULTS = 250
MAX_PAGES_PER_CALENDAR = 10
MAX_EVENTS_PER_CALENDAR = 1_000
MAX_EVENTS_PER_REFRESH = 5_000
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_REFRESH_BYTES = 10 * 1024 * 1024
MAX_REQUESTS = 50
REFRESH_DEADLINE_SECONDS = 60.0
MAX_PAGE_TOKEN_BYTES = 4096
EVENT_TYPES = ("default", "birthday", "focusTime", "outOfOffice", "workingLocation")
FIELDS = (
    "nextPageToken,items(id,status,eventType,summary,visibility,etag,updated,"
    "recurringEventId,originalStartTime(date,dateTime,timeZone),"
    "start(date,dateTime,timeZone),end(date,dateTime,timeZone))"
)


class CalendarTransportError(Exception):
    """Content-free provider/limit failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CalendarPage:
    items: list[object]
    next_page_token: str | None


class CalendarTransport(Protocol):
    def events(
        self,
        access_token: str,
        calendar_id: str,
        window_start: datetime,
        window_end: datetime,
        page_token: str | None = None,
    ) -> CalendarPage: ...


class HttpxCalendarTransport:
    """A transport surface that cannot express Calendar writes or arbitrary URLs."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._clock = clock
        self._sleeper = sleeper
        self._started = clock()
        self._requests = 0
        self._bytes = 0
        self._client = httpx.Client(
            base_url=f"https://{CALENDAR_HOST}",
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
            follow_redirects=False,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    def _deadline(self) -> None:
        if self._clock() - self._started >= REFRESH_DEADLINE_SECONDS:
            raise CalendarTransportError("calendar_deadline_ceiling")

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if value.tzinfo is None or value.utcoffset() is None:
            raise CalendarTransportError("calendar_request_invalid")
        return value.isoformat(timespec="seconds").replace("+00:00", "Z")

    def events(
        self,
        access_token: str,
        calendar_id: str,
        window_start: datetime,
        window_end: datetime,
        page_token: str | None = None,
    ) -> CalendarPage:
        if not calendar_id or len(calendar_id) > 1024 or not access_token:
            raise CalendarTransportError("calendar_request_invalid")
        if page_token is not None and (
            not page_token or len(page_token.encode("utf-8")) > MAX_PAGE_TOKEN_BYTES
        ):
            raise CalendarTransportError("calendar_page_token_invalid")
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("singleEvents", "true"),
            ("showDeleted", "false"),
            ("orderBy", "startTime"),
            ("timeMin", self._timestamp(window_start)),
            ("timeMax", self._timestamp(window_end)),
            ("maxResults", str(MAX_RESULTS)),
            *[("eventTypes", value) for value in EVENT_TYPES],
            ("fields", FIELDS),
        ]
        if page_token is not None:
            params.append(("pageToken", page_token))
        path = f"/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"
        for attempt in range(3):
            self._deadline()
            if self._requests >= MAX_REQUESTS:
                raise CalendarTransportError("calendar_request_ceiling")
            self._requests += 1
            try:
                with self._client.stream(
                    "GET",
                    path,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                ) as response:
                    if response.is_redirect:
                        raise CalendarTransportError("calendar_redirect")
                    transient = response.status_code == 429 or response.status_code in {
                        500,
                        502,
                        503,
                        504,
                    }
                    if transient and attempt < 2:
                        delay = min(
                            _retry_after(response.headers.get("retry-after")), 2.0
                        )
                        self._deadline()
                        self._sleeper(delay)
                        continue
                    if response.status_code in {401, 403}:
                        raise CalendarTransportError("calendar_authorization_failed")
                    if response.status_code != 200:
                        code = (
                            "calendar_transient_exhausted"
                            if transient
                            else "calendar_provider_rejected"
                        )
                        raise CalendarTransportError(code)
                    media_type = response.headers.get("content-type", "").split(";", 1)[
                        0
                    ]
                    if media_type != "application/json" or response.headers.get(
                        "content-encoding", "identity"
                    ).lower() not in {"", "identity"}:
                        raise CalendarTransportError("calendar_invalid_response")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise CalendarTransportError("calendar_response_ceiling")
                    self._bytes += len(content)
                    if self._bytes > MAX_REFRESH_BYTES:
                        raise CalendarTransportError("calendar_byte_ceiling")
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
                if attempt < 2:
                    self._sleeper(min(0.25 * (2**attempt), 1.0))
                    continue
                raise CalendarTransportError("calendar_timeout") from None
            self._deadline()
            try:
                raw: Any = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise CalendarTransportError("calendar_invalid_response") from None
            if not isinstance(raw, dict) or not set(raw).issubset(
                {"items", "nextPageToken"}
            ):
                raise CalendarTransportError("calendar_invalid_response")
            items = raw.get("items", [])
            token = raw.get("nextPageToken")
            if not isinstance(items, list) or (
                token is not None and not isinstance(token, str)
            ):
                raise CalendarTransportError("calendar_invalid_response")
            if len(items) > MAX_RESULTS:
                raise CalendarTransportError("calendar_page_item_ceiling")
            if token is not None and (
                not token or len(token.encode("utf-8")) > MAX_PAGE_TOKEN_BYTES
            ):
                raise CalendarTransportError("calendar_page_token_invalid")
            return CalendarPage(items, token)
        raise AssertionError("unreachable")


def _retry_after(value: str | None) -> float:
    if value is None:
        return 0.25
    try:
        parsed = float(value)
    except ValueError:
        return 0.25
    return max(0.0, parsed)


@dataclass(frozen=True, slots=True)
class FakeCalendarCall:
    calendar_id: str
    window_start: datetime
    window_end: datetime
    page_token: str | None


class FakeCalendarTransport:
    def __init__(self, responses: list[CalendarPage | CalendarTransportError]) -> None:
        self._responses = list(responses)
        self.calls: list[FakeCalendarCall] = []

    def events(
        self,
        access_token: str,
        calendar_id: str,
        window_start: datetime,
        window_end: datetime,
        page_token: str | None = None,
    ) -> CalendarPage:
        self.calls.append(
            FakeCalendarCall(calendar_id, window_start, window_end, page_token)
        )
        if not self._responses:
            raise AssertionError("unexpected fake Calendar request")
        result = self._responses.pop(0)
        if isinstance(result, CalendarTransportError):
            raise result
        return result
