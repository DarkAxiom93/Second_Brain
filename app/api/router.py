"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.memories import router as memories_router
from app.api.routes.projects import router as projects_router
from app.api.routes.readiness import router as readiness_router
from app.api.routes.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(readiness_router)
api_router.include_router(projects_router)
api_router.include_router(memories_router)
api_router.include_router(sources_router)
