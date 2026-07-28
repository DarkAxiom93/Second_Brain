"""Health endpoint response schema."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness response returned by the health endpoint."""

    status: Literal["ok"]
