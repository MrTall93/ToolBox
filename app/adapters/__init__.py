"""Adapter package for external integrations."""

from .litellm_mcp import (
    LiteLLMMCPAdapter,
    LiteLLMTool,
    LiteLLMToolCall,
    LiteLLMToolResult,
    get_litellm_mcp_adapter,
)

__all__ = [
    "LiteLLMMCPAdapter",
    "LiteLLMTool",
    "LiteLLMToolCall",
    "LiteLLMToolResult",
    "get_litellm_mcp_adapter",
]