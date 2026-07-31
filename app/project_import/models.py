"""Typed results and safe errors for Project import."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImportBundleError(Exception):
    """A bundle is malformed, unsafe, or incompatible."""


class ImportConflictError(Exception):
    """The target already contains a conflicting identity."""


class ImportResult(BaseModel):
    """Non-sensitive result returned by validation or execution."""

    model_config = ConfigDict(frozen=True)

    import_status: Literal["validated", "imported"]
    format_name: str
    format_version: int
    project_id: UUID
    project_name: str
    source_alembic_revision: str
    entity_counts: dict[str, int]
    bundle_sha256: str
