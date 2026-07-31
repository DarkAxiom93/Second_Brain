"""Typed, secret-safe operational diagnostic results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DiagnosticStatus = Literal["passed", "failed", "warning"]
SAFE_METADATA_KEYS = {
    "actual",
    "database",
    "dimensions",
    "expected",
    "head",
    "host",
    "model",
    "port",
    "provider",
    "revision",
    "version",
}
FORBIDDEN_TEXT = ("password", "secret", "token", "api_key", "://", "@")


class DiagnosticCheck(BaseModel):
    """One bounded result with deliberately restricted metadata."""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    category: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    status: DiagnosticStatus
    message: str = Field(min_length=1, max_length=240)
    metadata: dict[str, str | int | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_safe_output(self) -> "DiagnosticCheck":
        if not set(self.metadata).issubset(SAFE_METADATA_KEYS):
            raise ValueError("diagnostic metadata contains an unsupported key")
        text = self.message.lower()
        values = " ".join(str(value).lower() for value in self.metadata.values())
        if any(marker in text or marker in values for marker in FORBIDDEN_TEXT):
            raise ValueError("diagnostic output contains potentially sensitive text")
        return self


class DiagnosticsResult(BaseModel):
    """Complete deterministic result for one captured instant."""

    model_config = ConfigDict(extra="forbid")

    diagnostics_status: Literal["healthy", "unhealthy"]
    captured_at: datetime
    target_database: Literal["second_brain", "second_brain_test"]
    checks: list[DiagnosticCheck]
    aggregate_counts: dict[str, int]
    warning_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_aggregation(self) -> "DiagnosticsResult":
        ordered = sorted(self.checks, key=lambda item: (item.category, item.check_id))
        if self.checks != ordered:
            raise ValueError("diagnostic checks must use deterministic ordering")
        warnings = sum(item.status == "warning" for item in self.checks)
        failures = sum(item.status == "failed" for item in self.checks)
        expected = "unhealthy" if failures else "healthy"
        if (
            self.warning_count != warnings
            or self.failure_count != failures
            or self.diagnostics_status != expected
        ):
            raise ValueError("diagnostic summary does not match checks")
        if any(value < 0 for value in self.aggregate_counts.values()):
            raise ValueError("aggregate counts cannot be negative")
        return self


def build_result(
    *,
    captured_at: datetime,
    target_database: Literal["second_brain", "second_brain_test"],
    checks: list[DiagnosticCheck],
    aggregate_counts: dict[str, int] | None = None,
) -> DiagnosticsResult:
    """Sort checks and derive the status without allowing hidden failures."""

    ordered = sorted(checks, key=lambda item: (item.category, item.check_id))
    failures = sum(item.status == "failed" for item in ordered)
    return DiagnosticsResult(
        diagnostics_status="unhealthy" if failures else "healthy",
        captured_at=captured_at,
        target_database=target_database,
        checks=ordered,
        aggregate_counts=aggregate_counts or {},
        warning_count=sum(item.status == "warning" for item in ordered),
        failure_count=failures,
    )
