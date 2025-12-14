"""Pydantic schemas for request/response validation."""

from app.schemas.mcp import (
    ToolSchema,
    ToolWithScore,
    ListToolsRequest,
    ListToolsResponse,
    FindToolRequest,
    FindToolResponse,
    CallToolRequest,
    CallToolResponse,
    RegisterToolRequest,
    RegisterToolResponse,
    UpdateToolRequest,
    UpdateToolResponse,
    ToolStatsResponse,
    HealthCheckResponse,
    ErrorResponse,
)

__all__ = [
    "ToolSchema",
    "ToolWithScore",
    "ListToolsRequest",
    "ListToolsResponse",
    "FindToolRequest",
    "FindToolResponse",
    "CallToolRequest",
    "CallToolResponse",
    "RegisterToolRequest",
    "RegisterToolResponse",
    "UpdateToolRequest",
    "UpdateToolResponse",
    "ToolStatsResponse",
    "HealthCheckResponse",
    "ErrorResponse",
]
