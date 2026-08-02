"""Secret-safe public schemas for read-only operational status."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicDiagnosticCheck(BaseModel):
    """One diagnostic check with all internal metadata removed."""

    model_config = ConfigDict(extra="forbid")

    check_id: str
    category: str
    status: Literal["passed", "warning", "failed"]
    message: str = Field(min_length=1, max_length=240)


class OperationsDiagnosticsRead(BaseModel):
    """Safe public subset of one deterministic diagnostics result."""

    model_config = ConfigDict(extra="forbid")

    diagnostics_status: Literal["healthy", "unhealthy"]
    captured_at: datetime
    warning_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    checks: list[PublicDiagnosticCheck]
    aggregate_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_ordering(self) -> "OperationsDiagnosticsRead":
        if self.checks != sorted(
            self.checks, key=lambda item: (item.category, item.check_id)
        ):
            raise ValueError("diagnostic checks must use deterministic ordering")
        return self


class MaintenanceFindingRead(BaseModel):
    """One established advisory maintenance category and its aggregate count."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    count: int = Field(ge=0)


class OperationsMaintenanceAuditRead(BaseModel):
    """Aggregate-only public maintenance audit without entity identifiers."""

    model_config = ConfigDict(extra="forbid")

    captured_at: datetime
    total_memories: int = Field(ge=0)
    project_assigned_memories: int = Field(ge=0)
    unassigned_memories: int = Field(ge=0)
    counts_by_status: dict[str, int]
    findings: list[MaintenanceFindingRead]

    @model_validator(mode="after")
    def validate_ordering(self) -> "OperationsMaintenanceAuditRead":
        if self.findings != sorted(self.findings, key=lambda item: item.finding_id):
            raise ValueError("maintenance findings must use deterministic ordering")
        return self


class ProjectImportPlanRead(BaseModel):
    """Content-free validation result, including safe target conflicts."""

    model_config = ConfigDict(extra="forbid")

    validation_status: Literal["valid"] = "valid"
    importable: bool
    format_name: str
    format_version: int
    project_id: UUID
    project_name: str
    source_alembic_revision: str
    entity_counts: dict[str, int]
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conflicts: list[str]
    warnings: list[str]
    conflict_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)


class ProjectImportExecuteRead(BaseModel):
    """Safe result for a completed atomic import."""

    model_config = ConfigDict(extra="forbid")

    import_status: Literal["imported"]
    format_name: str
    format_version: int
    project_id: UUID
    project_name: str
    source_alembic_revision: str
    entity_counts: dict[str, int]
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
