from fastapi import FastAPI

from backend.app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="VietReceipt API",
        version="1.0.0",
        description="Core Receipt and Human-in-the-Loop API",
    )

    app.include_router(api_router)

    return app


app = create_app()
