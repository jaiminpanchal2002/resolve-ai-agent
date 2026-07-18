from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core Application Config
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    JWT_SECRET: str = "super-secret-jwt-key-replace-in-production-123456"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/resolveai"
    DATABASE_SYNC_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/resolveai"
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Settings
    OPENAI_API_KEY: str = "mock-key-or-real-key"
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = "mock-key-or-real-key"
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash"
    DEFAULT_PROVIDER: Literal["openai", "gemini"] = "openai"
    USE_FAKE_LLM: bool = False  # deterministic offline provider for tests/CI
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 3

    # CORS (explicit origins; wildcard + credentials is invalid per spec)
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # RAG Config
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # Observability
    OPENTELEMETRY_ENDPOINT: str = "http://localhost:4317"
    PROMETHEUS_PORT: int = 8001


settings = Settings()
