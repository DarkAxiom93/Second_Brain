"""Immutable proposed-action creation and exact human review."""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.agent_runtime import ApprovalRequest
from app.models.memory import Memory
from app.repositories import agent_runtime as repository
from app.repositories import memories as memory_repository
from app.schemas.memory import MemoryUpdate

ACTION_TYPE = "memory.update"
TARGET_TYPE = "memory"
PROPOSAL_LIFETIME = timedelta(hours=24)
MAX_EVIDENCE = 20
ALLOWED_EVIDENCE_TYPES = frozenset({"project", "memory", "source", "source_chunk"})


class ApprovalError(Exception):
    """Base safe approval-domain error."""


class NotFoundError(ApprovalError):
    pass


class InvalidProposalError(ApprovalError):
    pass


class ReviewConflictError(ApprovalError):
    pass


class ExpiredApprovalError(ReviewConflictError):
    pass


class StaleApprovalError(ReviewConflictError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def target_version(memory: Memory) -> str:
    """Derive an application-owned version from every proposal-relevant field."""

    return _digest(
        {
            "id": str(memory.id),
            "project_id": None if memory.project_id is None else str(memory.project_id),
            "content": memory.content,
            "source": memory.source,
            "title": memory.title,
            "summary": memory.summary,
            "memory_type": memory.memory_type,
            "importance": memory.importance,
            "confidence": memory.confidence,
            "status": memory.status,
            "event_time": (
                None if memory.event_time is None else memory.event_time.isoformat()
            ),
            "expires_at": (
                None if memory.expires_at is None else memory.expires_at.isoformat()
            ),
            "supersedes_id": (
                None if memory.supersedes_id is None else str(memory.supersedes_id)
            ),
            "updated_at": memory.updated_at.isoformat(),
        }
    )


def normalize_memory_update(
    proposed_input: dict[str, Any], *, target: Memory
) -> dict[str, Any]:
    try:
        update = MemoryUpdate.model_validate(proposed_input)
    except ValidationError as exc:
        raise InvalidProposalError("invalid proposed input") from exc
    normalized = update.model_dump(mode="json", exclude_unset=True)
    if all(
        getattr(target, field) == getattr(update, field)
        for field in update.model_fields_set
    ):
        raise InvalidProposalError("proposed update would not change the target")
    return normalized


def proposal_hash(
    *, target_id: uuid.UUID, version: str, normalized_input: dict[str, Any]
) -> str:
    return _digest(
        {
            "action_type": ACTION_TYPE,
            "target_type": TARGET_TYPE,
            "target_id": str(target_id),
            "target_version": version,
            "normalized_input": normalized_input,
        }
    )


def _safe_evidence(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for reference in references:
        entity_type = reference.get("entity_type")
        raw_id = reference.get("id")
        if entity_type not in ALLOWED_EVIDENCE_TYPES:
            continue
        try:
            public_id = str(uuid.UUID(str(raw_id)))
        except (TypeError, ValueError, AttributeError):
            continue
        key = (str(entity_type), public_id)
        if key not in seen:
            result.append({"entity_type": entity_type, "id": public_id})
            seen.add(key)
        if len(result) == MAX_EVIDENCE:
            break
    return result


def _preview(normalized_input: dict[str, Any]) -> str:
    fields = ", ".join(sorted(normalized_input))
    return f"Update Memory fields: {fields}"[:2000]


def create_proposal(
    session: Session,
    *,
    run_id: uuid.UUID,
    step_ordinal: int,
    action_type: str,
    target_id: uuid.UUID,
    proposed_input: dict[str, Any],
    now: datetime | None = None,
) -> tuple[ApprovalRequest, bool]:
    captured_at = now or datetime.now(UTC)
    if action_type != ACTION_TYPE:
        raise InvalidProposalError("unsupported action type")
    run = repository.get_agent_run_for_update(session, run_id)
    if run is None:
        raise NotFoundError("agent run not found")
    step = repository.get_agent_step_by_ordinal_for_update(
        session, run_id, step_ordinal
    )
    if step is None:
        raise NotFoundError("agent step not found")
    target = memory_repository.lock_memory(session, target_id)
    if target is None or target.project_id != run.project_id:
        raise NotFoundError("target memory not found")
    normalized = normalize_memory_update(proposed_input, target=target)
    version = target_version(target)
    identity = proposal_hash(
        target_id=target.id, version=version, normalized_input=normalized
    )
    existing = repository.get_exact_approval_request(
        session,
        run_id=run.id,
        step_id=step.id,
        action_type=ACTION_TYPE,
        target_type=TARGET_TYPE,
        target_public_id=target.id,
        target_version=version,
        proposal_hash=identity,
    )
    if existing is not None:
        return existing, False
    evidence = _safe_evidence(repository.list_step_evidence(session, run.id, step.id))
    approval = repository.insert_approval_request(
        session,
        ApprovalRequest(
            run_id=run.id,
            step_id=step.id,
            action_type=ACTION_TYPE,
            target_type=TARGET_TYPE,
            target_public_id=target.id,
            target_version=version,
            normalized_input=normalized,
            proposal_hash=identity,
            preview=_preview(normalized),
            evidence_references=evidence,
            risk_classification="bounded_memory_update",
            status="pending",
            created_at=captured_at,
            expires_at=captured_at + PROPOSAL_LIFETIME,
            execution_identity=uuid.uuid4(),
        ),
    )
    repository.append_agent_event(
        session,
        run_id=run.id,
        step_id=step.id,
        approval_id=approval.id,
        event_type="approval_requested",
        safe_code="proposal_created",
        safe_message="Approval request created for human review",
        metadata={"action_type": ACTION_TYPE, "target_type": TARGET_TYPE},
        correlation_id=run.correlation_id,
        occurred_at=captured_at,
        event_idempotency_hash=_digest({"event": "created", "proposal": identity}),
    )
    return approval, True


def review_proposal(
    session: Session,
    *,
    approval_id: uuid.UUID,
    decision: Literal["approve", "reject"],
    now: datetime | None = None,
) -> tuple[ApprovalRequest, bool]:
    captured_at = now or datetime.now(UTC)
    approval = repository.get_approval_request_for_update(session, approval_id)
    if approval is None:
        raise NotFoundError("approval request not found")
    desired = "approved" if decision == "approve" else "rejected"
    if approval.status == desired:
        return approval, False
    if approval.status != "pending":
        raise ReviewConflictError("approval request is already terminal")
    run = repository.get_agent_run_for_update(session, approval.run_id)
    if run is None:
        raise NotFoundError("agent run not found")
    target = memory_repository.lock_memory(session, approval.target_public_id)

    if captured_at >= approval.expires_at:
        approval.status = "expired"
        approval.reviewed_at = captured_at
        approval.reviewer_metadata = {"source": "server", "reason": "expired"}
        code = "approval_expired"
        message = "Approval request expired"
        terminal_error: type[ReviewConflictError] | None = ExpiredApprovalError
    elif (
        target is None
        or target.project_id != run.project_id
        or target_version(target) != approval.target_version
    ):
        approval.status = "superseded"
        approval.reviewed_at = captured_at
        approval.reviewer_metadata = {"source": "server", "reason": "stale_target"}
        code = "approval_superseded"
        message = "Approval request target is stale"
        terminal_error = StaleApprovalError
    else:
        approval.status = desired
        approval.reviewed_at = captured_at
        approval.reviewer_metadata = {"source": "human_api", "decision": decision}
        code = f"approval_{desired}"
        message = f"Approval request {desired} by human review"
        terminal_error = None
    repository.append_agent_event(
        session,
        run_id=run.id,
        step_id=approval.step_id,
        approval_id=approval.id,
        event_type=code,
        safe_code=code,
        safe_message=message,
        metadata={"action_type": approval.action_type, "status": approval.status},
        correlation_id=run.correlation_id,
        occurred_at=captured_at,
        event_idempotency_hash=_digest({"event": code, "approval": str(approval.id)}),
    )
    session.flush()
    if terminal_error is not None:
        raise terminal_error(message)
    return approval, True
