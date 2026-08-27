"""Manual Agent Run create, read, list, and cancel endpoints."""

import uuid
from collections.abc import Callable
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_planning import service as planning_service
from app.agent_planning.dependencies import (
    configured_embedding_provider_available,
    get_planning_provider,
)
from app.agent_planning.provider import (
    PlanningOutputInvalidError,
    PlanningProvider,
    PlanningProviderRequestError,
    PlanningProviderTimeoutError,
    PlanningProviderUnavailableError,
)
from app.agent_runs import approvals, executor, faults, service
from app.automations.catalog import is_reserved_automation_agent_identity
from app.curator import service as curator_service
from app.curator.catalog import CURATOR_KIND, curator_definition, is_curator
from app.curator.dependencies import get_curator_provider
from app.curator.provider import (
    CuratorOutputInvalidError,
    CuratorProvider,
    CuratorProviderError,
    CuratorProviderRequestError,
    CuratorProviderResult,
    CuratorProviderTimeoutError,
    CuratorProviderUnavailableError,
)
from app.daily_brief import service as daily_brief_service
from app.db.dependencies import get_db_session
from app.embeddings import EmbeddingProvider, get_embedding_provider
from app.models.agent_runtime import (
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)
from app.repositories import agent_runtime as repository
from app.research import service as research_service
from app.research.catalog import RESEARCH_KIND, is_research, research_definition
from app.research.dependencies import get_research_provider
from app.research.provider import (
    ResearchOutputInvalidError,
    ResearchProvider,
    ResearchProviderError,
    ResearchProviderRequestError,
    ResearchProviderResult,
    ResearchProviderTimeoutError,
    ResearchProviderUnavailableError,
)
from app.schemas.agent_run import (
    AgentRunCancel,
    AgentRunCreate,
    AgentRunExecuteRequest,
    AgentRunExecutionRead,
    AgentRunPlanRead,
    AgentRunPlanRequest,
    AgentRunRead,
    AgentRunState,
    AgentStepExecutionRead,
    AgentStepRead,
    ApprovalRequestCreate,
    ApprovalRequestRead,
    ApprovalRequestStatus,
    ApprovalReview,
    CuratorResultRead,
    ResearchResultRead,
)

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])
approval_router = APIRouter(prefix="/approval-requests", tags=["approval-requests"])


def planning_provider_resolver() -> Callable[[], PlanningProvider]:
    return get_planning_provider


def configured_provider_availability() -> Callable[[], bool]:
    return configured_embedding_provider_available


def embedding_provider_resolver() -> Callable[[], EmbeddingProvider]:
    return get_embedding_provider


def research_provider_resolver() -> Callable[[], ResearchProvider]:
    return get_research_provider


def curator_provider_resolver() -> Callable[[], CuratorProvider]:
    return get_curator_provider


def _error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _validate_idempotency_key(value: str) -> str:
    if (
        not 1 <= len(value) <= 128
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) > 126 for character in value)
    ):
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid Idempotency-Key")
    return value


def _approval_projection(
    session: Session, approval: ApprovalRequest
) -> ApprovalRequestRead:
    step = repository.get_agent_step(session, approval.run_id, approval.step_id)
    if step is None:
        raise approvals.NotFoundError("agent step not found")
    return ApprovalRequestRead(
        id=approval.id,
        run_id=approval.run_id,
        step_ordinal=step.ordinal,
        action_type=approval.action_type,
        target_type=approval.target_type,
        target_id=approval.target_public_id,
        target_version=approval.target_version,
        proposed_input=approval.normalized_input,
        preview=approval.preview,
        evidence_references=approval.evidence_references,
        risk_classification=approval.risk_classification,
        status=cast(ApprovalRequestStatus, approval.status),
        created_at=approval.created_at,
        expires_at=approval.expires_at,
        reviewed_at=approval.reviewed_at,
    )


