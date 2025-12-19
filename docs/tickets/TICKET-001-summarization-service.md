# TICKET-001: Create Summarization Service

## Overview
Create a new service that summarizes large tool outputs using LiteLLM to reduce token usage in the agent's context window.

## Priority
High

## Estimated Effort
4-6 hours

## Background
When tools return large outputs (internal docs, logs, API responses), this consumes many tokens in the agent's context. We need a service that can summarize these outputs while preserving relevant information.

## Requirements

### Functional Requirements
1. Estimate token count for any string input
2. Serialize various output types (dict, list, string) to string
3. Summarize content using LiteLLM's chat completions API
4. Only summarize when content exceeds a specified token threshold
5. Fall back to truncation if summarization fails

### Non-Functional Requirements
1. Use existing HTTP client utilities (`create_http_client`)
2. Follow existing code patterns in `app/services/`
3. Add comprehensive logging
4. Handle errors gracefully

---

## Implementation Steps

### Step 1: Create the file
Create a new file: `app/services/summarization.py`

### Step 2: Add imports
```python
"""
Summarization service for reducing tool output token usage.

Uses LiteLLM to summarize large tool outputs, preserving relevant information
while reducing token consumption in the agent's context window.
"""

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.utils.http import create_http_client

logger = logging.getLogger(__name__)
```

### Step 3: Add token estimation constants and function

**Why**: We need to estimate how many tokens a string will use. This helps us decide if summarization is needed.

**Constant**:
```python
# Approximate tokens per character ratio (conservative estimate)
# Most tokenizers average ~4 characters per token for English text
CHARS_PER_TOKEN = 4
```

**Function**:
```python
def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a string.

    Uses a conservative character-to-token ratio. For more accurate counts,
    consider using tiktoken, but this is sufficient for threshold checks.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN
```

### Step 4: Add output serialization function

**Why**: Tool outputs can be dicts, lists, strings, etc. We need to convert them to strings for summarization.

```python
def serialize_output(output: Any) -> str:
    """
    Serialize tool output to string for summarization.

    Args:
        output: Tool output (can be dict, list, string, etc.)

    Returns:
        String representation of the output
    """
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, indent=2, default=str)
    except (TypeError, ValueError):
        return str(output)
```

### Step 5: Create the SummarizationService class

**Why**: Encapsulates all summarization logic in a reusable service.

```python
class SummarizationService:
    """
    Service for summarizing large tool outputs via LiteLLM.
    """

    def __init__(
        self,
        litellm_url: str | None = None,
        litellm_api_key: str | None = None,
        model: str = "claude-3-5-haiku-latest",
        timeout: float = 30.0,
    ):
        """
        Initialize the summarization service.

        Args:
            litellm_url: LiteLLM proxy URL (defaults to settings.LITELLM_MCP_SERVER_URL)
            litellm_api_key: LiteLLM API key (defaults to settings.LITELLM_MCP_API_KEY)
            model: Model to use for summarization (should be fast/cheap like Haiku)
            timeout: Request timeout in seconds
        """
        self.litellm_url = (litellm_url or settings.LITELLM_MCP_SERVER_URL).rstrip("/")
        self.litellm_api_key = litellm_api_key or settings.LITELLM_MCP_API_KEY
        self.model = model
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
```

### Step 6: Add the main `summarize` method

**Why**: This is the core method that calls LiteLLM to summarize content.

