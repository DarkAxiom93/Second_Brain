"""Typed results for the read-only Memory maintenance audit."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MEMORY_STATUSES = ("active", "superseded", "invalid", "archived", "expired")


class AuditCategory(BaseModel):
    """A complete category count with bounded deterministic details."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    memory_ids: list[uuid.UUID]
    truncated: bool


class MemoryMaintenanceAudit(BaseModel):
    """Complete typed report produced from one captured instant."""

    model_config = ConfigDict(extra="forbid")

    captured_at: datetime
    detail_limit: int = Field(ge=0, le=1000)
    total_memories: int = Field(ge=0)
    project_assigned_memories: int = Field(ge=0)
    unassigned_memories: int = Field(ge=0)
    counts_by_status: dict[str, int]
    active_missing_embedding: AuditCategory
    active_stale_embedding: AuditCategory
    active_expiration_due: AuditCategory
    active_future_expiration: AuditCategory
    expired_missing_expires_at: AuditCategory
    non_active_with_embedding: AuditCategory
