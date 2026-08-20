"""Collect, validate, persist, and project bounded Research results."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_runs import approvals
from app.agent_runs import service as run_service
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.repositories import agent_runtime as repository
from app.research.catalog import is_research
from app.research.provider import ResearchProviderResult
from app.schemas.agent_run import AgentRunState

RESULT_EVENT = "research.result"
ALLOWED_TYPES = frozenset({"project", "memory", "source", "source_chunk"})
FORBIDDEN_PUBLIC_TEXT = (
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "bearer ",
    "://",
)


class ResearchValidationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CollectedEvidence:
    evidence_id: str
    run_id: uuid.UUID
    step_id: uuid.UUID
    invocation_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    version: str
    content: dict[str, object]

    def provider_value(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "version": self.version,
            "content": self.content,
        }


@dataclass(frozen=True, slots=True)
class ObservedEvidence:
    """Identity/version captured in the same Tool handler that observed the row."""

    entity_type: str
    entity_id: uuid.UUID
    version: str


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _entity_version(entity_type: str, row: object) -> str:
    if entity_type == "memory":
        assert isinstance(row, Memory)
        return approvals.target_version(row)
    if entity_type == "project":
        assert isinstance(row, Project)
        return _digest(
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "updated_at": row.updated_at,
            }
        )
    if entity_type == "source":
        assert isinstance(row, Source)
        return _digest(
            {
                "id": row.id,
                "source_type": row.source_type,
                "name": row.name,
                "reference": row.reference,
                "updated_at": row.updated_at,
            }
        )
    assert entity_type == "source_chunk" and isinstance(row, SourceChunk)
    return _digest(
        {
            "id": row.id,
            "document_id": row.document_id,
            "chunk_index": row.chunk_index,
            "content_hash": row.content_hash,
            "content_sha256": hashlib.sha256(row.content.encode()).hexdigest(),
            "char_start": row.char_start,
            "char_end": row.char_end,
            "locator": row.locator,
        }
    )


def observe_entity(entity_type: str, row: object) -> ObservedEvidence:
    if entity_type not in ALLOWED_TYPES:
        raise ResearchValidationError
    entity_id = getattr(row, "id", None)
    if not isinstance(entity_id, uuid.UUID):
        raise ResearchValidationError
    return ObservedEvidence(entity_type, entity_id, _entity_version(entity_type, row))


def _row(session: Session, entity_type: str, entity_id: uuid.UUID) -> object | None:
    model = {
        "project": Project,
        "memory": Memory,
        "source": Source,
        "source_chunk": SourceChunk,
    }[entity_type]
    return session.get(model, entity_id)


def _in_scope(
    session: Session, run: AgentRun, entity_type: str, entity_id: uuid.UUID
) -> bool:
    if entity_type == "project":
        return run.project_id is not None and entity_id == run.project_id
    scope = (
        Memory.project_id.is_(None)
        if run.project_id is None
        else Memory.project_id == run.project_id
    )
    if entity_type == "memory":
        statement = select(Memory.id).where(Memory.id == entity_id, scope)
    elif entity_type == "source":
        statement = (
            select(Source.id)
            .join(MemorySource, MemorySource.source_id == Source.id)
            .join(Memory, Memory.id == MemorySource.memory_id)
            .where(Source.id == entity_id, scope)
        )
    else:
        statement = (
            select(SourceChunk.id)
            .join(SourceDocument, SourceDocument.id == SourceChunk.document_id)
            .join(Source, Source.id == SourceDocument.source_id)
            .join(MemorySource, MemorySource.source_id == Source.id)
            .join(Memory, Memory.id == MemorySource.memory_id)
            .where(SourceChunk.id == entity_id, scope)
        )
    return session.scalar(statement.limit(1)) is not None


def collect_output(
    *,
    run: AgentRun,
    step: AgentStep,
    invocation: ToolInvocation,
    output: BaseModel,
    offset: int,
    observed: list[ObservedEvidence],
) -> list[CollectedEvidence]:
    """Bind safe output to identities captured by the exact Tool read."""

    value = output.model_dump(mode="json")
    if step.tool_name == "memory.search_explained":
        candidates = [
            ("memory", uuid.UUID(item["memory_id"]), item) for item in value["results"]
        ]
    else:
        entity_type = {
            "project.get": "project",
            "memory.get": "memory",
            "source.get": "source",
            "source_chunk.get": "source_chunk",
        }.get(step.tool_name or "")
        if entity_type is None:
            raise ResearchValidationError
        candidates = [(entity_type, uuid.UUID(value["id"]), value)]
    if [(item.entity_type, item.entity_id) for item in observed] != [
        (entity_type, entity_id) for entity_type, entity_id, _content in candidates
    ]:
        raise ResearchValidationError
    collected: list[CollectedEvidence] = []
    for index, ((entity_type, entity_id, content), snapshot) in enumerate(
        zip(candidates, observed, strict=True), offset + 1
    ):
        if entity_type not in ALLOWED_TYPES:
            raise ResearchValidationError
        collected.append(
            CollectedEvidence(
                f"e{index}",
                run.id,
                step.id,
                invocation.id,
                entity_type,
                entity_id,
                snapshot.version,
                content,
            )
        )
    return collected


def evidence_references(items: list[CollectedEvidence]) -> list[dict[str, object]]:
    return [
        {
            "entity_type": item.entity_type,
            "id": str(item.entity_id),
            "version": item.version,
        }
        for item in items
    ]


def validate_result(
    result: ResearchProviderResult, evidence: list[CollectedEvidence]
) -> dict[str, object]:
    try:
        result = ResearchProviderResult.model_validate(result, strict=True)
    except (ValidationError, TypeError, ValueError):
        raise ResearchValidationError from None
    by_id = {item.evidence_id: item for item in evidence}
    if not evidence and result.status == "answered":
        raise ResearchValidationError
    citations: list[dict[str, object]] = []
    numbers: dict[str, int] = {}
    claims: list[dict[str, object]] = []
    for claim in result.claims:
        lowered = claim.text.casefold()
        if any(marker in lowered for marker in FORBIDDEN_PUBLIC_TEXT) or any(
            ord(character) < 32 and character not in "\n\t" for character in claim.text
        ):
            raise ResearchValidationError
        if len(claim.citations) != len(set(claim.citations)):
            raise ResearchValidationError
        claim_numbers: list[int] = []
        for reference in claim.citations:
            item = by_id.get(reference)
            if item is None:
                raise ResearchValidationError
            if reference not in numbers:
                if len(numbers) == 20:
                    raise ResearchValidationError
                number = len(numbers) + 1
                numbers[reference] = number
                citations.append(
                    {
                        "number": number,
                        "entity_type": item.entity_type,
                        "entity_id": str(item.entity_id),
                        "version": item.version,
                    }
                )
            claim_numbers.append(numbers[reference])
        claims.append({"text": claim.text, "citation_numbers": claim_numbers})
    if result.insufficiency is not None:
        lowered = result.insufficiency.casefold()
        if any(marker in lowered for marker in FORBIDDEN_PUBLIC_TEXT):
            raise ResearchValidationError
    value: dict[str, object] = {
        "status": result.status,
        "claims": claims,
        "citations": citations,
        "insufficiency": result.insufficiency,
    }
    if len(json.dumps(value, separators=(",", ":")).encode()) > 3500:
        raise ResearchValidationError
    return value


def _still_current(
    session: Session, run: AgentRun, items: list[CollectedEvidence]
) -> bool:
    for item in items:
        if item.run_id != run.id:
            return False
        step = repository.get_agent_step(session, run.id, item.step_id)
        invocation = repository.get_tool_invocation_for_update(
            session, run.id, item.invocation_id
        )
        row = _row(session, item.entity_type, item.entity_id)
        if (
            step is None
            or invocation is None
            or invocation.step_id != step.id
            or invocation.status != "succeeded"
            or row is None
        ):
            return False
        if not _in_scope(session, run, item.entity_type, item.entity_id):
            return False
        if _entity_version(item.entity_type, row) != item.version:
            return False
    return True


def evidence_is_current(
    session: Session, run: AgentRun, items: list[CollectedEvidence]
) -> bool:
    """Public fail-closed reuse boundary for evidence-backed Agents."""

    return _still_current(session, run, items)


def persist_result(
    session: Session,
    *,
    run_id: uuid.UUID,
    evidence: list[CollectedEvidence],
    result: ResearchProviderResult,
) -> bool:
    # Provider latency occurs outside the transaction. Discard every cached ORM
    # value so the locking reads below observe cancellation, deadline, and entity
    # mutations committed by concurrent sessions.
    session.expire_all()
    run = repository.get_agent_run_for_update(session, run_id)
    if (
        run is None
        or not is_research(run.agent_kind, run.agent_version)
        or run.state != AgentRunState.RUNNING.value
    ):
        raise ResearchValidationError
    now = run_service.utc_now()
    if now >= run.run_deadline:
        run_service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.RUNNING,
            expected_revision=run.revision,
            new_state=AgentRunState.EXPIRED,
            now=now,
            safe_error_code="deadline_expired",
        )
        return False
    if not _still_current(session, run, evidence):
        raise ResearchValidationError
    value = validate_result(result, evidence)
    repository.append_agent_event(
        session,
        run_id=run.id,
        event_type=RESULT_EVENT,
        safe_code="research_result",
        safe_message="bounded Research result produced",
        metadata=value,
        correlation_id=run.correlation_id,
        occurred_at=run_service.utc_now(),
    )
    return True


def fail_result(session: Session, run_id: uuid.UUID, code: str) -> None:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return
    run_service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.FAILED,
        safe_error_code=code,
    )


def claim_synthesis(session: Session, run_id: uuid.UUID) -> bool:
    """Reconcile cancellation/deadline immediately before provider latency."""

    run = repository.get_agent_run_for_update(session, run_id)
    if run is None or run.state != AgentRunState.RUNNING.value:
        return False
    now = run_service.utc_now()
    if now < run.run_deadline:
        return True
    run_service.transition_run(
        session,
        run.id,
        expected_state=AgentRunState.RUNNING,
        expected_revision=run.revision,
        new_state=AgentRunState.EXPIRED,
        now=now,
        safe_error_code="deadline_expired",
    )
    return False


def get_result(session: Session, run_id: uuid.UUID) -> dict[str, Any] | None:
    event = session.scalar(
        select(AgentEvent)
        .where(AgentEvent.run_id == run_id, AgentEvent.event_type == RESULT_EVENT)
        .order_by(AgentEvent.sequence.desc())
        .limit(1)
    )
    return None if event is None else event.safe_metadata
