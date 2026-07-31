"""Focused unit coverage for the read-only Memory maintenance audit."""

import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.memory_maintenance.models import MEMORY_STATUSES
from app.memory_maintenance.service import run_memory_maintenance_audit


def test_aggregation_categories_truncation_timestamp_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = datetime(2026, 7, 31, 12, 30, tzinfo=UTC)
    clock = Mock(return_value=captured)
    ids = [uuid.UUID(int=value) for value in (1, 2)]
    aggregate = Mock(return_value=(9, 4, {"active": 5, "expired": 4}))
    categories = Mock(
        return_value={
            "active_missing_embedding": (3, ids),
            "active_stale_embedding": (1, ids[:1]),
            "active_expiration_due": (1, ids[:1]),
            "active_future_expiration": (0, []),
            "expired_missing_expires_at": (2, ids),
            "non_active_with_embedding": (1, ids[:1]),
        }
    )
    monkeypatch.setattr(
        "app.memory_maintenance.service.repository.aggregate_counts", aggregate
    )
    monkeypatch.setattr(
        "app.memory_maintenance.service.repository.category_counts_and_ids",
        categories,
    )

    report = run_memory_maintenance_audit(
        Mock(),
        expected_embedding_identity=("openai", "model", 1536),
        detail_limit=2,
        clock=clock,
    )

    clock.assert_called_once_with()
    assert report.captured_at == captured
    assert report.total_memories == 9
    assert report.project_assigned_memories == 4
    assert report.unassigned_memories == 5
    assert report.counts_by_status == {
        status: (5 if status == "active" else 4 if status == "expired" else 0)
        for status in MEMORY_STATUSES
    }
    assert report.active_missing_embedding.count == 3
    assert report.active_missing_embedding.memory_ids == ids
    assert report.active_missing_embedding.truncated is True
    assert report.active_stale_embedding.truncated is False
    assert (
        datetime.fromisoformat(report.model_dump(mode="json")["captured_at"])
        == captured
    )
    assert '"active_expiration_due"' in report.model_dump_json()
    sent = categories.call_args.kwargs
    assert sent["captured_at"] is captured
    assert (sent["provider"], sent["model"], sent["dimensions"]) == (
        "openai",
        "model",
        1536,
    )


def test_rejects_invalid_limit_and_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="detail limit"):
        run_memory_maintenance_audit(
            Mock(), expected_embedding_identity=("p", "m", 1536), detail_limit=1001
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        run_memory_maintenance_audit(
            Mock(),
            expected_embedding_identity=("p", "m", 1536),
            clock=lambda: datetime(2026, 1, 1),
        )


def test_service_never_flushes_or_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock()
    monkeypatch.setattr(
        "app.memory_maintenance.service.repository.aggregate_counts",
        Mock(return_value=(0, 0, {})),
    )
    monkeypatch.setattr(
        "app.memory_maintenance.service.repository.category_counts_and_ids",
        Mock(
            return_value={
                name: (0, [])
                for name in (
                    "active_missing_embedding",
                    "active_stale_embedding",
                    "active_expiration_due",
                    "active_future_expiration",
                    "expired_missing_expires_at",
                    "non_active_with_embedding",
                )
            }
        ),
    )
    run_memory_maintenance_audit(session, expected_embedding_identity=("p", "m", 1536))
    session.flush.assert_not_called()
    session.commit.assert_not_called()
