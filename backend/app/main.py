from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.errors import register_error_handlers
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="SketchBuild API", version=settings.version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
