"""Pure policy for explicit, human-controlled Memory expiration."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.models.memory import Memory

ExpirationStatus = Literal["updated", "unchanged"]


@dataclass(frozen=True)
class ExpirationConflict(Exception):
    """An expected public conflict in an expiration request."""

    detail: str


@dataclass(frozen=True)
class ExpirationDecision:
    """The classified transition and timestamp to persist, if any."""

    status: ExpirationStatus
    expires_at: datetime


def classify_expiration(*, memory: Memory, captured_at: datetime) -> ExpirationDecision:
    """Validate locked state and select the stable expiration timestamp."""

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    if memory.status == "expired":
        if memory.expires_at is None:
            raise ExpirationConflict("memory expiration state is inconsistent")
        return ExpirationDecision(status="unchanged", expires_at=memory.expires_at)
    if memory.status != "active":
        raise ExpirationConflict("memory not eligible for expiration")
    expires_at = memory.expires_at
    if expires_at is None or expires_at > captured_at:
        expires_at = captured_at
    return ExpirationDecision(status="updated", expires_at=expires_at)