```python
    async def summarize(
        self,
        content: str,
        user_query: str | None = None,
        tool_name: str | None = None,
        max_output_tokens: int = 1000,
    ) -> str:
        """
        Summarize content using LiteLLM.

        Args:
            content: The content to summarize
            user_query: Optional context about what the user is looking for
            tool_name: Optional tool name for context
            max_output_tokens: Maximum tokens for the summary

        Returns:
            Summarized content

        Raises:
            RuntimeError: If summarization fails
        """
        # Build context for the summarization prompt
        context_parts = []
        if tool_name:
            context_parts.append(f"Tool: {tool_name}")
        if user_query:
            context_parts.append(f"User's goal: {user_query}")
        context = "\n".join(context_parts) if context_parts else ""

        # System prompt instructs the model how to summarize
        system_prompt = """You are a precise summarization assistant. Your task is to summarize tool output while preserving all important information.

Rules:
1. Keep key data points, IDs, names, values, and actionable information
2. Remove redundant or repetitive content
3. Preserve structure where it aids understanding (use bullet points, brief sections)
4. If the output contains errors, always include the error message and relevant details
5. Be concise but complete - don't omit information that could be needed
6. For JSON/structured data, extract and present the essential fields
7. Never make up information - only summarize what's in the output"""

        user_prompt = f"""Summarize the following tool output concisely.

{context}

Tool Output:
{content[:50000]}

Provide a focused summary that captures the essential information."""

        try:
            # Call LiteLLM chat completions endpoint
            endpoint = f"{self.litellm_url}/v1/chat/completions"

            headers = {"Content-Type": "application/json"}
            if self.litellm_api_key:
                headers["Authorization"] = f"Bearer {self.litellm_api_key}"

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_output_tokens,
                "temperature": 0.1,  # Low temperature for consistent summarization
            }

            async with create_http_client(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)

                if response.status_code != 200:
                    self.logger.error(f"Summarization failed: {response.status_code} - {response.text}")
                    raise RuntimeError(f"Summarization request failed: {response.status_code}")

                data = response.json()

                # Extract the summary from the response
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise RuntimeError("Invalid response format from LiteLLM")

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error during summarization: {e}")
            raise RuntimeError(f"Summarization HTTP error: {e}")
        except Exception as e:
            self.logger.error(f"Summarization failed: {e}")
            raise RuntimeError(f"Summarization failed: {e}")
```

### Step 7: Add the `summarize_if_needed` convenience method

**Why**: This method checks if summarization is needed and handles the decision logic.

```python
    async def summarize_if_needed(
        self,
        content: Any,
        max_tokens: int,
        user_query: str | None = None,
        tool_name: str | None = None,
    ) -> tuple[str, bool]:
        """
        Summarize content only if it exceeds the token threshold.

        Args:
            content: The content to potentially summarize
            max_tokens: Maximum allowed tokens before summarization kicks in
            user_query: Optional context about what the user is looking for
            tool_name: Optional tool name for context

        Returns:
            Tuple of (processed_content, was_summarized)
            - processed_content: Either original content or summary
            - was_summarized: True if content was summarized, False otherwise
        """
        content_str = serialize_output(content)
        estimated_tokens = estimate_tokens(content_str)

        # If within limit, return original
        if estimated_tokens <= max_tokens:
            return content_str, False

        self.logger.info(
            f"Content exceeds {max_tokens} tokens (estimated: {estimated_tokens}), summarizing..."
        )

        # Calculate output tokens for summary (half of max, with minimum floor)
        summary_max_tokens = max(500, max_tokens // 2)

        try:
            summary = await self.summarize(
                content=content_str,
                user_query=user_query,
                tool_name=tool_name,
                max_output_tokens=summary_max_tokens,
            )
            return summary, True
        except Exception as e:
            # Fallback: truncate if summarization fails
            self.logger.warning(f"Summarization failed, falling back to truncation: {e}")
            truncated = content_str[:max_tokens * CHARS_PER_TOKEN]
            if len(content_str) > len(truncated):
                truncated += "\n\n[Output truncated due to length]"
            return truncated, True
```

### Step 8: Add global service instance helper

**Why**: Provides a singleton pattern for easy access throughout the app.

```python
# Global service instance
_summarization_service: SummarizationService | None = None


def get_summarization_service() -> SummarizationService:
    """
    Get or create the global summarization service instance.

    Returns:
        Configured SummarizationService instance
    """
    global _summarization_service

    if _summarization_service is None:
        _summarization_service = SummarizationService()

    return _summarization_service
```

---

## Testing Checklist

After implementation, verify:

- [ ] `estimate_tokens("hello world")` returns approximately 2-3
- [ ] `serialize_output({"key": "value"})` returns valid JSON string
- [ ] `serialize_output("plain text")` returns "plain text"
- [ ] Service initializes with default settings from `app/config.py`
- [ ] `summarize_if_needed` returns `(content, False)` when under threshold
- [ ] `summarize_if_needed` returns `(summary, True)` when over threshold
- [ ] Fallback truncation works when LiteLLM is unavailable

## Files to Modify
- `app/services/summarization.py` (create new)
- `app/services/__init__.py` (add export)

## Dependencies
- No new dependencies needed (uses existing `httpx`, `app.config`, `app.utils.http`)

## Related Tickets
- TICKET-002: Add call_tool_summarized MCP tool
- TICKET-003: Add summarization configuration settings
