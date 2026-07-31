"""Orchestration for the deterministic read-only maintenance audit."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.memory_maintenance.models import (
    MEMORY_STATUSES,
    AuditCategory,
    MemoryMaintenanceAudit,
)
from app.repositories import memory_maintenance as repository


def run_memory_maintenance_audit(
    session: Session,
    *,
    expected_embedding_identity: tuple[str, str, int],
    detail_limit: int = 100,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MemoryMaintenanceAudit:
    """Report maintenance conditions without flushing or committing."""

    if not 0 <= detail_limit <= 1000:
        raise ValueError("detail limit must be between 0 and 1000")
    captured_at = clock()
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("audit timestamp must be timezone-aware")
    captured_at = captured_at.astimezone(UTC)
    total, assigned, raw_statuses = repository.aggregate_counts(session)
    categories = repository.category_counts_and_ids(
        session,
        captured_at=captured_at,
        detail_limit=detail_limit,
        provider=expected_embedding_identity[0],
        model=expected_embedding_identity[1],
        dimensions=expected_embedding_identity[2],
    )

    def result(name: str) -> AuditCategory:
        count, ids = categories[name]
        return AuditCategory(count=count, memory_ids=ids, truncated=count > len(ids))

    return MemoryMaintenanceAudit(
        captured_at=captured_at,
        detail_limit=detail_limit,
        total_memories=total,
        project_assigned_memories=assigned,
        unassigned_memories=total - assigned,
        counts_by_status={
            status: raw_statuses.get(status, 0) for status in MEMORY_STATUSES
        },
        active_missing_embedding=result("active_missing_embedding"),
        active_stale_embedding=result("active_stale_embedding"),
        active_expiration_due=result("active_expiration_due"),
        active_future_expiration=result("active_future_expiration"),
        expired_missing_expires_at=result("expired_missing_expires_at"),
        non_active_with_embedding=result("non_active_with_embedding"),
    )
