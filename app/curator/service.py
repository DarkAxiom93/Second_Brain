"""Validate and persist evidence-backed Curator advice and proposals."""

import json
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_runs import approvals
from app.agent_runs import service as run_service
from app.curator.catalog import is_curator
from app.curator.provider import CuratorProviderResult
from app.models.agent_runtime import AgentEvent
from app.repositories import agent_runtime as repository
from app.research.service import CollectedEvidence, evidence_is_current
from app.schemas.agent_run import AgentRunState

RESULT_EVENT = "curator.result"
FORBIDDEN = (
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "bearer ",
    "://",
)


class CuratorValidationError(Exception):
    pass


def _safe_text(value: str) -> bool:
    lowered = value.casefold()
    return not any(marker in lowered for marker in FORBIDDEN) and not any(
        ord(c) < 32 and c not in "\n\t" for c in value
    )


def _safe_proposed_value(value: object) -> bool:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _safe_text(key) and _safe_proposed_value(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_safe_proposed_value(item) for item in value)
    return value is None or isinstance(value, (bool, int, float))


def persist_result(
    session: Session,
    *,
    run_id: uuid.UUID,
    evidence: list[CollectedEvidence],
    result: CuratorProviderResult,
) -> bool:
    session.expire_all()
    run = repository.get_agent_run_for_update(session, run_id)
    if (
        run is None
        or not is_curator(run.agent_kind, run.agent_version)
        or run.state != AgentRunState.RUNNING.value
    ):
        raise CuratorValidationError
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
    if not evidence_is_current(session, run, evidence):
        raise CuratorValidationError
    try:
        result = CuratorProviderResult.model_validate(result, strict=True)
    except (ValidationError, TypeError, ValueError):
        raise CuratorValidationError from None
    by_id = {item.evidence_id: item for item in evidence}
    findings: list[dict[str, object]] = []
    for finding in result.findings:
        if not _safe_text(finding.text) or len(finding.evidence) != len(
            set(finding.evidence)
        ):
            raise CuratorValidationError
        refs = [by_id.get(key) for key in finding.evidence]
        if any(item is None for item in refs):
            raise CuratorValidationError
        findings.append(
            {
                "text": finding.text,
                "evidence": [
                    {
                        "entity_type": item.entity_type,
                        "entity_id": str(item.entity_id),
                        "version": item.version,
                    }
                    for item in refs
                    if item is not None
                ],
            }
        )
    proposed: list[dict[str, object]] = []
    proposal_ids: set[uuid.UUID] = set()
    for proposal in result.proposals:
        target = by_id.get(proposal.target_evidence)
        refs = [by_id.get(key) for key in proposal.evidence]
        if (
            target is None
            or target.entity_type != "memory"
            or target not in refs
            or any(item is None for item in refs)
            or len(proposal.evidence) != len(set(proposal.evidence))
            or not _safe_proposed_value(proposal.proposed_input)
        ):
            raise CuratorValidationError
        step = repository.get_agent_step(session, run.id, target.step_id)
        if step is None:
            raise CuratorValidationError
        try:
            approval, _created = approvals.create_curator_proposal(
                session,
                run_id=run.id,
                step_ordinal=step.ordinal,
                action_type=proposal.action_type,
                target_id=target.entity_id,
                expected_target_version=target.version,
                proposed_input=proposal.proposed_input,
                validated_evidence=[
                    {
                        "entity_type": item.entity_type,
                        "id": str(item.entity_id),
                        "version": item.version,
                    }
                    for item in refs
                    if item is not None
                ],
            )
        except approvals.ApprovalError as exc:
            raise CuratorValidationError from exc
        if approval.id in proposal_ids:
            raise CuratorValidationError
        proposal_ids.add(approval.id)
        proposed.append(
            {
                "approval_id": str(approval.id),
                "action_type": approval.action_type,
                "target_id": str(approval.target_public_id),
                "target_version": approval.target_version,
            }
        )
    value: dict[str, object] = {"findings": findings, "proposed_actions": proposed}
    if len(json.dumps(value, separators=(",", ":")).encode()) > 12_000:
        raise CuratorValidationError
    repository.append_agent_event(
        session,
        run_id=run.id,
        event_type=RESULT_EVENT,
        safe_code="curator_result",
        safe_message="bounded Curator advice produced",
        metadata=value,
        correlation_id=run.correlation_id,
        occurred_at=now,
    )
    return True


def claim_synthesis(session: Session, run_id: uuid.UUID) -> bool:
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


def fail_result(session: Session, run_id: uuid.UUID, code: str) -> None:
    run = repository.get_agent_run_for_update(session, run_id)
    if run is not None and run.state == AgentRunState.RUNNING.value:
        run_service.transition_run(
            session,
            run.id,
            expected_state=AgentRunState.RUNNING,
            expected_revision=run.revision,
            new_state=AgentRunState.FAILED,
            safe_error_code=code,
        )


def get_result(session: Session, run_id: uuid.UUID) -> dict[str, Any] | None:
    event = session.scalar(
        select(AgentEvent)
        .where(AgentEvent.run_id == run_id, AgentEvent.event_type == RESULT_EVENT)
        .order_by(AgentEvent.sequence.desc())
        .limit(1)
    )
    return None if event is None else event.safe_metadata
