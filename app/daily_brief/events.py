"""Closed, scoped application-event evidence from Automation occurrences."""

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation import AutomationOccurrence

MAX_APPLICATION_EVENTS = 5
EVENT_KIND_BY_STATE = {
    "completed": "automation_run_completed",
    "missed": "automation_occurrence_missed",
    "failed": "automation_occurrence_failed",
    "cancelled": "automation_occurrence_cancelled",
}


class ApplicationEventValidationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ApplicationEventEvidence:
    evidence_id: str
    entity_type: str
    entity_id: uuid.UUID
    version: str
    project_id: uuid.UUID | None
    content: dict[str, object]

    def provider_value(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "version": self.version,
            "content": self.content,
        }


def _projection(row: AutomationOccurrence) -> dict[str, object]:
    kind = EVENT_KIND_BY_STATE.get(row.state)
    if kind is None or row.completed_at is None:
        raise ApplicationEventValidationError
    return {
        "event_kind": kind,
        "occurred_at": row.completed_at.isoformat(),
        "scheduled_at": row.scheduled_at.isoformat(),
        "agent_kind": row.agent_kind,
        "agent_version": row.agent_version,
    }


def _version(row: AutomationOccurrence) -> str:
    encoded = json.dumps(
        _projection(row), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def collect(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> list[ApplicationEventEvidence]:
    """Select recent terminal occurrences in one exact nullable scope."""

    bounded = min(max(limit, 0), MAX_APPLICATION_EVENTS)
    if bounded == 0:
        return []
    scope = (
        AutomationOccurrence.project_id.is_(None)
        if project_id is None
        else AutomationOccurrence.project_id == project_id
    )
    rows = session.scalars(
        select(AutomationOccurrence)
        .where(
            scope,
            AutomationOccurrence.state.in_(tuple(EVENT_KIND_BY_STATE)),
            AutomationOccurrence.completed_at.is_not(None),
        )
        .order_by(
            AutomationOccurrence.completed_at.desc(),
            AutomationOccurrence.id.desc(),
        )
        .limit(bounded)
    ).all()
    return [
        ApplicationEventEvidence(
            evidence_id=f"e{offset + index}",
            entity_type="application_event",
            entity_id=row.id,
            version=_version(row),
            project_id=row.project_id,
            content=_projection(row),
        )
        for index, row in enumerate(rows, 1)
    ]


def is_current(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    evidence: list[ApplicationEventEvidence],
) -> bool:
    for item in evidence:
        row = session.get(AutomationOccurrence, item.entity_id)
        if (
            item.entity_type != "application_event"
            or item.project_id != project_id
            or row is None
            or row.project_id != project_id
            or row.state not in EVENT_KIND_BY_STATE
            or row.completed_at is None
            or _version(row) != item.version
            or _projection(row) != item.content
        ):
            return False
    return True
