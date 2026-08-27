"""Closed, exact-scope Project Watch change projection and watermark."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_runtime import AgentEvent, AgentRun
from app.models.automation import Automation, AutomationOccurrence
from app.models.memory import Memory
from app.models.project import Project
from app.research import service as evidence_service

MAX_CHANGES = 20
INITIAL_WINDOW = timedelta(days=7)


class ChangeValidationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ChangeWindow:
    occurrence_id: uuid.UUID
    project_id: uuid.UUID
    lower: datetime
    upper: datetime


@dataclass(frozen=True, slots=True)
class ChangeEvidence:
    evidence_id: str
    entity_type: str
    entity_id: uuid.UUID
    version: str
    project_id: uuid.UUID
    changed_at: datetime
    content: dict[str, object]

    def provider_value(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "version": self.version,
            "content": self.content,
        }


def derive_window(session: Session, run_id: uuid.UUID) -> ChangeWindow:
    current = session.scalar(
        select(AutomationOccurrence).where(
            AutomationOccurrence.agent_run_id == run_id,
            AutomationOccurrence.agent_kind == "project_watch",
            AutomationOccurrence.agent_version == "1",
        )
    )
    if current is None or current.project_id is None:
        raise ChangeValidationError
    automation = session.get(Automation, current.automation_id)
    project = session.get(Project, current.project_id)
    if automation is None or project is None:
        raise ChangeValidationError
    previous = session.scalar(
        select(AutomationOccurrence)
        .join(AgentRun, AgentRun.id == AutomationOccurrence.agent_run_id)
        .join(
            AgentEvent,
            (AgentEvent.run_id == AgentRun.id)
            & (AgentEvent.event_type == "project_watch.result"),
        )
        .where(
            AutomationOccurrence.automation_id == current.automation_id,
            AutomationOccurrence.id != current.id,
            AutomationOccurrence.agent_kind == "project_watch",
            AutomationOccurrence.agent_version == "1",
            AutomationOccurrence.project_id == current.project_id,
            AutomationOccurrence.state == "completed",
            AgentRun.state == "completed",
            AutomationOccurrence.scheduled_at < current.scheduled_at,
        )
        .order_by(
            AutomationOccurrence.scheduled_at.desc(),
            AutomationOccurrence.id.desc(),
        )
        .limit(1)
    )
    initial_lower = max(automation.created_at, current.scheduled_at - INITIAL_WINDOW)
    if initial_lower >= current.scheduled_at:
        initial_lower = current.scheduled_at - INITIAL_WINDOW
    lower = previous.scheduled_at if previous is not None else initial_lower
    if lower >= current.scheduled_at:
        raise ChangeValidationError
    return ChangeWindow(current.id, current.project_id, lower, current.scheduled_at)


def _content(
    entity_type: str, row: Project | Memory, changed_at: datetime
) -> dict[str, object]:
    if entity_type == "project":
        assert isinstance(row, Project)
        return {
            "change_kind": "project_state",
            "changed_at": changed_at.isoformat(),
            "name": row.name,
            "description": row.description,
        }
    assert isinstance(row, Memory)
    return {
        "change_kind": "memory_state",
        "changed_at": changed_at.isoformat(),
        "title": row.title,
        "summary": row.summary,
        "content": row.content,
        "memory_type": row.memory_type,
        "status": row.status,
        "importance": row.importance,
        "confidence": row.confidence,
    }


def collect(session: Session, window: ChangeWindow) -> list[ChangeEvidence]:
    project = session.get(Project, window.project_id)
    if project is None:
        raise ChangeValidationError
    candidates: list[tuple[datetime, str, Project | Memory]] = []
    if window.lower < project.updated_at <= window.upper:
        candidates.append((project.updated_at, "project", project))
    memories = session.scalars(
        select(Memory)
        .where(
            Memory.project_id == window.project_id,
            Memory.updated_at > window.lower,
            Memory.updated_at <= window.upper,
        )
        .order_by(Memory.updated_at.asc(), Memory.id.asc())
        .limit(MAX_CHANGES)
    ).all()
    candidates.extend((row.updated_at, "memory", row) for row in memories)
    candidates.sort(key=lambda item: (item[0], item[2].id))
    result: list[ChangeEvidence] = []
    for index, (changed_at, entity_type, row) in enumerate(candidates[:MAX_CHANGES], 1):
        observed = evidence_service.observe_entity(entity_type, row)
        result.append(
            ChangeEvidence(
                f"e{index}",
                entity_type,
                row.id,
                observed.version,
                window.project_id,
                changed_at,
                _content(entity_type, row, changed_at),
            )
        )
    return result


def is_current(
    session: Session, window: ChangeWindow, evidence: list[ChangeEvidence]
) -> bool:
    try:
        if (
            derive_window(
                session, _run_id_for_occurrence(session, window.occurrence_id)
            )
            != window
        ):
            return False
    except ChangeValidationError:
        return False
    for item in evidence:
        row: Project | Memory | None
        if item.entity_type == "project":
            row = session.get(Project, item.entity_id)
        elif item.entity_type == "memory":
            row = session.get(Memory, item.entity_id)
        else:
            return False
        if (
            row is None
            or item.project_id != window.project_id
            or not (window.lower < item.changed_at <= window.upper)
        ):
            return False
        if item.entity_type == "project":
            if item.entity_id != window.project_id or row.updated_at != item.changed_at:
                return False
        elif (
            not isinstance(row, Memory)
            or row.project_id != window.project_id
            or row.updated_at != item.changed_at
        ):
            return False
        observed = evidence_service.observe_entity(item.entity_type, row)
        if (
            observed.version != item.version
            or _content(item.entity_type, row, item.changed_at) != item.content
        ):
            return False
    return True


def _run_id_for_occurrence(session: Session, occurrence_id: uuid.UUID) -> uuid.UUID:
    occurrence = session.get(AutomationOccurrence, occurrence_id)
    if occurrence is None or occurrence.agent_run_id is None:
        raise ChangeValidationError
    return occurrence.agent_run_id
