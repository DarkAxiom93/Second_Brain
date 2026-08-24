"""Pure deterministic calculation for the closed Automation schedule forms."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ScheduleCalculationError(ValueError):
    """The schedule cannot produce a valid progressing UTC instant."""


@dataclass(frozen=True)
class ScheduleDefinition:
    kind: str
    timezone_name: str
    local_time: time
    one_time_local_date: date | None = None
    weekdays: tuple[int, ...] = ()
    interval_count: int = 1


@dataclass(frozen=True)
class SchedulePoint:
    local_date: date
    local_time: time
    timezone_name: str
    utc_offset_minutes: int
    utc_instant: datetime


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleCalculationError("unknown IANA timezone") from exc


def _valid_fold(local: datetime, zone: ZoneInfo, fold: int) -> datetime | None:
    aware = local.replace(tzinfo=zone, fold=fold)
    round_trip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    return aware if round_trip == local else None


def _resolve_local(local: datetime, zone: ZoneInfo) -> datetime:
    fold_zero = _valid_fold(local, zone, 0)
    if fold_zero is not None:
        return fold_zero
    # A gap is bounded by timezone transition rules. Moving minute-by-minute
    # yields the first valid wall instant after it, rather than preserving the
    # invalid minute component across the jump.
    candidate = local
    for _ in range(24 * 60):
        candidate += timedelta(minutes=1)
        resolved = _valid_fold(candidate, zone, 0)
        if resolved is not None:
            return resolved
    raise ScheduleCalculationError("nonexistent local time did not resolve")


def _point(
    local_date: date, local_time: time, definition: ScheduleDefinition
) -> SchedulePoint:
    zone = _zone(definition.timezone_name)
    naive = datetime.combine(local_date, local_time.replace(tzinfo=None))
    aware = _resolve_local(naive, zone)
    offset = aware.utcoffset()
    if offset is None:
        raise ScheduleCalculationError("timezone has no UTC offset")
    return SchedulePoint(
        local_date=aware.date(),
        local_time=aware.time().replace(tzinfo=None),
        timezone_name=definition.timezone_name,
        utc_offset_minutes=int(offset.total_seconds() // 60),
        utc_instant=aware.astimezone(UTC),
    )


def validate_definition(definition: ScheduleDefinition) -> None:
    """Validate the complete closed schedule without consulting host timezone."""

    _zone(definition.timezone_name)
    if definition.local_time.tzinfo is not None:
        raise ScheduleCalculationError("local wall time must not include timezone")
    if definition.local_time.second or definition.local_time.microsecond:
        raise ScheduleCalculationError("seconds-level schedules are not supported")
    if not 1 <= definition.interval_count <= 365:
        raise ScheduleCalculationError("interval count is outside approved bounds")
    if definition.kind == "one_time":
        if definition.one_time_local_date is None or definition.weekdays:
            raise ScheduleCalculationError("invalid one-time schedule fields")
    elif definition.kind == "daily":
        if definition.one_time_local_date is not None or definition.weekdays:
            raise ScheduleCalculationError("invalid daily schedule fields")
    elif definition.kind == "weekly":
        if definition.one_time_local_date is not None:
            raise ScheduleCalculationError("invalid weekly schedule fields")
        if not definition.weekdays or any(
            day < 1 or day > 7 for day in definition.weekdays
        ):
            raise ScheduleCalculationError(
                "weekly schedule requires weekdays 1 through 7"
            )
        if len(set(definition.weekdays)) != len(definition.weekdays):
            raise ScheduleCalculationError("weekly weekdays must be unique")
    else:
        raise ScheduleCalculationError("unsupported schedule kind")


def next_point(
    definition: ScheduleDefinition,
    *,
    after_utc: datetime,
    prior: SchedulePoint | None = None,
) -> SchedulePoint | None:
    """Return the first slot strictly after ``after_utc``.

    When ``prior`` is supplied, recurrence advances from its scheduled local
    slot. This is the drift-prevention boundary used by future materialization.
    """

    validate_definition(definition)
    if after_utc.tzinfo is None or after_utc.utcoffset() is None:
        raise ScheduleCalculationError("reference instant must be timezone-aware")
    after = after_utc.astimezone(UTC)
    if definition.kind == "one_time":
        assert definition.one_time_local_date is not None
        result = _point(
            definition.one_time_local_date, definition.local_time, definition
        )
        return result if result.utc_instant > after else None

    zone = _zone(definition.timezone_name)
    if prior is None:
        candidate_date = after.astimezone(zone).date()
    else:
        candidate_date = prior.local_date

    if definition.kind == "daily":
        if prior is not None:
            candidate_date += timedelta(days=definition.interval_count)
        for _ in range(367):
            result = _point(candidate_date, definition.local_time, definition)
            if result.utc_instant > after:
                return result
            candidate_date += timedelta(
                days=1 if prior is None else definition.interval_count
            )
    else:
        weekdays = sorted(definition.weekdays)
        if prior is not None:
            later = [day for day in weekdays if day > prior.local_date.isoweekday()]
            if later:
                candidate_date += timedelta(
                    days=later[0] - prior.local_date.isoweekday()
                )
            else:
                candidate_date += timedelta(
                    days=(7 - prior.local_date.isoweekday())
                    + weekdays[0]
                    + 7 * (definition.interval_count - 1)
                )
        for _ in range(370):
            weekday = candidate_date.isoweekday()
            days_forward = min((day - weekday) % 7 for day in weekdays)
            candidate_date += timedelta(days=days_forward)
            result = _point(candidate_date, definition.local_time, definition)
            if result.utc_instant > after:
                return result
            candidate_date += timedelta(days=1)
    raise ScheduleCalculationError("schedule calculation did not progress")


def preview(
    definition: ScheduleDefinition, *, after_utc: datetime, count: int
) -> list[SchedulePoint]:
    """Calculate a bounded sequence without persistence or lifecycle effects."""

    if not 1 <= count <= 10:
        raise ScheduleCalculationError("preview count is outside approved bounds")
    points: list[SchedulePoint] = []
    prior: SchedulePoint | None = None
    cursor = after_utc
    for _ in range(count):
        point = next_point(definition, after_utc=cursor, prior=prior)
        if point is None:
            break
        if point.utc_instant <= cursor:
            raise ScheduleCalculationError("schedule calculation did not progress")
        points.append(point)
        prior = point
        cursor = point.utc_instant
    return points
