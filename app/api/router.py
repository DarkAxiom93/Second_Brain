"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.agent_runs import approval_router
from app.api.routes.agent_runs import router as agent_runs_router
from app.api.routes.answers import router as answers_router
from app.api.routes.automation_notifications import (
    router as automation_notifications_router,
)
from app.api.routes.automations import router as automations_router
from app.api.routes.health import router as health_router
from app.api.routes.memories import router as memories_router
from app.api.routes.memory_embedding_batches import router as embedding_batches_router
from app.api.routes.memory_proposals import router as memory_proposals_router
from app.api.routes.operations import router as operations_router
from app.api.routes.projects import router as projects_router
from app.api.routes.readiness import router as readiness_router
from app.api.routes.sources import document_router
from app.api.routes.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(agent_runs_router)
api_router.include_router(approval_router)
api_router.include_router(answers_router)
api_router.include_router(automations_router)
api_router.include_router(automation_notifications_router)
api_router.include_router(health_router)
api_router.include_router(readiness_router)
api_router.include_router(operations_router)
api_router.include_router(projects_router)
api_router.include_router(memories_router)
api_router.include_router(embedding_batches_router)
api_router.include_router(memory_proposals_router)
api_router.include_router(sources_router)
api_router.include_router(document_router)
