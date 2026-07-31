"""Typed contract models for project export format version 1."""

from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FORMAT_NAME = "second-brain-project-export"
FORMAT_VERSION = 1


class ExportError(Exception):
    """Safe base error for an export failure."""


class ProjectNotFoundError(ExportError):
    """The requested Project does not exist."""


class ExportIntegrityError(ExportError):
    """The selected rows do not form a self-contained export graph."""


class ExportFile(BaseModel):
    """Integrity metadata for one data file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    byte_length: int = Field(ge=0)
    row_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or "\\" in value
            or path.is_absolute()
            or ".." in path.parts
            or str(path) != value
        ):
            raise ValueError("archive path must be a safe POSIX relative path")
        return value


class ExportOptions(BaseModel):
    """Options required to interpret this export."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row_order: str = "uuid_ascending"
    timestamp_format: str = "UTC ISO-8601 with Z suffix"
    newline: str = "LF"
    encoding: str = "UTF-8"


class ExportManifest(BaseModel):
    """Top-level format-versioned manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format_name: str = Field(default=FORMAT_NAME, pattern=f"^{FORMAT_NAME}$")
    format_version: int = Field(default=FORMAT_VERSION, ge=1, le=1)
    exported_at: datetime
    source_alembic_revision: str
    project_id: UUID
    project_name: str
    entity_counts: dict[str, int]
    files: list[ExportFile]
    export_options: ExportOptions = Field(default_factory=ExportOptions)

    @field_validator("exported_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("exported_at must be timezone-aware")
        return value


class ExportResult(BaseModel):
    """Safe command summary for a completed bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    output_path: str
    project_id: UUID
    project_name: str
    entity_counts: dict[str, int]
    package_byte_size: int
    package_sha256: str
    source_alembic_revision: str
    format_version: int = FORMAT_VERSION
