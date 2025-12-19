# TICKET-003: Add Summarization Configuration Settings

## Overview
Add configuration settings for the summarization feature to `app/config.py`, allowing operators to customize the summarization behavior without code changes.

## Priority
Medium

## Estimated Effort
1-2 hours

## Prerequisites
- TICKET-001 (Summarization Service) should be completed first

## Background
The summarization service needs configurable settings for:
- Which model to use for summarization
- Default token thresholds
- Timeout settings
- Enable/disable flag

---

## Implementation Steps

### Step 1: Open the config file
Open: `app/config.py`

### Step 2: Add new settings to the Settings class

Find the `class Settings(BaseSettings):` section. Add these new settings after the existing LiteLLM settings (around line 87):

```python
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
```

### Step 3: Add validators for the new settings

Add these validators after the existing validators (around line 190):

```python
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
```

---

## Step 4: Update the Summarization Service to use these settings

After TICKET-001 is complete, update `app/services/summarization.py` to use these settings:

### 4a: Update the `__init__` method

Change the `SummarizationService.__init__` to use settings:

```python
def __init__(
    self,
    litellm_url: str | None = None,
    litellm_api_key: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
):
    """
    Initialize the summarization service.

    Args:
        litellm_url: LiteLLM proxy URL (defaults to settings)
        litellm_api_key: LiteLLM API key (defaults to settings)
        model: Model to use for summarization (defaults to settings)
        timeout: Request timeout in seconds (defaults to settings)
    """
    self.litellm_url = (litellm_url or settings.LITELLM_MCP_SERVER_URL).rstrip("/")
    self.litellm_api_key = litellm_api_key or settings.LITELLM_MCP_API_KEY
    self.model = model or settings.SUMMARIZATION_MODEL
    self.timeout = timeout or settings.SUMMARIZATION_TIMEOUT
    self.max_input_chars = settings.SUMMARIZATION_MAX_INPUT_CHARS
    self.enabled = settings.SUMMARIZATION_ENABLED
    self.logger = logging.getLogger(__name__)
```

### 4b: Update the `summarize` method to respect max input chars

In the `summarize` method, change:
```python
{content[:50000]}
```
to:
```python
{content[:self.max_input_chars]}
```

### 4c: Update `summarize_if_needed` to check if enabled

At the start of `summarize_if_needed`, add:
```python
if not self.enabled:
    return serialize_output(content), False
```

---

## Environment Variables Reference

After implementation, these environment variables can be set:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUMMARIZATION_ENABLED` | `true` | Set to `false` to disable summarization |
| `SUMMARIZATION_MODEL` | `claude-3-5-haiku-latest` | Model for summarization |
| `SUMMARIZATION_DEFAULT_MAX_TOKENS` | `2000` | Default token threshold |
| `SUMMARIZATION_TIMEOUT` | `30.0` | Timeout in seconds |
| `SUMMARIZATION_MAX_INPUT_CHARS` | `50000` | Max chars to summarize |

### Example `.env` additions:
```bash
# Summarization Settings
SUMMARIZATION_ENABLED=true
SUMMARIZATION_MODEL=claude-3-5-haiku-latest
SUMMARIZATION_DEFAULT_MAX_TOKENS=2000
SUMMARIZATION_TIMEOUT=30.0
```

---

## Testing Checklist

### Test Configuration Loading

1. **Test default values**:
   - Don't set any SUMMARIZATION_* env vars
   - Verify settings load with defaults

2. **Test custom values**:
   - Set `SUMMARIZATION_MODEL=gpt-4o-mini`
   - Verify it's used instead of default

3. **Test validation - too low max tokens**:
   - Set `SUMMARIZATION_DEFAULT_MAX_TOKENS=50`
   - Expect ValueError on startup

4. **Test validation - too high timeout**:
   - Set `SUMMARIZATION_TIMEOUT=200`
   - Expect ValueError on startup

5. **Test disabled**:
   - Set `SUMMARIZATION_ENABLED=false`
   - Verify `call_tool_summarized` returns unsummarized output

### Unit Tests

Add to `tests/test_config.py` (or create if doesn't exist):

```python
import pytest
from pydantic import ValidationError

def test_summarization_default_values():
    """Test summarization settings have correct defaults."""
    from app.config import Settings

    # Create settings with minimal required fields
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        EMBEDDING_ENDPOINT_URL="http://localhost:8000"
    )

    assert s.SUMMARIZATION_ENABLED is True
    assert s.SUMMARIZATION_MODEL == "claude-3-5-haiku-latest"
    assert s.SUMMARIZATION_DEFAULT_MAX_TOKENS == 2000
    assert s.SUMMARIZATION_TIMEOUT == 30.0

def test_summarization_max_tokens_too_low():
    """Test validation rejects too-low max tokens."""
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_DEFAULT_MAX_TOKENS=50  # Too low
        )

def test_summarization_timeout_too_high():
    """Test validation rejects too-high timeout."""
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            EMBEDDING_ENDPOINT_URL="http://localhost:8000",
            SUMMARIZATION_TIMEOUT=200.0  # Too high
        )
```

---

## Files to Modify

1. `app/config.py` - Add new settings and validators
2. `app/services/summarization.py` - Update to use settings (after TICKET-001)
3. `tests/test_config.py` - Add configuration tests
4. `.env.example` - Add example values (if file exists)

## Related Tickets

- TICKET-001: Create Summarization Service (should be done first)
- TICKET-002: Add call_tool_summarized MCP tool
