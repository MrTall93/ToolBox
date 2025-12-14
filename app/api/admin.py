"""
Admin API endpoints for tool management.

Provides CRUD operations for tools:
- POST /admin/tools - Register a new tool
- GET /admin/tools/{tool_id} - Get tool details
- PUT /admin/tools/{tool_id} - Update a tool
- DELETE /admin/tools/{tool_id} - Delete a tool
- GET /admin/tools/{tool_id}/stats - Get tool statistics
- POST /admin/tools/{tool_id}/reindex - Regenerate embedding
- POST /admin/mcp/sync - Sync tools from MCP servers
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.db.session import get_db
from app.middleware.auth import require_auth
from app.registry import ToolRegistry
from app.schemas.mcp import (
    RegisterToolRequest,
    RegisterToolResponse,
    UpdateToolRequest,
    UpdateToolResponse,
    ToolSchema,
    ToolStatsResponse,
)
from app.services.mcp_discovery import get_mcp_discovery_service, MCPServerConfig

# Import OpenTelemetry functions if enabled
from app.config import settings
if settings.OTEL_ENABLED:
    from app.observability import (
        record_registry_operation,
        update_registry_tools_count,
        create_span,
        add_span_event,
        record_litellm_sync_operation
    )

router = APIRouter(prefix="/admin", tags=["Admin"])


def get_tool_registry(db: AsyncSession = Depends(get_db)) -> ToolRegistry:
    """Dependency to get ToolRegistry instance."""
    return ToolRegistry(session=db)


@router.post(
    "/tools",
    response_model=RegisterToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tool",
    description="Register a new tool in the registry with automatic embedding generation.",
)
async def register_tool(
    request: RegisterToolRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> RegisterToolResponse:
    """
    Register a new tool.

    Automatically generates embeddings for semantic search unless auto_embed=False.
    """
    # Create span for operation if OpenTelemetry is enabled
    span = None
    if settings.OTEL_ENABLED:
        span = create_span(
            name="admin.register_tool",
            attributes={
                "tool.name": request.name,
                "tool.category": request.category or "unknown",
                "tool.auto_embed": str(request.auto_embed),
            }
        )
        add_span_event("tool_registration_started", {
            "tool_name": request.name,
            "category": request.category
        })

    start_time = time.time()
    success = False

    try:
        tool = await registry.register_tool(
            name=request.name,
            description=request.description,
            category=request.category,
            input_schema=request.input_schema,
            tags=request.tags,
            output_schema=request.output_schema,
            implementation_type=request.implementation_type,
            implementation_code=request.implementation_code,
            version=request.version,
            metadata=request.metadata,
            auto_embed=request.auto_embed,
        )

        success = True

        # Record metrics
        if settings.OTEL_ENABLED:
            record_registry_operation("register", success=True)
            add_span_event("tool_registered", {
                "tool_id": tool.id,
                "tool_name": tool.name
            })

        return RegisterToolResponse(
            success=True,
            tool=ToolSchema.model_validate(tool),
            message=f"Tool '{tool.name}' registered successfully",
        )

    except ValueError as e:
        if settings.OTEL_ENABLED:
            record_registry_operation("register", success=False)
            add_span_event("tool_registration_failed", {
                "error": str(e),
                "error_type": "ValidationError"
            })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        if settings.OTEL_ENABLED:
            record_registry_operation("register", success=False)
            add_span_event("tool_registration_failed", {
                "error": str(e),
                "error_type": "InternalServerError"
            })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register tool: {str(e)}",
        )
    finally:
        if span:
            span.set_attribute("operation.duration", time.time() - start_time)
            span.set_attribute("operation.success", str(success))
            span.end()


@router.get(
    "/tools/{tool_id}",
    response_model=ToolSchema,
    summary="Get tool details",
    description="Get detailed information about a specific tool.",
)
async def get_tool(
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> ToolSchema:
    """Get tool by ID."""
    tool = await registry.get_tool(tool_id)

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with id {tool_id} not found",
        )

    return ToolSchema.model_validate(tool)


@router.put(
    "/tools/{tool_id}",
    response_model=UpdateToolResponse,
    summary="Update a tool",
    description="Update tool properties. Automatically regenerates embeddings if content changes.",
)
async def update_tool(
    request: UpdateToolRequest,
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> UpdateToolResponse:
    """
    Update a tool.

    Only provided fields will be updated. Automatically regenerates
    embeddings if name, description, category, or tags are changed.
    """
    try:
        # Build updates dict from request (exclude None values)
        updates = request.model_dump(exclude_unset=True, exclude_none=True)

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        tool = await registry.update_tool(tool_id, **updates)

        return UpdateToolResponse(
            success=True,
            tool=ToolSchema.model_validate(tool),
            message=f"Tool '{tool.name}' updated successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tool: {str(e)}",
        )


@router.delete(
    "/tools/{tool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tool",
    description="Permanently delete a tool from the registry.",
)
async def delete_tool(
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> None:
    """
    Delete a tool.

    This is a permanent deletion. Consider using deactivate instead
    for soft delete.
    """
    try:
        await registry.delete_tool(tool_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tool: {str(e)}",
        )


@router.post(
    "/tools/{tool_id}/deactivate",
    response_model=UpdateToolResponse,
    summary="Deactivate a tool",
    description="Soft delete - marks tool as inactive without removing it.",
)
async def deactivate_tool(
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> UpdateToolResponse:
    """Deactivate a tool (soft delete)."""
    try:
        await registry.deactivate_tool(tool_id)
        tool = await registry.get_tool(tool_id)

        return UpdateToolResponse(
            success=True,
            tool=ToolSchema.model_validate(tool),
            message=f"Tool deactivated successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/tools/{tool_id}/activate",
    response_model=UpdateToolResponse,
    summary="Activate a tool",
    description="Reactivate a previously deactivated tool.",
)
async def activate_tool(
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> UpdateToolResponse:
    """Activate a tool."""
    try:
        await registry.activate_tool(tool_id)
        tool = await registry.get_tool(tool_id)

        return UpdateToolResponse(
            success=True,
            tool=ToolSchema.model_validate(tool),
            message=f"Tool activated successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/tools/{tool_id}/stats",
    response_model=ToolStatsResponse,
    summary="Get tool statistics",
    description="Get execution statistics for a tool (total runs, success rate, avg execution time).",
)
async def get_tool_stats(
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> ToolStatsResponse:
    """Get execution statistics for a tool."""
    tool = await registry.get_tool(tool_id)

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with id {tool_id} not found",
        )

    stats = await registry.get_tool_stats(tool_id)

    # Calculate success rate
    total = stats["total_executions"]
    success_rate = (
        stats["successful_executions"] / total if total > 0 else 0.0
    )

    return ToolStatsResponse(
        tool_id=tool_id,
        tool_name=tool.name,
        total_executions=stats["total_executions"],
        successful_executions=stats["successful_executions"],
        failed_executions=stats["failed_executions"],
        success_rate=round(success_rate, 4),
        avg_execution_time_ms=stats["avg_execution_time_ms"],
    )


@router.post(
    "/tools/{tool_id}/reindex",
    response_model=UpdateToolResponse,
    summary="Regenerate tool embedding",
    description="Manually regenerate the embedding for a tool.",
)
async def reindex_tool(
    tool_id: int = Path(..., description="Tool ID"),
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> UpdateToolResponse:
    """Regenerate embedding for a tool."""
    try:
        await registry.update_tool_embedding(tool_id)
        tool = await registry.get_tool(tool_id)

        return UpdateToolResponse(
            success=True,
            tool=ToolSchema.model_validate(tool),
            message=f"Tool embedding regenerated successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reindex tool: {str(e)}",
        )


# ============================================================================
# MCP Server Sync Endpoints
# ============================================================================


class MCPSyncRequest(BaseModel):
    """Request model for MCP sync."""
    servers: Optional[List[Dict[str, Any]]] = None  # Override configured servers


class MCPSyncResponse(BaseModel):
    """Response model for MCP sync."""
    success: bool
    total_servers: int
    successful_syncs: int
    failed_syncs: int
    total_tools_created: int
    total_tools_updated: int
    total_tools_skipped: int
    servers: Dict[str, Any]


@router.post(
    "/mcp/sync",
    response_model=MCPSyncResponse,
    summary="Sync tools from MCP servers",
    description="Discover and sync tools from configured MCP servers into the Toolbox registry.",
)
async def sync_mcp_servers(
    request: MCPSyncRequest = Body(default=MCPSyncRequest()),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> MCPSyncResponse:
    """
    Sync tools from MCP servers.

    This endpoint:
    1. Connects to each configured MCP server
    2. Discovers available tools
    3. Registers or updates tools in the Toolbox registry
    4. Generates embeddings for semantic search

    You can optionally provide a list of servers to sync instead of using
    the configured servers from settings.
    """
    try:
        discovery_service = get_mcp_discovery_service()
        results = await discovery_service.sync_all_servers(
            session=db,
            server_configs=request.servers
        )

        return MCPSyncResponse(
            success=results["failed_syncs"] == 0,
            total_servers=results["total_servers"],
            successful_syncs=results["successful_syncs"],
            failed_syncs=results["failed_syncs"],
            total_tools_created=results["total_tools_created"],
            total_tools_updated=results["total_tools_updated"],
            total_tools_skipped=results["total_tools_skipped"],
            servers=results["servers"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync MCP servers: {str(e)}",
        )


@router.post(
    "/mcp/sync/server",
    response_model=MCPSyncResponse,
    summary="Sync tools from a single MCP server",
    description="Discover and sync tools from a specific MCP server.",
)
async def sync_single_mcp_server(
    server: MCPServerConfig = Body(...),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> MCPSyncResponse:
    """
    Sync tools from a single MCP server.

    Provide the server configuration directly in the request body.
    """
    try:
        discovery_service = get_mcp_discovery_service()
        results = await discovery_service.sync_all_servers(
            session=db,
            server_configs=[server.model_dump()]
        )

        return MCPSyncResponse(
            success=results["failed_syncs"] == 0,
            total_servers=results["total_servers"],
            successful_syncs=results["successful_syncs"],
            failed_syncs=results["failed_syncs"],
            total_tools_created=results["total_tools_created"],
            total_tools_updated=results["total_tools_updated"],
            total_tools_skipped=results["total_tools_skipped"],
            servers=results["servers"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync MCP server: {str(e)}",
        )


@router.post(
    "/mcp/sync-from-liteLLM",
    summary="Sync tools from LiteLLM",
    description="Sync all tools from LiteLLM gateway to Toolbox.",
)
async def sync_from_liteLLM(
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Sync tools from LiteLLM gateway.

    This endpoint:
    1. Connects to LiteLLM's MCP endpoint
    2. Retrieves all registered tools
    3. Creates or updates tools in Toolbox
    """
    # Create span for operation if OpenTelemetry is enabled
    span = None
    if settings.OTEL_ENABLED:
        span = create_span(
            name="admin.sync_from_liteLLM",
            attributes={
                "sync.source": "litellm",
                "sync.direction": "inbound"
            }
        )
        add_span_event("liteLLM_sync_started")

    start_time = time.time()
    success = False

    try:
        from app.services.mcp_discovery import get_mcp_discovery_service

        discovery_service = get_mcp_discovery_service()
        results = await discovery_service.sync_from_liteLLM(session=db)

        success = True
        total_tools = results.get("total_tools_created", 0) + results.get("total_tools_updated", 0)

        # Record sync metrics
        if settings.OTEL_ENABLED:
            record_litellm_sync_operation(
                server="litellm",
                tools_count=total_tools,
                duration=time.time() - start_time,
                success=True
            )
            add_span_event("liteLLM_sync_completed", {
                "tools_created": results.get("total_tools_created", 0),
                "tools_updated": results.get("total_tools_updated", 0),
                "tools_failed": results.get("total_tools_failed", 0)
            })

        return results

    except Exception as e:
        if settings.OTEL_ENABLED:
            record_litellm_sync_operation(
                server="litellm",
                tools_count=0,
                duration=time.time() - start_time,
                success=False
            )
            add_span_event("liteLLM_sync_failed", {
                "error": str(e),
                "error_type": type(e).__name__
            })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync from LiteLLM: {str(e)}",
        )
    finally:
        if span:
            span.set_attribute("operation.duration", time.time() - start_time)
            span.set_attribute("operation.success", str(success))
            span.end()
