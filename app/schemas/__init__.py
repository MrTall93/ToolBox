"""Pydantic schemas for request/response validation."""

from app.schemas.mcp import (
    # Tool schemas
    ToolSchema,
    ToolWithScore,
    # list_tools
    ListToolsRequest,
    ListToolsResponse,
    # find_tool
    FindToolRequest,
    FindToolResponse,
    # call_tool
    CallToolRequest,
    CallToolResponse,
    # Admin endpoints
    RegisterToolRequest,
    RegisterToolResponse,
    UpdateToolRequest,
    UpdateToolResponse,
    # Stats and health
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
