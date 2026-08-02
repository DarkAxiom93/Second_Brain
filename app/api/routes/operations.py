"""Read-only, aggregate-only local operations endpoints."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.dependencies import get_db_session
from app.diagnostics.models import build_result
from app.diagnostics.service import (
    inspect_database,
    inspect_provider_configuration,
    repository_head,
    validate_database_target,
)
from app.memory_maintenance.service import run_memory_maintenance_audit
from app.schemas.operations import (
    MaintenanceFindingRead,
    OperationsDiagnosticsRead,
    OperationsMaintenanceAuditRead,
    PublicDiagnosticCheck,
)

router = APIRouter(prefix="/operations", tags=["operations"])


def _database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="database unavailable",
    )


def _make_read_only(session: Session) -> None:
    session.execute(text("SET TRANSACTION READ ONLY"))


def _validate_development_target(settings: Settings) -> None:
    _, checks = validate_database_target(settings.database_url, "development")
    if any(item.status == "failed" for item in checks):
        raise _database_unavailable()


@router.get(
    "/diagnostics",
    response_model=OperationsDiagnosticsRead,
    responses={503: {"description": "Database unavailable"}},
)
def diagnostics(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationsDiagnosticsRead:
    """Return safe checks and aggregate counts without diagnostic metadata."""

    captured_at = datetime.now(UTC)
    _validate_development_target(settings)
    try:
        _, target_checks = validate_database_target(
            settings.database_url, "development"
        )
        head, head_checks = repository_head(Path.cwd())
        _make_read_only(session)
        database_checks, counts = inspect_database(
            session.connection(), expected_database="second_brain", head=head
        )
    except SQLAlchemyError:
        raise _database_unavailable() from None

    result = build_result(
        captured_at=captured_at,
        target_database="second_brain",
        checks=(
            target_checks
            + inspect_provider_configuration(settings)
            + head_checks
            + database_checks
        ),
        aggregate_counts=counts,
    )
    return OperationsDiagnosticsRead(
        diagnostics_status=result.diagnostics_status,
        captured_at=result.captured_at,
        warning_count=result.warning_count,
        failure_count=result.failure_count,
        checks=[
            PublicDiagnosticCheck(
                check_id=item.check_id,
                category=item.category,
                status=item.status,
                message=item.message,
            )
            for item in result.checks
        ],
        aggregate_counts=dict(sorted(result.aggregate_counts.items())),
    )


@router.get(
    "/maintenance-audit",
    response_model=OperationsMaintenanceAuditRead,
    responses={503: {"description": "Database unavailable"}},
)
def maintenance_audit(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationsMaintenanceAuditRead:
    """Return advisory aggregate findings without bounded Memory ID details."""

    _validate_development_target(settings)
    try:
        _make_read_only(session)
        if session.scalar(text("SELECT current_database()")) != "second_brain":
            raise _database_unavailable()
        report = run_memory_maintenance_audit(
            session,
            expected_embedding_identity=(
                settings.embedding_provider,
                settings.embedding_model,
                settings.embedding_dimensions,
            ),
            detail_limit=0,
        )
    except SQLAlchemyError:
        raise _database_unavailable() from None

    names = (
        "active_expiration_due",
        "active_future_expiration",
        "active_missing_embedding",
        "active_stale_embedding",
        "expired_missing_expires_at",
        "non_active_with_embedding",
    )
    return OperationsMaintenanceAuditRead(
        captured_at=report.captured_at,
        total_memories=report.total_memories,
        project_assigned_memories=report.project_assigned_memories,
        unassigned_memories=report.unassigned_memories,
        counts_by_status=dict(sorted(report.counts_by_status.items())),
        findings=[
            MaintenanceFindingRead(finding_id=name, count=getattr(report, name).count)
            for name in names
        ],
    )
