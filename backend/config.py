"""
AI Architecture Decision Platform - Backend Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Architecture Decision Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # File Upload
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".docx", ".txt"]

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM - OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # LLM - Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Vector DB
    VECTOR_DB_TYPE: str = "faiss"  # "faiss" or "qdrant"
    FAISS_INDEX_PATH: str = "./data/faiss_index"

    # Qdrant (optional)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "architecture_decisions"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
