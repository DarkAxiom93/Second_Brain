"""Pure policy for explicit, human-controlled Memory quality refinement."""

from dataclasses import dataclass
from typing import Literal

from app.models.memory import Memory

QualityRefinementStatus = Literal["updated", "unchanged"]


@dataclass(frozen=True)
class QualityRefinementConflict(Exception):
    """An expected public conflict in a quality-refinement request."""

    detail: str


def classify_quality_refinement(
    *, memory: Memory, confidence: float | None, importance: float | None
) -> QualityRefinementStatus:
    """Validate locked state and classify whether supplied values differ."""

    if memory.status != "active":
        raise QualityRefinementConflict("memory not eligible for quality refinement")
    if confidence is not None and confidence != memory.confidence:
        return "updated"
    if importance is not None and importance != memory.importance:
        return "updated"
    return "unchanged"
