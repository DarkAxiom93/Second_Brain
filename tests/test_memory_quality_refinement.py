"""Unit tests for explicit Memory quality-refinement policy and responses."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.memory_quality.refinement import (
    QualityRefinementConflict,
    classify_quality_refinement,
)
from app.schemas.memory import MemoryQualityRefinementRead
from tests.test_memory_routes import memory


def test_classification_is_active_only_and_compares_supplied_fields() -> None:
    row = memory()
    assert (
        classify_quality_refinement(
            memory=row, confidence=row.confidence, importance=None
        )
        == "unchanged"
    )
    assert (
        classify_quality_refinement(memory=row, confidence=0.4, importance=0.7)
        == "updated"
    )
    for status in ("superseded", "expired", "invalid", "archived"):
        row.status = status
        with pytest.raises(QualityRefinementConflict) as error:
            classify_quality_refinement(memory=row, confidence=0.4, importance=None)
        assert error.value.detail == "memory not eligible for quality refinement"


def test_response_accepts_only_updated_or_unchanged() -> None:
    row = memory()
    for status in ("updated", "unchanged"):
        result = MemoryQualityRefinementRead(
            refinement_status=status,
            memory=row,  # type: ignore[arg-type]
        )
        assert result.refinement_status == status
    with pytest.raises(ValidationError):
        MemoryQualityRefinementRead(
            refinement_status="other",
            memory=SimpleNamespace(),  # type: ignore[arg-type]
        )
