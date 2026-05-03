"""ArchGuide Elite v5.0 — Backend Configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "ArchGuide — AI Architecture Intelligence"
    APP_VERSION: str = "5.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".docx", ".txt"]

    # Database — optional, SQLite used as primary storage
    DATABASE_URL: Optional[str] = None
    SQLITE_PATH: str = "./archguide.db"

    # Redis — optional
    REDIS_URL: Optional[str] = None
    REDIS_TOKEN: Optional[str] = None

    # LLM
    DEFAULT_LLM_PROVIDER: str = "ollama"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_EMBEDDING_DIMENSION: int = 768
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_CHUNK_SIZE: int = 500
    EMBEDDING_CHUNK_OVERLAP: int = 50
    VECTOR_DB_TYPE: str = "faiss"
    FAISS_INDEX_PATH: str = "./faiss_index"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "architecture_decisions"
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
