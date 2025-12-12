"""
MCP (Model Context Protocol) API endpoints.

Implements the three core MCP endpoints:
- POST /mcp/list_tools - List all available tools
- POST /mcp/find_tool - Semantic search for tools
- POST /mcp/call_tool - Execute a tool
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import time

from app.db.session import get_db
from app.registry import ToolRegistry
from app.execution.executor import executor
from app.schemas.mcp import (
    ListToolsRequest,
    ListToolsResponse,
    FindToolRequest,
    FindToolResponse,
    CallToolRequest,
    CallToolResponse,
    ToolSchema,
    ToolWithScore,
    ErrorResponse,
)
from app.models.execution import ExecutionStatus

router = APIRouter(prefix="/mcp", tags=["MCP Protocol"])


def get_tool_registry(db: AsyncSession = Depends(get_db)) -> ToolRegistry:
    """Dependency to get ToolRegistry instance."""
    return ToolRegistry(session=db)


@router.post(
    "/list_tools",
    response_model=ListToolsResponse,
    summary="List all tools",
    description="List all available tools with optional filtering by category and active status.",
)
async def list_tools(
    request: ListToolsRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ListToolsResponse:
    """
    List all available tools.

    Supports:
    - Category filtering
    - Active/inactive filtering
    - Pagination (limit/offset)

    Returns list of tools with metadata.
    """
    try:
        # Get tools from registry
        tools = await registry.list_tools(
            category=request.category,
            active_only=request.active_only,
            limit=request.limit,
            offset=request.offset,
        )

        # Convert to schema
        tool_schemas = [ToolSchema.model_validate(tool) for tool in tools]

        # Get total count (for pagination)
        # For now, just return the count we got
        # TODO: Add a proper count query for accurate pagination
        total = len(tool_schemas)

        return ListToolsResponse(
            tools=tool_schemas,
            total=total,
            limit=request.limit,
            offset=request.offset,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tools: {str(e)}",
        )


@router.post(
    "/find_tool",
    response_model=FindToolResponse,
    summary="Find tools using semantic search",
    description="Search for tools using natural language queries. "
    "Uses vector embeddings for semantic similarity or hybrid search (vector + text).",
)
async def find_tool(
    request: FindToolRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> FindToolResponse:
    """
    Find tools using semantic search.

    Supports:
    - Natural language queries
    - Vector similarity search
    - Hybrid search (vector + full-text)
    - Similarity threshold filtering
    - Category filtering

    Returns tools ranked by relevance with similarity scores.
    """
    try:
        # Perform semantic search
        results = await registry.find_tool(
            query=request.query,
            limit=request.limit,
            threshold=request.threshold,
            category=request.category,
            use_hybrid=request.use_hybrid,
        )

        # Convert to schema
        tool_results = [
            ToolWithScore(
                tool=ToolSchema.model_validate(tool),
                score=round(score, 4),  # Round to 4 decimal places
            )
            for tool, score in results
        ]

        return FindToolResponse(
            results=tool_results,
            query=request.query,
            count=len(tool_results),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search tools: {str(e)}",
        )


@router.post(
    "/call_tool",
    response_model=CallToolResponse,
    summary="Execute a tool",
    description="Execute a tool by name with provided arguments. "
    "Records execution history and returns results.",
)
async def call_tool(
    request: CallToolRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> CallToolResponse:
    """
    Execute a tool.

    Looks up the tool by name, validates it exists and is active,
    executes the tool based on its implementation type, and records
    the execution with full input validation and output validation.

    Returns execution results with timing information.
    """
    start_time = time.time()

    try:
        # Get tool by name
        tool = await registry.get_tool_by_name(request.tool_name)

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{request.tool_name}' not found",
            )

        if not tool.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tool '{request.tool_name}' is not active",
            )

        # Execute the tool
        execution_result = await executor.execute_tool(
            tool=tool,
            arguments=request.arguments,
            metadata=request.metadata
        )

        # Record execution in database
        execution = await registry.record_execution(
            tool_id=tool.id,
            input_data=request.arguments,
            output_data=execution_result["output"] if execution_result["success"] else None,
            status=execution_result["status"],
            execution_time_ms=execution_result["execution_time_ms"],
            error_message=execution_result["error_message"],
            metadata=request.metadata,
        )

        # Return response based on execution result
        if execution_result["success"]:
            return CallToolResponse(
                success=True,
                tool_name=request.tool_name,
                execution_id=execution.id,
                output=execution_result["output"],
                execution_time_ms=execution_result["execution_time_ms"],
            )
        else:
            return CallToolResponse(
                success=False,
                tool_name=request.tool_name,
                execution_id=execution.id,
                error=execution_result["error_message"],
                execution_time_ms=execution_result["execution_time_ms"],
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Record failed execution if we have the tool
        execution_time_ms = int((time.time() - start_time) * 1000)

        try:
            tool = await registry.get_tool_by_name(request.tool_name)
            if tool:
                execution = await registry.record_execution(
                    tool_id=tool.id,
                    input_data=request.arguments,
                    status=ExecutionStatus.FAILED,
                    error_message=str(e),
                    execution_time_ms=execution_time_ms,
                    metadata=request.metadata,
                )

                return CallToolResponse(
                    success=False,
                    tool_name=request.tool_name,
                    execution_id=execution.id,
                    error=str(e),
                    execution_time_ms=execution_time_ms,
                )
        except Exception:
            pass  # Ignore errors during error recording

        # Return error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}",
        )
