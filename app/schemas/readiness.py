"""Database readiness response schema."""

from typing import Literal

from pydantic import BaseModel


class ReadinessResponse(BaseModel):
    """Successful database readiness response."""

    status: Literal["ready"]
