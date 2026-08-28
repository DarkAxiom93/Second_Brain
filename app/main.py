"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(settings.app_log_level)
    application = FastAPI(title=settings.app_name)

    @application.exception_handler(RequestValidationError)
    async def safe_connector_validation(
        request: Request, exc: RequestValidationError
    ) -> Response:
        # Pydantic's normal 422 body echoes rejected input. Connector input may be
        # secret-shaped, so this boundary returns one closed content-free error.
        if request.url.path.startswith("/connector-accounts"):
            return JSONResponse(
                status_code=422,
                content={"detail": "invalid connector account request"},
            )
        return await request_validation_exception_handler(request, exc)

    application.include_router(api_router)
    return application


app = create_app()
