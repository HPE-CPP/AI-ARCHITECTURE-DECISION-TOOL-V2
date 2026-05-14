"""
AI Architecture Decision Platform — Main FastAPI Application
Entry point: uvicorn app.main:app --reload
"""
import logging
import sys
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# Ensure backend root is on the path so `services/` and `config` are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from app.db.base import Base
from app.db.session import engine
import app.db.models  # noqa: F401 — registers all models with Base

from app.routers import upload, analysis, questionnaire, projects, users

logging.basicConfig(level=logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


from app.limiter import limiter


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Attach limiter state and register the 429 handler
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda req, exc: JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please wait a moment before trying again.",
                "retry_after": str(exc.retry_after) if hasattr(exc, "retry_after") else "60",
            },
        ),
    )

    # CORS — SEC-006 FIX: Replaced allow_origin_regex='.*' with explicit origin
    # allowlist from settings. Wildcard + credentials violates CORS spec and allows
    # any site to make credentialed cross-origin requests to this API.
    _allow_credentials = bool(settings.CORS_ORIGINS) and "*" not in settings.CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

    # Mount routers under /api/v1
    prefix = settings.API_PREFIX  # "/api/v1"
    app.include_router(upload.router, prefix=prefix, tags=["Upload"])
    app.include_router(analysis.router, prefix=prefix, tags=["Analysis"])
    app.include_router(questionnaire.router, prefix=prefix, tags=["Questionnaire"])
    app.include_router(projects.router, prefix=prefix, tags=["Projects"])
    app.include_router(users.router, prefix=prefix, tags=["Users"])

    # Startup: create DB tables + FAISS directory
    @app.on_event("startup")
    def on_startup():
        logger.info("Verifying database connection...")
        try:
            with engine.connect() as connection:
                logger.info("PostgreSQL connection successful!")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")

        logger.info("Verifying Redis connection...")
        try:
            from app.services import cache_service
            # We can use the existing cache_service logic or a raw client check
            if cache_service._client:
                cache_service._client.set("test_startup", "ok", ex=10)
                logger.info("Redis connection successful!")
            else:
                logger.warning("Redis client not initialized.")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

        logger.info("Running Alembic migrations (upgrade head)...")
        try:
            from alembic.config import Config as AlembicConfig
            from alembic import command as alembic_command
            alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
            alembic_cfg = AlembicConfig(str(alembic_ini))
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("Migrations complete.")
        except Exception as e:
            # Non-fatal in dev — tables may already exist via create_all from a
            # previous run.  In production, fix the migration before deploying.
            logger.error("Alembic migration failed: %s", e)
            logger.warning("Falling back to create_all (dev only — do not use in production)")
            Base.metadata.create_all(bind=engine)

        faiss_path = Path(settings.FAISS_INDEX_PATH)
        faiss_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"FAISS index directory ready at: {faiss_path.resolve()}")

        # Recover orphaned sessions: any session stuck in "processing" after a
        # server crash or OOM kill will never self-heal. Mark them as "error" on
        # startup so users get a clear failure rather than an infinite spinner.
        try:
            from datetime import datetime, timedelta, timezone
            from app.db.session import SessionLocal
            from app.db.models import Session as SessionModel
            db = SessionLocal()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
                stale = (
                    db.query(SessionModel)
                    .filter(
                        SessionModel.status == "processing",
                        SessionModel.created_at < cutoff,
                    )
                    .all()
                )
                if stale:
                    for s in stale:
                        s.status = "error"
                    db.commit()
                    logger.warning("Recovered %d orphaned processing session(s) → error", len(stale))
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to recover orphaned sessions: %s", e)

        logger.info("Startup complete.")

    # Health check
    @app.get("/api/v1/health", tags=["Health"])
    def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
