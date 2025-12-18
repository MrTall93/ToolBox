"""
Pydantic schemas for MCP (Model Context Protocol) endpoints.

Defines request and response models for the MCP API:
- list_tools: List all available tools
- find_tool: Semantic search for tools
- call_tool: Execute a tool
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Tool Schemas
# ============================================================================

class ToolSchema(BaseModel):
    """Schema for tool information in MCP responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    category: str
    tags: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    version: str = "1.0.0"
    is_active: bool = True


class ToolWithScore(BaseModel):
    """Tool with similarity/relevance score."""

    tool: ToolSchema
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0-1)")


# ============================================================================
# list_tools Endpoint
# ============================================================================

class ListToolsRequest(BaseModel):
    """Request schema for list_tools endpoint."""

    category: Optional[str] = Field(None, description="Filter by category")
    active_only: bool = Field(True, description="Only return active tools")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of tools")
    offset: int = Field(0, ge=0, description="Pagination offset")


class ListToolsResponse(BaseModel):
    """Response schema for list_tools endpoint."""

    tools: List[ToolSchema]
    total: int = Field(..., description="Total number of tools matching filters")
    limit: int
    offset: int


# ============================================================================
# find_tool Endpoint
# ============================================================================

class FindToolRequest(BaseModel):
    """Request schema for find_tool endpoint (semantic search)."""

    query: str = Field(..., min_length=1, description="Natural language search query")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of results")
    threshold: float = Field(
        0.7, ge=0.0, le=1.0, description="Minimum similarity threshold (0-1)"
    )
    category: Optional[str] = Field(None, description="Filter by category")
    use_hybrid: bool = Field(
        True, description="Use hybrid search (vector + text) for better results"
    )


class FindToolResponse(BaseModel):
    """Response schema for find_tool endpoint."""

    results: List[ToolWithScore]
    query: str
    count: int = Field(..., description="Number of results returned")


# ============================================================================
# call_tool Endpoint
# ============================================================================

class CallToolRequest(BaseModel):
    """Request schema for call_tool endpoint."""

    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Input arguments for the tool"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional execution metadata"
    )


class CallToolResponse(BaseModel):
    """Response schema for call_tool endpoint."""

    success: bool
    tool_name: str
    execution_id: int = Field(..., description="ID of the execution record")
    output: Optional[Dict[str, Any]] = Field(None, description="Tool execution output")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    execution_time_ms: Optional[int] = Field(
        None, description="Execution duration in milliseconds"
    )


# ============================================================================
# Error Responses
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# ============================================================================
# Registration Schemas (for admin/management endpoints)
# ============================================================================

class RegisterToolRequest(BaseModel):
    """Request schema for registering a new tool."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=100)
    input_schema: Dict[str, Any] = Field(
        ..., description="JSON Schema for input validation"
    )
    tags: List[str] = Field(default_factory=list)
    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for output"
    )
    implementation_type: str = Field(
        "python_function", description="Type of implementation"
    )
    implementation_code: Optional[str] = Field(
        None, description="Implementation code or reference"
    )
    version: str = Field("1.0.0", description="Tool version")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    auto_embed: bool = Field(True, description="Automatically generate embedding")


class RegisterToolResponse(BaseModel):
    """Response schema for tool registration."""

    success: bool
    tool: ToolSchema
    message: str = "Tool registered successfully"


class UpdateToolRequest(BaseModel):
    """Request schema for updating a tool."""

    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    implementation_code: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateToolResponse(BaseModel):
    """Response schema for tool update."""

    success: bool
    tool: ToolSchema
    message: str = "Tool updated successfully"


# ============================================================================
# Stats and Analytics
# ============================================================================

class ToolStatsResponse(BaseModel):
    """Response schema for tool statistics."""

    tool_id: int
    tool_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float = Field(..., ge=0.0, le=1.0)
    avg_execution_time_ms: Optional[float] = None


class ComponentHealth(BaseModel):
    """Health status for a single component."""

    healthy: bool = Field(..., description="Whether the component is healthy")
    latency_ms: Optional[float] = Field(None, description="Health check latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str
    version: str
    database: bool = Field(..., description="Database connectivity status")
    embedding_service: bool = Field(..., description="Embedding service status")
    indexed_tools: int = Field(..., description="Number of tools with embeddings")


class DetailedHealthCheckResponse(BaseModel):
    """Detailed health check response with component-level status."""

    status: str = Field(..., description="Overall status: healthy, degraded, or unhealthy")
    service: str
    version: str
    components: Dict[str, ComponentHealth] = Field(
        ..., description="Health status for each component"
    )
    indexed_tools: int = Field(..., description="Number of tools with embeddings")


class ReadinessResponse(BaseModel):
    """Response model for readiness check."""

    status: str = Field(..., description="ready or not_ready")
    service: str
    error: Optional[str] = Field(None, description="Error message if not ready")
