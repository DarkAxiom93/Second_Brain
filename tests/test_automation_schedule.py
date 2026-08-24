"""Deterministic unit coverage for closed Automation schedules and schemas."""

from datetime import UTC, date, datetime, time

import pytest
from pydantic import ValidationError

from app.automations.schedule import (
    ScheduleCalculationError,
    ScheduleDefinition,
    next_point,
    preview,
)
from app.schemas.automation import AutomationCreate


def _definition(**changes: object) -> ScheduleDefinition:
    values: dict[str, object] = {
        "kind": "daily",
        "timezone_name": "Asia/Jerusalem",
        "local_time": time(8, 30),
    }
    values.update(changes)
    return ScheduleDefinition(**values)  # type: ignore[arg-type]


def test_one_time_daily_and_weekly_calculation() -> None:
    one_time = next_point(
        _definition(kind="one_time", one_time_local_date=date(2026, 8, 25)),
        after_utc=datetime(2026, 8, 24, tzinfo=UTC),
    )
    assert one_time is not None
    assert one_time.local_date == date(2026, 8, 25)
    assert one_time.utc_instant == datetime(2026, 8, 25, 5, 30, tzinfo=UTC)

    daily = preview(
        _definition(interval_count=2),
        after_utc=datetime(2026, 8, 24, 6, tzinfo=UTC),
        count=3,
    )
    assert [point.local_date for point in daily] == [
        date(2026, 8, 25),
        date(2026, 8, 27),
        date(2026, 8, 29),
    ]

    weekly = preview(
        _definition(kind="weekly", weekdays=(1, 3), interval_count=2),
        after_utc=datetime(2026, 8, 24, 6, tzinfo=UTC),
        count=4,
    )
    assert [point.local_date for point in weekly] == [
        date(2026, 8, 26),
        date(2026, 9, 7),
        date(2026, 9, 9),
        date(2026, 9, 21),
    ]


def test_dst_gap_uses_first_valid_instant_and_fold_uses_fold_zero_once() -> None:
    gap = next_point(
        _definition(
            kind="one_time",
            timezone_name="America/New_York",
            local_time=time(2, 30),
            one_time_local_date=date(2026, 3, 8),
        ),
        after_utc=datetime(2026, 3, 1, tzinfo=UTC),
    )
    assert gap is not None
    assert (gap.local_time, gap.utc_offset_minutes, gap.utc_instant) == (
        time(3, 0),
        -240,
        datetime(2026, 3, 8, 7, tzinfo=UTC),
    )

    fold = preview(
        _definition(
            kind="one_time",
            timezone_name="America/New_York",
            local_time=time(1, 30),
            one_time_local_date=date(2026, 11, 1),
        ),
        after_utc=datetime(2026, 10, 1, tzinfo=UTC),
        count=5,
    )
    assert len(fold) == 1
    assert fold[0].utc_offset_minutes == -240
    assert fold[0].utc_instant == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    "definition",
    [
        _definition(timezone_name="Invalid/Nowhere"),
        _definition(kind="weekly", weekdays=()),
        _definition(kind="daily", weekdays=(1,)),
        _definition(local_time=time(8, 30, 1)),
        _definition(interval_count=0),
    ],
)
def test_invalid_closed_schedule_fields_fail(definition: ScheduleDefinition) -> None:
    with pytest.raises(ScheduleCalculationError):
        next_point(definition, after_utc=datetime(2026, 1, 1, tzinfo=UTC))


def test_calculation_is_host_timezone_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _definition(timezone_name="Asia/Tokyo")
    expected = next_point(definition, after_utc=datetime(2026, 8, 24, 0, tzinfo=UTC))
    monkeypatch.setenv("TZ", "Pacific/Honolulu")
    actual = next_point(definition, after_utc=datetime(2026, 8, 24, 0, tzinfo=UTC))
    assert actual == expected


def test_preview_rejects_non_progressing_calculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.automations import schedule as module

    first = next_point(_definition(), after_utc=datetime(2026, 8, 24, 0, tzinfo=UTC))
    assert first is not None
    monkeypatch.setattr(module, "next_point", lambda *args, **kwargs: first)
    with pytest.raises(ScheduleCalculationError, match="did not progress"):
        module.preview(
            _definition(),
            after_utc=datetime(2026, 8, 24, 0, tzinfo=UTC),
            count=2,
        )


def test_request_schema_is_closed_and_execution_defaults_create_only() -> None:
    request = AutomationCreate.model_validate(
        {
            "label": "Morning",
            "agent_kind": "daily_brief",
            "schedule": {
                "kind": "daily",
                "timezone_name": "UTC",
                "local_time": "08:30:00",
            },
        }
    )
    assert request.execution_mode == "create_only"
    one_time = AutomationCreate.model_validate(
        {
            "label": "Once",
            "agent_kind": "daily_brief",
            "schedule": {
                "kind": "one_time",
                "timezone_name": "UTC",
                "local_time": "08:30:00",
                "one_time_local_date": "2030-01-01",
            },
        }
    )
    assert one_time.missed_run_policy == "run_once"
    with pytest.raises(ValidationError):
        AutomationCreate.model_validate(
            {
                **request.model_dump(mode="json"),
                "tools": ["memory.get"],
            }
        )
