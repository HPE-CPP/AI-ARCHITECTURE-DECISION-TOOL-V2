"""
AI Architecture Decision Platform - Main FastAPI Application
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

from config import settings
from app.db.session import engine, SessionLocal
import app.db.models  # noqa: F401

from app.routers import upload, analysis, questionnaire, projects, users, chat, score_preview, share_router

from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy import inspect, text

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# P7-007 FIX: Security response headers middleware
# The API returned zero security headers. OWASP recommends these four as a
# baseline for any HTTP API consumed by browsers.
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append OWASP-recommended security headers to every API response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Swagger UI needs scripts/styles from CDN — skip strict CSP for docs paths
        if request.url.path not in ("/docs", "/redoc", "/openapi.json"):
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response


# ---------------------------------------------------------------------------
# M-001 FIX: Lifespan context manager (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the FastAPI application."""
    # --- STARTUP ---
    logger.info("Verifying database connection...")
    try:
        with engine.connect() as _:
            logger.info("PostgreSQL connection successful!")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")

    redis_url = settings.effective_redis_url
    masked = redis_url[:20] + "..." if len(redis_url) > 20 else redis_url
    logger.info(f"Verifying Redis connection (URL: {masked})...")
    try:
        from app.services import cache_service
        if cache_service._client:
            cache_service._client.set("test_startup", "ok", ex=10)
            logger.info("Redis connection successful!")
        else:
            logger.warning("Redis client not initialized.")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    try:
        logger.info("Running Alembic migrations...")
        alembic_ini = Path(__file__).resolve().parent / "alembic.ini"
        alembic_cfg = AlembicConfig(str(alembic_ini))
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            alembic_command.stamp(alembic_cfg, "head")
            logger.info("Stamped existing database with Alembic head.")
        else:
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied.")
    except Exception as e:
        logger.error("Alembic migrations skipped (DB unavailable): %s", e)

    logger.info("Verifying Qdrant connection...")
    try:
        from app.utils.faiss_store import _get_client
        _get_client().get_collections()
        logger.info("Qdrant connection successful!")
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")

    faiss_path = Path(settings.FAISS_INDEX_PATH)
    faiss_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"FAISS index directory ready at: {faiss_path.resolve()}")

    try:
        from app.utils.faiss_store import cleanup_old_indexes
        cleaned = cleanup_old_indexes(max_age_days=30)
        if cleaned:
            logger.info("Qdrant: removed vectors for %d old sessions", cleaned)
    except Exception as e:
        logger.error("Qdrant cleanup failed: %s", e)

    # Recover orphaned sessions: any session stuck in "processing" after a
    # server crash or OOM kill will never self-heal. Mark them as "error" on
    # startup so users get a clear failure rather than an infinite spinner.
    try:
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

    yield  # Application runs here

    # --- SHUTDOWN ---
    logger.info("Shutting down...")


# --- App ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# P7-007: Security headers must be added BEFORE CORS so they are present on
# all responses including preflight OPTIONS responses.
app.add_middleware(SecurityHeadersMiddleware)

# SEC-3.5 FIX: CORS wildcard + allow_credentials=True violates the CORS spec
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
app.include_router(chat.router, prefix=prefix, tags=["Chat"])
app.include_router(score_preview.router, prefix=prefix, tags=["ScorePreview"])
app.include_router(share_router.router, prefix=prefix, tags=["Share"])

@app.get("/api/v1/ping", tags=["Health"])
async def ping():
    """Liveness probe — returns 200 as long as the process is alive."""
    return {"status": "ok"}


@app.get("/api/v1/health", tags=["Health"])
async def health():
    """Deep health check — tests PostgreSQL, Redis, Qdrant, and LLM provider.

    Returns per-service status so load balancers and dashboards get real signal,
    not a blind {"status": "ok"} that hides broken dependencies.
    """
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "up"
    except Exception:
        checks["database"] = "down"

    # Redis
    try:
        from app.services import cache_service
        if cache_service._client:
            cache_service._client.ping()
            checks["redis"] = "up"
        else:
            checks["redis"] = "not_configured"
    except Exception:
        checks["redis"] = "down"

    # Qdrant
    try:
        from app.utils.faiss_store import _get_client
        _get_client().get_collections()
        checks["qdrant"] = "up"
    except Exception:
        checks["qdrant"] = "down"

    # LLM provider — quick connectivity check (no inference)
    try:
        provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama").lower()
        if provider == "openai":
            if settings.OPENAI_API_KEY:
                checks["llm"] = "configured"
            elif settings.GROQ_API_KEY:
                checks["llm"] = "configured_groq_fallback"
            else:
                checks["llm"] = "no_api_key"
        elif provider == "ollama":
            import httpx
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    expected = getattr(settings, "OLLAMA_MODEL", "")
                    checks["llm"] = "up" if any(expected in m.get("name", "") for m in models) else "model_missing"
                else:
                    checks["llm"] = "down"
        else:
            checks["llm"] = "unknown_provider"
    except Exception:
        checks["llm"] = "down"

    all_up = all(v in ("up", "configured", "configured_groq_fallback", "not_configured") for v in checks.values())
    overall = "healthy" if all_up else "degraded"
    status_code = 200 if all_up else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "version": settings.APP_VERSION,
            "checks": checks,
        },
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

