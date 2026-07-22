"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import jobs, workflows
from app.api.routes import settings as settings_routes
from app.config import get_settings
from app.database import init_db, session_scope
from app.services.feedback_service import ensure_default_rule
from app.services.scheduler_service import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    app_settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    with session_scope() as db:
        ensure_default_rule(db)
    start_scheduler()
    logger.info("ACONEX Workflow Manager started (db=%s)", app_settings.database_url)
    yield
    shutdown_scheduler()
    logger.info("ACONEX Workflow Manager stopped")


def create_app() -> FastAPI:
    app_settings = get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list + ["*"] if app_settings.debug else app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings_routes.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": app_settings.app_name}

    return app


app = create_app()
