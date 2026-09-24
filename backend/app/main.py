from uuid import uuid4

from fastapi import FastAPI, Request

from backend.app.api.dependencies import ServiceRegistry
from backend.app.api.error_handlers import (
    register_error_handlers,
)
from backend.app.api.router import api_router


def create_app(
    *,
    service_registry: ServiceRegistry | None = None,
    v2_service=None,
) -> FastAPI:
    app = FastAPI(
        title="VietReceipt API",
        version="1.0.0",
        description="Core Receipt and Human-in-the-Loop API",
    )
    app.state.service_registry = service_registry
    if v2_service is None:
        import os

        if os.getenv("DATABASE_URL"):
            from backend.app.v2.runtime import build_service

            v2_service = build_service()
    app.state.v2_service = v2_service
    from backend.app.v2.api import register_v2

    register_v2(app)

    @app.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next,
    ):
        request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    register_error_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
