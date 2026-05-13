"""
AI Architecture Decision Platform - Backend Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Architecture Decision Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    FIREBASE_PROJECT_ID: Optional[str] = "archguide-dev"

    # CORS — add your Vercel URL here or set CORS_ORIGINS env var
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # File Upload
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".docx", ".txt"]

    # PostgreSQL (Supabase)
    DATABASE_URL: str = "postgresql+psycopg2://postgres:password@localhost:5432/architecture_db"

    # Redis (Upstash)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TOKEN: Optional[str] = None  # Upstash REST token (for SSL auth)

    # Default Provider Switch
    DEFAULT_LLM_PROVIDER: str = "ollama"

    # LLM - OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # LLM - Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_EMBEDDING_DIMENSION: int = 768

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"  # OpenAI embedding model
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_CHUNK_SIZE: int = 500    # tokens per chunk
    EMBEDDING_CHUNK_OVERLAP: int = 50  # token overlap between chunks

    # Vector DB (FAISS)
    VECTOR_DB_TYPE: str = "faiss"
    FAISS_INDEX_PATH: str = "./faiss_index"

    # Qdrant (optional future swap)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "architecture_decisions"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    # H-001 FIX: Migrated from deprecated class Config to ConfigDict
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