@router.post(
    "/{run_id}/approval-requests",
    response_model=ApprovalRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_approval_request(
    run_id: uuid.UUID,
    request: ApprovalRequestCreate,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ApprovalRequestRead:
    try:
        approval, created = approvals.create_proposal(
            session,
            run_id=run_id,
            step_ordinal=request.step_ordinal,
            action_type=request.action_type,
            target_id=request.target_id,
            proposed_input=request.proposed_input,
        )
        session.commit()
        session.refresh(approval)
        if not created:
            response.status_code = status.HTTP_200_OK
        return _approval_projection(session, approval)
    except approvals.NotFoundError as exc:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except approvals.InvalidProposalError as exc:
        session.rollback()
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "proposal creation conflict") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.get("/{run_id}/approval-requests", response_model=list[ApprovalRequestRead])
def list_approval_requests(
    run_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ApprovalRequestRead]:
    try:
        if repository.get_agent_run(session, run_id) is None:
            raise approvals.NotFoundError("agent run not found")
        rows = repository.list_approval_requests(
            session, run_id, limit=limit, offset=offset
        )
        return [_approval_projection(session, row) for row in rows]
    except approvals.NotFoundError as exc:
        raise _error(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except SQLAlchemyError:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@approval_router.get("/{approval_id}", response_model=ApprovalRequestRead)
def get_approval_request(
    approval_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> ApprovalRequestRead:
    try:
        approval = repository.get_approval_request_by_id(session, approval_id)
        if approval is None:
            raise approvals.NotFoundError("approval request not found")
        return _approval_projection(session, approval)
    except approvals.NotFoundError as exc:
        raise _error(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except SQLAlchemyError:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@approval_router.post("/{approval_id}/review", response_model=ApprovalRequestRead)
def review_approval_request(
    approval_id: uuid.UUID,
    request: ApprovalReview,
    session: Annotated[Session, Depends(get_db_session)],
) -> ApprovalRequestRead:
    try:
        approval, _changed = approvals.review_proposal(
            session, approval_id=approval_id, decision=request.decision
        )
        session.commit()
        session.refresh(approval)
        return _approval_projection(session, approval)
    except (approvals.ExpiredApprovalError, approvals.StaleApprovalError) as exc:
        # Expiry/staleness is a durable terminal transition and must commit.
        try:
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from None
        raise _error(status.HTTP_409_CONFLICT, str(exc)) from None
    except approvals.NotFoundError as exc:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except approvals.ReviewConflictError as exc:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, str(exc)) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("", response_model=AgentRunRead, status_code=status.HTTP_201_CREATED)
def create_agent_run(
    request: AgentRunCreate,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AgentRun:
    """Create one Run and its sequence-zero event atomically."""

    if (request.agent_kind, request.agent_version) == ("daily_brief", "1"):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "agent definition unsupported"
        )
    if is_reserved_automation_agent_identity(request.agent_kind, request.agent_version):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "agent definition unsupported"
        )
    if (
        request.agent_kind == RESEARCH_KIND
        and research_definition(request.agent_kind, request.agent_version) is None
    ):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "unsupported Research Agent version"
        )
    if (
        request.agent_kind == CURATOR_KIND
        and curator_definition(request.agent_kind, request.agent_version) is None
    ):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "unsupported Memory Curator Agent version",
        )
    key_hash = service.hash_idempotency_key(_validate_idempotency_key(idempotency_key))
    fingerprint = service.normalized_request_fingerprint(request)
    try:
        result = service.create_run(
            session,
            request,
            idempotency_key_hash=key_hash,
            fingerprint=fingerprint,
        )
        session.commit()
        session.refresh(result.run)
    except service.ProjectNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "project not found") from None
    except service.IdempotencyConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT,
            "idempotency key already used with a different request",
        ) from None
    except service.AgentRunCapacityError:
        session.rollback()
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "active Agent Run capacity reached",
        ) from None
    except IntegrityError:
        # A concurrent creator may win the unique hash constraint after our
        # initial lookup. Roll back the failed transaction before resolving it.
        session.rollback()
        try:
            replay_result = service.resolve_create_replay(
                session,
                idempotency_key_hash=key_hash,
                fingerprint=fingerprint,
            )
            if replay_result is None:
                raise _error(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
                )
            result = replay_result
        except service.IdempotencyConflictError:
            session.rollback()
            raise _error(
                status.HTTP_409_CONFLICT,
                "idempotency key already used with a different request",
            ) from None
        except SQLAlchemyError:
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None

    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result.run


