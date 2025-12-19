"""Application configuration using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Any

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
    EMBEDDING_API_KEY: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-nomic-embed-text-v1.5"
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
    API_KEY: str | None = None
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "http://localhost:8000"],
        description="Allowed CORS origins"
    )

    # Performance
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 300  # seconds

    # MCP Server Discovery Settings
    MCP_SERVERS: list[dict[str, Any]] = Field(
        default=[],
        description="List of MCP servers to sync tools from"
    )
    MCP_AUTO_SYNC_ON_STARTUP: bool = True
    MCP_SYNC_INTERVAL_SECONDS: int = 300  # 5 minutes
    MCP_REQUEST_TIMEOUT: float = 30.0

    # LiteLLM Integration Settings
    LITELLM_SYNC_ENABLED: bool = True
    LITELLM_MCP_SERVER_URL: str = Field(
        default="http://litellm:4000",
        description="litellm mcp server"
    )
    LITELLM_MCP_API_KEY: str | None = None
    LITELLM_MCP_TIMEOUT: int = 30
    LITELLM_MCP_MAX_RETRIES: int = 3

    # Summarization Settings
    SUMMARIZATION_ENABLED: bool = Field(
        default=True,
        description="Enable/disable output summarization feature"
    )
    SUMMARIZATION_MODEL: str = Field(
        default="claude-3-5-haiku-latest",
        description="Model to use for summarization (should be fast/cheap)"
    )
    SUMMARIZATION_DEFAULT_MAX_TOKENS: int = Field(
        default=2000,
        description="Default max tokens before summarization triggers"
    )
    SUMMARIZATION_TIMEOUT: float = Field(
        default=30.0,
        description="Timeout for summarization requests in seconds"
    )
    SUMMARIZATION_MAX_INPUT_CHARS: int = Field(
        default=50000,
        description="Maximum characters to send for summarization (truncate before)"
    )

    # OpenTelemetry Configuration
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: str | None = None
    OTEL_SERVICE_NAME: str = "toolbox"
    OTEL_SERVICE_VERSION: str = "1.0.0"
    OTEL_HONEYCOMB_TEAM: str | None = None
    OTEL_RESOURCE_ATTRIBUTES: str = ""  # Comma-separated key=value pairs
    OTEL_ENABLED: bool = True

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v) -> list[str]:
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

    @field_validator("MCP_SERVERS", mode="before")
    @classmethod
    def parse_mcp_servers(cls, v) -> list[dict[str, Any]]:
        """Parse MCP servers from JSON string or list."""
        if isinstance(v, str):
            if not v.strip():
                return []
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        # Must be PostgreSQL with asyncpg driver
        if not v.startswith(("postgresql+asyncpg://", "postgresql://", "postgres://")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string "
                "(postgresql+asyncpg:// or postgresql://)"
            )
        return v

    @field_validator("EMBEDDING_ENDPOINT_URL")
    @classmethod
    def validate_embedding_url(cls, v: str) -> str:
        """Validate embedding endpoint URL format."""
        if not v:
            raise ValueError("EMBEDDING_ENDPOINT_URL is required")
        if not v.startswith(("http://", "https://")):
            raise ValueError("EMBEDDING_ENDPOINT_URL must be a valid HTTP(S) URL")
        return v.rstrip("/")

    @field_validator("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate positive integer values."""
        if v < 0:
            raise ValueError("Value must be a non-negative integer")
        return v

    @field_validator("EMBEDDING_DIMENSION")
    @classmethod
    def validate_embedding_dimension(cls, v: int) -> int:
        """Validate embedding dimension is reasonable."""
        if v < 1 or v > 10000:
            raise ValueError("EMBEDDING_DIMENSION must be between 1 and 10000")
        return v

    @field_validator("EMBEDDING_TIMEOUT", "MCP_REQUEST_TIMEOUT")
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        """Validate timeout values are positive."""
        if v <= 0:
            raise ValueError("Timeout must be a positive number")
        if v > 600:
            raise ValueError("Timeout should not exceed 600 seconds")
        return v

    @field_validator("WORKERS")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """Validate worker count is reasonable."""
        if v < 1:
            raise ValueError("WORKERS must be at least 1")
        if v > 32:
            raise ValueError("WORKERS should not exceed 32")
        return v

    @field_validator("SUMMARIZATION_DEFAULT_MAX_TOKENS")
    @classmethod
    def validate_summarization_max_tokens(cls, v: int) -> int:
        """Validate summarization max tokens is reasonable."""
        if v < 100:
            raise ValueError("SUMMARIZATION_DEFAULT_MAX_TOKENS must be at least 100")
        if v > 50000:
            raise ValueError("SUMMARIZATION_DEFAULT_MAX_TOKENS should not exceed 50000")
        return v

    @field_validator("SUMMARIZATION_TIMEOUT")
    @classmethod
    def validate_summarization_timeout(cls, v: float) -> float:
        """Validate summarization timeout is reasonable."""
        if v <= 0:
            raise ValueError("SUMMARIZATION_TIMEOUT must be positive")
        if v > 120:
            raise ValueError("SUMMARIZATION_TIMEOUT should not exceed 120 seconds")
        return v

    @field_validator("SUMMARIZATION_MAX_INPUT_CHARS")
    @classmethod
    def validate_summarization_max_input(cls, v: int) -> int:
        """Validate max input characters is reasonable."""
        if v < 1000:
            raise ValueError("SUMMARIZATION_MAX_INPUT_CHARS must be at least 1000")
        if v > 200000:
            raise ValueError("SUMMARIZATION_MAX_INPUT_CHARS should not exceed 200000")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
