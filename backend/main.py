"""
AI Architecture Decision Platform - Main FastAPI Application
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from config import settings
from app.db.base import Base
from app.db.session import engine
import app.db.models  # noqa: F401

from app.routers import upload, analysis, questionnaire, projects, users

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- App ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

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
        if cache_service._client:
            cache_service._client.set("test_startup", "ok", ex=10)
            logger.info("Redis connection successful!")
        else:
            logger.warning("Redis client not initialized.")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    logger.info("Creating database tables (if not exist)...")
    from pathlib import Path
    Base.metadata.create_all(bind=engine)
    faiss_path = Path(settings.FAISS_INDEX_PATH)
    faiss_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"FAISS index directory ready at: {faiss_path.resolve()}")
    logger.info("Startup complete.")

@app.get("/api/v1/health", tags=["Health"])
def health():
    return {"status": "ok", "version": settings.APP_VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