@router.get("", response_model=list[AgentRunRead])
def list_agent_runs(
    session: Annotated[Session, Depends(get_db_session)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    unassigned: Annotated[bool, Query()] = False,
    state_filter: Annotated[AgentRunState | None, Query(alias="state")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AgentRun]:
    if project_id is not None and unassigned:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "project_id and unassigned=true are mutually exclusive",
        )
    try:
        return repository.list_agent_runs(
            session,
            project_id=project_id,
            unassigned=unassigned,
            state=None if state_filter is None else state_filter.value,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.get("/{run_id}", response_model=AgentRunRead)
def get_agent_run(
    run_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRun:
    try:
        run = repository.get_agent_run(session, run_id)
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None
    if run is None:
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found")
    return run


def _plan_projection(run: AgentRun, steps: list[AgentStep]) -> AgentRunPlanRead:
    return AgentRunPlanRead(
        run=AgentRunRead.model_validate(run),
        goal_summary=run.goal_summary,
        steps=[
            AgentStepRead(
                ordinal=step.ordinal,
                purpose=step.purpose,
                tool_name=step.tool_name or "",
                tool_version=int(step.tool_version or "0"),
                normalized_input=step.normalized_input,
                expected_evidence=step.expected_evidence,
                success_condition=step.success_condition,
                stop_condition=step.stop_condition,
            )
            for step in steps
        ],
    )


def _execution_projection(
    run: AgentRun,
    steps: list[AgentStep],
    invocations: list[ToolInvocation],
    research_result: dict[str, object] | None = None,
    curator_result: dict[str, object] | None = None,
    daily_brief_result: dict[str, object] | None = None,
) -> AgentRunExecutionRead:
    by_step = {item.step_id: item for item in invocations}
    return AgentRunExecutionRead(
        run=AgentRunRead.model_validate(run),
        research_result=(
            None
            if research_result is None
            else ResearchResultRead.model_validate(research_result)
        ),
        curator_result=(
            None
            if curator_result is None
            else CuratorResultRead.model_validate(curator_result)
        ),
        daily_brief_result=(
            None
            if daily_brief_result is None
            else ResearchResultRead.model_validate(daily_brief_result)
        ),
        steps=[
            AgentStepExecutionRead(
                ordinal=step.ordinal,
                purpose=step.purpose,
                tool_name=step.tool_name or "",
                tool_version=int(step.tool_version or "0"),
                status=step.status,
                invocation_status=(
                    None if step.id not in by_step else by_step[step.id].status
                ),
                safe_result_summary=(
                    None
                    if step.id not in by_step
                    else by_step[step.id].safe_result_summary
                ),
                evidence_references=(
                    []
                    if step.id not in by_step
                    else by_step[step.id].evidence_references
                ),
                safe_error_code=(
                    None if step.id not in by_step else by_step[step.id].safe_error_code
                ),
            )
            for step in steps
        ],
    )


def _load_execution(session: Session, run_id: uuid.UUID) -> AgentRunExecutionRead:
    run = repository.get_agent_run(session, run_id)
    if run is None:
        raise service.AgentRunNotFoundError
    steps = repository.list_agent_steps(session, run_id, limit=13)
    invocations = repository.list_step_invocations(session, run_id)
    return _execution_projection(
        run,
        steps,
        list(invocations),
        research_service.get_result(session, run.id),
        curator_service.get_result(session, run.id),
        daily_brief_service.get_result(session, run.id),
    )


@router.get("/{run_id}/execution", response_model=AgentRunExecutionRead)
def get_agent_run_execution(
    run_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRunExecutionRead:
    try:
        return _load_execution(session, run_id)
    except service.AgentRunNotFoundError:
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/{run_id}/execute", response_model=AgentRunExecutionRead)
def execute_agent_run(
    run_id: uuid.UUID,
    request: AgentRunExecuteRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_provider: Annotated[
        Callable[[], EmbeddingProvider], Depends(embedding_provider_resolver)
    ],
    provider_available: Annotated[
        Callable[[], bool], Depends(configured_provider_availability)
    ],
    resolve_research_provider: Annotated[
        Callable[[], ResearchProvider], Depends(research_provider_resolver)
    ],
    resolve_curator_provider: Annotated[
        Callable[[], CuratorProvider], Depends(curator_provider_resolver)
    ],
) -> AgentRunExecutionRead:
    """Claim and synchronously execute one complete frozen read-only plan."""

    try:
        claim = executor.claim_execution(
            session, run_id, expected_revision=request.expected_revision
        )
        session.commit()
        if claim is None:
            return _load_execution(session, run_id)
        faults.fire(faults.FaultPoint.AFTER_RUN_CLAIM)
    except service.AgentRunNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunRevisionConflictError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent run revision conflict") from None
    except executor.ExecutionRegistryVersionError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run registry version unsupported"
        ) from None
    except executor.ExecutionAgentVersionError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent definition unsupported") from None
    except executor.ExecutionPlanInvalidError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent run plan invalid") from None
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None

    collected: list[research_service.CollectedEvidence] = []
    research_run = is_research(claim.agent_kind, claim.agent_version)
    curator_run = is_curator(claim.agent_kind, claim.agent_version)
    evidence_agent = research_run or curator_run
    while True:
        try:
            reserved = executor.reserve_next(
                session, claim, provider_available=provider_available()
            )
            session.commit()
        except (executor.ExecutionPlanInvalidError, SQLAlchemyError):
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "execution unavailable"
            ) from None
        if reserved is None:
            break
        step, invocation, timeout_seconds = reserved
        step_id = step.id
        invocation_id = invocation.id
        observed: list[research_service.ObservedEvidence] = []

        def capture_research_evidence(
            entity_type: str,
            row: object,
            target: list[research_service.ObservedEvidence] = observed,
        ) -> None:
            target.append(research_service.observe_entity(entity_type, row))

        output, safe_error = executor.call_reserved_tool(
            session,
            claim,
            step,
            invocation,
            timeout_seconds,
            resolve_provider,
            capture_research_evidence if evidence_agent else None,
        )
        references: list[dict[str, object]] | None = None
        if evidence_agent and output is not None and safe_error is None:
            try:
                evidence_run = repository.get_agent_run(session, claim.run_id)
                if evidence_run is None:
                    raise research_service.ResearchValidationError
                new_evidence = research_service.collect_output(
                    run=evidence_run,
                    step=step,
                    invocation=invocation,
                    output=output,
                    offset=len(collected),
                    observed=observed,
                )
                collected.extend(new_evidence)
                references = research_service.evidence_references(new_evidence)
            except research_service.ResearchValidationError:
                safe_error = "research_evidence_invalid"
        # End the read Tool's transaction before entering finalization.
        session.rollback()
        try:
            faults.fire(faults.FaultPoint.BEFORE_INVOCATION_FINALIZATION)
            succeeded = executor.finalize_invocation(
                session,
                claim,
                step_id=step_id,
                invocation_id=invocation_id,
                output=output,
                safe_error_code=safe_error,
                evidence_references=references,
            )
            session.commit()
            faults.fire(faults.FaultPoint.AFTER_INVOCATION_FINALIZATION)
        except SQLAlchemyError:
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from None
        if not succeeded:
            break

    if research_run:
        active = research_service.claim_synthesis(session, claim.run_id)
        session.commit()
        if active:
            try:
                research_result = (
                    ResearchProviderResult(
                        status="insufficient_evidence",
                        claims=[],
                        insufficiency=(
                            "The collected local evidence is insufficient to "
                            "answer safely."
                        ),
                    )
                    if not collected
                    else resolve_research_provider().synthesize(
                        goal=claim.goal_summary,
                        evidence=[item.provider_value() for item in collected],
                    )
                )
                research_service.persist_result(
                    session,
                    run_id=claim.run_id,
                    evidence=collected,
                    result=research_result,
                )
                session.commit()
            except ResearchProviderUnavailableError:
                session.rollback()
                research_service.fail_result(
                    session, claim.run_id, "research_provider_unavailable"
                )
                session.commit()
            except ResearchProviderTimeoutError:
                session.rollback()
                research_service.fail_result(
                    session, claim.run_id, "research_provider_timeout"
                )
                session.commit()
            except ResearchProviderRequestError:
                session.rollback()
                research_service.fail_result(
                    session, claim.run_id, "research_provider_failed"
                )
                session.commit()
            except (
                ResearchOutputInvalidError,
                ResearchProviderError,
                research_service.ResearchValidationError,
            ):
                session.rollback()
                research_service.fail_result(
                    session, claim.run_id, "research_result_invalid"
                )
                session.commit()

    if curator_run:
        active = curator_service.claim_synthesis(session, claim.run_id)
        session.commit()
        if active:
            try:
                curator_result = (
                    CuratorProviderResult(findings=[], proposals=[])
                    if not collected
                    else resolve_curator_provider().synthesize(
                        goal=claim.goal_summary,
                        evidence=[item.provider_value() for item in collected],
                    )
                )
                curator_service.persist_result(
                    session,
                    run_id=claim.run_id,
                    evidence=collected,
                    result=curator_result,
                )
                session.commit()
            except CuratorProviderUnavailableError:
                session.rollback()
                curator_service.fail_result(
                    session, claim.run_id, "curator_provider_unavailable"
                )
                session.commit()
            except CuratorProviderTimeoutError:
                session.rollback()
                curator_service.fail_result(
                    session, claim.run_id, "curator_provider_timeout"
                )
                session.commit()
            except CuratorProviderRequestError:
                session.rollback()
                curator_service.fail_result(
                    session, claim.run_id, "curator_provider_failed"
                )
                session.commit()
            except (
                CuratorOutputInvalidError,
                CuratorProviderError,
                curator_service.CuratorValidationError,
            ):
                session.rollback()
                curator_service.fail_result(
                    session, claim.run_id, "curator_result_invalid"
                )
                session.commit()
    try:
        completed = executor.complete_run(session, claim)
        session.commit()
        if completed is not None:
            session.refresh(completed)
        return _load_execution(session, run_id)
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.get("/{run_id}/plan", response_model=AgentRunPlanRead)
def get_agent_run_plan(
    run_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRunPlanRead:
    try:
        run, steps = planning_service.get_frozen_plan(session, run_id)
        return _plan_projection(run, list(steps))
    except service.AgentRunNotFoundError:
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunTransitionConflictError:
        raise _error(status.HTTP_409_CONFLICT, "agent run plan not available") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/{run_id}/plan", response_model=AgentRunPlanRead)
def plan_agent_run(
    run_id: uuid.UUID,
    request: AgentRunPlanRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_provider: Annotated[
        Callable[[], PlanningProvider], Depends(planning_provider_resolver)
    ],
    provider_available: Annotated[
        Callable[[], bool], Depends(configured_provider_availability)
    ],
) -> AgentRunPlanRead:
    """Claim, externally plan, validate, and atomically freeze one Run."""

    try:
        claim = planning_service.claim_planning(
            session, run_id, expected_revision=request.expected_revision
        )
        session.commit()
        if claim is None:
            run, steps = planning_service.get_frozen_plan(session, run_id)
            return _plan_projection(run, list(steps))
    except service.AgentRunNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunRevisionConflictError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent run revision conflict") from None
    except planning_service.AgentRunRegistryVersionError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run registry version unsupported"
        ) from None
    except planning_service.AgentDefinitionUnsupportedError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent definition unsupported") from None
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None

    error_code: str | None = None
    error_detail: str | None = None
    try:
        provider = resolve_provider()
        result = provider.plan(planning_service.build_context(claim))
        validated_steps = planning_service.validate_plan(
            claim,
            result,
            configured_provider_available=provider_available(),
        )
    except PlanningProviderUnavailableError:
        error_code, error_detail = (
            "planning_provider_unavailable",
            "planning provider unavailable",
        )
    except PlanningProviderTimeoutError:
        error_code, error_detail = (
            "planning_provider_timeout",
            "planning provider failed",
        )
    except PlanningProviderRequestError:
        error_code, error_detail = (
            "planning_provider_failed",
            "planning provider failed",
        )
    except (PlanningOutputInvalidError, planning_service.PlanningOutputRejectedError):
        error_code, error_detail = (
            "planning_output_invalid",
            "planning provider returned an invalid plan",
        )
    except planning_service.PlanningPolicyRejectedError:
        error_code, error_detail = (
            "planning_policy_rejected",
            "planning provider returned an invalid plan",
        )

    if error_code is not None:
        try:
            won = planning_service.finalize_failure(
                session, claim, safe_error_code=error_code
            )
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from None
        if not won:
            raise _error(status.HTTP_409_CONFLICT, "agent run transition conflict")
        assert error_detail is not None
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error_code == "planning_provider_unavailable"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise _error(code, error_detail)

    try:
        run = planning_service.finalize_plan(session, claim, validated_steps)
        session.commit()
        session.refresh(run)
        persisted = repository.list_agent_steps(session, run.id, limit=13)
        return _plan_projection(run, list(persisted))
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None


@router.post("/{run_id}/cancel", response_model=AgentRunRead)
def cancel_agent_run(
    run_id: uuid.UUID,
    request: AgentRunCancel,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentRun:
    try:
        run = service.cancel_run(
            session, run_id, expected_revision=request.expected_revision
        )
        session.commit()
        session.refresh(run)
        return run
    except service.AgentRunNotFoundError:
        session.rollback()
        raise _error(status.HTTP_404_NOT_FOUND, "agent run not found") from None
    except service.AgentRunRevisionConflictError:
        session.rollback()
        raise _error(status.HTTP_409_CONFLICT, "agent run revision conflict") from None
    except service.AgentRunTransitionConflictError:
        session.rollback()
        raise _error(
            status.HTTP_409_CONFLICT, "agent run transition conflict"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
        ) from None
