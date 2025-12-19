"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_summarization_default_values():
    """Test summarization settings have correct defaults."""
    # Create settings with minimal required fields
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        EMBEDDING_ENDPOINT_URL="http://localhost:8000"
    )

    assert s.SUMMARIZATION_ENABLED is True
    assert s.SUMMARIZATION_MODEL == "claude-3-5-haiku-latest"
    assert s.SUMMARIZATION_DEFAULT_MAX_TOKENS == 2000
    assert s.SUMMARIZATION_TIMEOUT == 30.0
    assert s.SUMMARIZATION_MAX_INPUT_CHARS == 50000


def test_summarization_max_tokens_too_low():
    """Test validation rejects too-low max tokens."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_DEFAULT_MAX_TOKENS=50  # Too low
        )

    assert "SUMMARIZATION_DEFAULT_MAX_TOKENS" in str(exc_info.value)
    assert "at least 100" in str(exc_info.value)


def test_summarization_max_tokens_too_high():
    """Test validation rejects too-high max tokens."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_DEFAULT_MAX_TOKENS=60000  # Too high
        )

    assert "SUMMARIZATION_DEFAULT_MAX_TOKENS" in str(exc_info.value)
    assert "should not exceed 50000" in str(exc_info.value)


def test_summarization_timeout_negative():
    """Test validation rejects negative timeout."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_TIMEOUT=-10.0
        )

    assert "SUMMARIZATION_TIMEOUT" in str(exc_info.value)
    assert "must be positive" in str(exc_info.value)


def test_summarization_timeout_too_high():
    """Test validation rejects too-high timeout."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_TIMEOUT=200.0  # Too high
        )

    assert "SUMMARIZATION_TIMEOUT" in str(exc_info.value)
    assert "should not exceed 120 seconds" in str(exc_info.value)


def test_summarization_max_input_too_low():
    """Test validation rejects too-low max input chars."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_MAX_INPUT_CHARS=500  # Too low
        )

    assert "SUMMARIZATION_MAX_INPUT_CHARS" in str(exc_info.value)
    assert "at least 1000" in str(exc_info.value)


def test_summarization_max_input_too_high():
    """Test validation rejects too-high max input chars."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_MAX_INPUT_CHARS=300000  # Too high
        )

    assert "SUMMARIZATION_MAX_INPUT_CHARS" in str(exc_info.value)
    assert "should not exceed 200000" in str(exc_info.value)


def test_summarization_custom_values():
    """Test custom summarization values are accepted."""
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        EMBEDDING_ENDPOINT_URL="http://localhost:8000",
        SUMMARIZATION_ENABLED=False,
        SUMMARIZATION_MODEL="gpt-4o-mini",
        SUMMARIZATION_DEFAULT_MAX_TOKENS=5000,
        SUMMARIZATION_TIMEOUT=60.0,
        SUMMARIZATION_MAX_INPUT_CHARS=100000,
    )

    assert s.SUMMARIZATION_ENABLED is False
    assert s.SUMMARIZATION_MODEL == "gpt-4o-mini"
    assert s.SUMMARIZATION_DEFAULT_MAX_TOKENS == 5000
    assert s.SUMMARIZATION_TIMEOUT == 60.0
    assert s.SUMMARIZATION_MAX_INPUT_CHARS == 100000