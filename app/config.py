"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "tool-registry-mcp"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    WORKERS: int = 4

    # Database
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string with asyncpg driver",
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Embedding Service
    EMBEDDING_ENDPOINT_URL: str = Field(
        ...,
        description="URL of the embedding service endpoint",
    )
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_DIMENSION: int = 1536

    # Embedding Cache Configuration
    ENABLE_EMBEDDING_CACHE: bool = True
    EMBEDDING_CACHE_SIZE: int = 1000
    EMBEDDING_MAX_RETRIES: int = 3
    EMBEDDING_BASE_DELAY: float = 1.0
    EMBEDDING_MAX_BATCH_SIZE: int = 100
    EMBEDDING_TIMEOUT: float = 30.0

    # Search Configuration
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.7
    DEFAULT_SEARCH_LIMIT: int = 5
    USE_HYBRID_SEARCH: bool = True

    # Security
    API_KEY: Optional[str] = None
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "http://localhost:8000"],
        description="Allowed CORS origins"
    )

    # Performance
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 300  # seconds

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        """Parse CORS origins from list or comma-separated string."""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).rstrip("/") for origin in v if origin]
        return []

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v_upper

    @field_validator("DEFAULT_SIMILARITY_THRESHOLD")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate similarity threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("DEFAULT_SIMILARITY_THRESHOLD must be between 0 and 1")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
