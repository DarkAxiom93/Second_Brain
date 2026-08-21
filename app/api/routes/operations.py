"""Safe local operations endpoints."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

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
from app.project_export.models import (
    CURRENT_DATABASE_REVISION,
    ExportError,
    ProjectNotFoundError,
)
from app.project_export.service import export_project
from app.project_import.models import ImportBundleError, ImportConflictError
from app.project_import.service import MAX_ARCHIVE_BYTES, import_project, load_bundle
from app.schemas.operations import (
    MaintenanceFindingRead,
    OperationsDiagnosticsRead,
    OperationsMaintenanceAuditRead,
    ProjectImportExecuteRead,
    ProjectImportPlanRead,
    PublicDiagnosticCheck,
)

router = APIRouter(prefix="/operations", tags=["operations"])

OPERATION_HEADER = "X-Second-Brain-Operation"
EXPORT_OPERATION = "project-export-v1"
VALIDATE_OPERATION = "project-import-validate-v1"
EXECUTE_OPERATION = "project-import-execute-v1"
BUNDLE_MEDIA_TYPE = "application/vnd.second-brain.project-export"
SAFE_HEADERS = {"Cache-Control": "no-store"}


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


def _require_current_database_revision(session: Session) -> str:
    revision = session.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != CURRENT_DATABASE_REVISION:
        raise _database_unavailable()
    return CURRENT_DATABASE_REVISION


def _protect_local_operation(
    request: Request, supplied: str | None, expected: str
) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1"} or supplied != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operation forbidden",
            headers=SAFE_HEADERS,
        )


def _cleanup_exact(path: Path) -> None:
    path.unlink(missing_ok=True)


async def _receive_bundle(request: Request) -> Path:
    content_type = (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if content_type not in {
        BUNDLE_MEDIA_TYPE,
        "application/octet-stream",
        "application/zip",
    }:
        raise HTTPException(
            status_code=415,
            detail="unsupported bundle content type",
            headers=SAFE_HEADERS,
        )
    descriptor, name = tempfile.mkstemp(
        prefix="second-brain-upload-", suffix=".sbexport"
    )
    path = Path(name)
    size = 0
    try:
        with os.fdopen(descriptor, "wb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="bundle exceeds size limit",
                        headers=SAFE_HEADERS,
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(
                status_code=400, detail="bundle is empty", headers=SAFE_HEADERS
            )
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _import_plan(path: Path, session: Session) -> ProjectImportPlanRead:
    manifest, _, bundle_hash = load_bundle(path)
    try:
        result = import_project(session, path, execute=False)
        conflicts: list[str] = []
    except ImportConflictError as exc:
        conflicts = [str(exc)]
        result = None
    return ProjectImportPlanRead(
        importable=result is not None,
        format_name=manifest.format_name,
        format_version=manifest.format_version,
        project_id=manifest.project_id,
        project_name=manifest.project_name,
        source_alembic_revision=manifest.source_alembic_revision,
        entity_counts=manifest.entity_counts,
        bundle_sha256=bundle_hash,
        conflicts=conflicts,
        warnings=[],
        conflict_count=len(conflicts),
        warning_count=0,
    )


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


@router.post(
    "/project-exports/{project_id}",
    responses={
        404: {"description": "Project not found"},
        403: {"description": "Forbidden"},
    },
)
def project_export(
    project_id: UUID,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    operation: Annotated[str | None, Header(alias=OPERATION_HEADER)] = None,
) -> FileResponse:
    """Stream one deterministic private bundle and remove its exact temporary file."""

    _protect_local_operation(request, operation, EXPORT_OPERATION)
    _validate_development_target(settings)
    descriptor, name = tempfile.mkstemp(
        prefix="second-brain-export-", suffix=".sbexport"
    )
    os.close(descriptor)
    output = Path(name)
    output.unlink()
    try:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        _make_read_only(session)
        if session.scalar(text("SELECT current_database()")) != "second_brain":
            raise _database_unavailable()
        revision = _require_current_database_revision(session)
        export_project(
            session,
            project_id,
            output,
            source_alembic_revision=revision,
        )
        session.rollback()
    except ProjectNotFoundError:
        session.rollback()
        _cleanup_exact(output)
        raise HTTPException(status_code=404, detail="project not found") from None
    except (ExportError, OSError):
        session.rollback()
        _cleanup_exact(output)
        raise HTTPException(status_code=500, detail="project export failed") from None
    except Exception:
        session.rollback()
        _cleanup_exact(output)
        raise
    filename = f"project-{project_id}.sbexport"
    return FileResponse(
        output,
        media_type=BUNDLE_MEDIA_TYPE,
        filename=filename,
        headers={**SAFE_HEADERS, "X-Content-Type-Options": "nosniff"},
        background=BackgroundTask(_cleanup_exact, output),
    )


@router.post("/project-imports/validate", response_model=ProjectImportPlanRead)
async def project_import_validate(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    operation: Annotated[str | None, Header(alias=OPERATION_HEADER)] = None,
) -> ProjectImportPlanRead:
    """Validate a raw bundle and return a content-free target plan."""

    _protect_local_operation(request, operation, VALIDATE_OPERATION)
    response.headers.update(SAFE_HEADERS)
    _validate_development_target(settings)
    path = await _receive_bundle(request)
    try:
        _make_read_only(session)
        if session.scalar(text("SELECT current_database()")) != "second_brain":
            raise _database_unavailable()
        _require_current_database_revision(session)
        return _import_plan(path, session)
    except ImportBundleError:
        raise HTTPException(
            status_code=400,
            detail="invalid project export bundle",
            headers=SAFE_HEADERS,
        ) from None
    except SQLAlchemyError:
        raise _database_unavailable() from None
    finally:
        session.rollback()
        _cleanup_exact(path)


@router.post("/project-imports/execute", response_model=ProjectImportExecuteRead)
async def project_import_execute(
    request: Request,
    response: Response,
    expected_project_id: UUID,
    expected_bundle_sha256: Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")],
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    operation: Annotated[str | None, Header(alias=OPERATION_HEADER)] = None,
) -> ProjectImportExecuteRead:
    """Revalidate and atomically import one exactly confirmed raw bundle."""

    _protect_local_operation(request, operation, EXECUTE_OPERATION)
    response.headers.update(SAFE_HEADERS)
    _validate_development_target(settings)
    path = await _receive_bundle(request)
    try:
        manifest, _, actual_hash = load_bundle(path)
        if actual_hash != expected_bundle_sha256:
            raise HTTPException(
                status_code=409,
                detail="bundle confirmation mismatch",
                headers=SAFE_HEADERS,
            )
        if manifest.project_id != expected_project_id:
            raise HTTPException(
                status_code=409,
                detail="Project confirmation mismatch",
                headers=SAFE_HEADERS,
            )
        if session.scalar(text("SELECT current_database()")) != "second_brain":
            raise _database_unavailable()
        _require_current_database_revision(session)
        result = import_project(
            session, path, execute=True, expected_project_id=expected_project_id
        )
        session.commit()
        return ProjectImportExecuteRead.model_validate(result, from_attributes=True)
    except ImportBundleError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="invalid project export bundle",
            headers=SAFE_HEADERS,
        ) from None
    except ImportConflictError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="project import conflicts with target",
            headers=SAFE_HEADERS,
        ) from None
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="project import conflicts with target",
            headers=SAFE_HEADERS,
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise _database_unavailable() from None
    except Exception:
        session.rollback()
        raise
    finally:
        _cleanup_exact(path)
