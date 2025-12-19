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

# Approximate tokens per character ratio (conservative estimate)
# Most tokenizers average ~4 characters per token for English text
CHARS_PER_TOKEN = 4


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


class SummarizationService:
    """
    Service for summarizing large tool outputs via LiteLLM.
    """

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
{content[:self.max_input_chars]}

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
        # Check if summarization is enabled (will be configurable in TICKET-003)
        if not self.enabled:
            return serialize_output(content), False

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