"""
FastMCP-based MCP Server for Toolbox.

Exposes Toolbox as an MCP server using FastMCP with two main tools:
- find_tools: Semantic search to find relevant tools
- call_tool: Execute a registered tool by name

This makes Toolbox act as a "tool of tools" - an MCP server that helps
discover and invoke other tools from the registry.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.registry import ToolRegistry
from app.execution.executor import ToolExecutor

logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP(
    name="Toolbox",
    instructions="""
    Toolbox is a tool registry and execution engine. It provides two main capabilities:

    1. **find_tools**: Search for tools using natural language queries. Use this to discover
       what tools are available for a specific task.

    2. **call_tool**: Execute a tool by name with the required arguments. Use this after
       finding the right tool to actually run it.

    Typical workflow:
    1. Use find_tools to search for relevant tools (e.g., "calculator", "weather", "text processing")
    2. Review the returned tools and their input schemas
    3. Use call_tool to execute the chosen tool with appropriate arguments
    """,
)


@mcp.tool
async def find_tools(
    query: str,
    limit: int = 10,
    threshold: float = 0.5,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for tools using semantic search.

    Use this to discover available tools that match your needs.
    The search uses embeddings to find tools based on meaning, not just keywords.

    Args:
        query: Natural language description of what you're looking for
               (e.g., "calculate math expressions", "get weather data", "process text")
        limit: Maximum number of tools to return (default: 10)
        threshold: Minimum similarity score 0.0-1.0 (default: 0.5)
        category: Optional category filter (e.g., "math", "weather", "text")

    Returns:
        Dictionary with list of matching tools and their details
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)

        try:
            results = await registry.find_tool(
                query=query,
                limit=limit,
                threshold=threshold,
                category=category,
            )

            tools_list = []
            for tool, score in results:
                input_schema = tool.input_schema
                if isinstance(input_schema, str):
                    try:
                        input_schema = json.loads(input_schema)
                    except json.JSONDecodeError:
                        input_schema = {}

                tools_list.append({
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category,
                    "tags": tool.tags or [],
                    "similarity_score": round(score, 3),
                    "input_schema": input_schema,
                    "version": tool.version,
                })

            return {
                "query": query,
                "total_found": len(tools_list),
                "tools": tools_list,
            }

        except Exception as e:
            logger.error(f"Error in find_tools: {e}")
            return {
                "error": str(e),
                "query": query,
                "total_found": 0,
                "tools": [],
            }


@mcp.tool
async def call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a registered tool by name.

    Use this after finding the right tool with find_tools to actually run it.
    Make sure to provide all required arguments as specified in the tool's input_schema.

    Args:
        tool_name: The exact name of the tool to execute (e.g., "calculator:calculate")
        arguments: Dictionary of arguments matching the tool's input_schema

    Returns:
        Dictionary with execution results or error message
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        executor = ToolExecutor()

        try:
            # Find the tool by name
            tool = await registry.get_tool_by_name(tool_name)

            if not tool:
                # Try to find similar tools to suggest
                similar = await registry.find_tool(query=tool_name, limit=3)
                suggestions = [t.name for t, _ in similar] if similar else []

                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "suggestions": suggestions,
                }

            if not tool.is_active:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' is currently inactive",
                }

            # Execute the tool
            result = await executor.execute_tool(
                tool=tool,
                arguments=arguments,
            )

            return {
                "success": result.get("success", False),
                "tool_name": tool_name,
                "output": result.get("output"),
                "execution_time_ms": result.get("execution_time_ms"),
                "error": result.get("error_message") if not result.get("success") else None,
            }

        except Exception as e:
            logger.error(f"Error in call_tool: {e}")
            return {
                "success": False,
                "tool_name": tool_name,
                "error": str(e),
            }


@mcp.tool
async def list_tools(
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List all available tools in the registry.

    Use this to get an overview of all registered tools without searching.

    Args:
        category: Optional category filter
        limit: Maximum number of tools to return (default: 50)
        offset: Number of tools to skip for pagination (default: 0)

    Returns:
        Dictionary with list of all tools and pagination info
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)

        try:
            tools = await registry.list_tools(
                category=category,
                active_only=True,
                limit=limit,
                offset=offset,
            )

            tools_list = []
            for tool in tools:
                tools_list.append({
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category,
                    "tags": tool.tags or [],
                    "version": tool.version,
                })

            return {
                "total": len(tools_list),
                "offset": offset,
                "limit": limit,
                "tools": tools_list,
            }

        except Exception as e:
            logger.error(f"Error in list_tools: {e}")
            return {
                "error": str(e),
                "total": 0,
                "tools": [],
            }


@mcp.tool
async def get_tool_schema(tool_name: str) -> Dict[str, Any]:
    """
    Get the full schema and details for a specific tool.

    Use this to see the complete input/output schema before calling a tool.

    Args:
        tool_name: The exact name of the tool

    Returns:
        Dictionary with full tool details including input/output schemas
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)

        try:
            tool = await registry.get_tool_by_name(tool_name)

            if not tool:
                return {
                    "error": f"Tool '{tool_name}' not found",
                }

            input_schema = tool.input_schema
            if isinstance(input_schema, str):
                try:
                    input_schema = json.loads(input_schema)
                except json.JSONDecodeError:
                    input_schema = {}

            output_schema = tool.output_schema
            if isinstance(output_schema, str):
                try:
                    output_schema = json.loads(output_schema)
                except json.JSONDecodeError:
                    output_schema = {}

            return {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "tags": tool.tags or [],
                "version": tool.version,
                "is_active": tool.is_active,
                "input_schema": input_schema,
                "output_schema": output_schema,
                "implementation_type": str(tool.implementation_type),
            }

        except Exception as e:
            logger.error(f"Error in get_tool_schema: {e}")
            return {
                "error": str(e),
            }


# Run the server
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting Toolbox FastMCP Server")

    # Get the ASGI app from FastMCP
    fastmcp_app = mcp.http_app()

    # Create a wrapper FastAPI app with CORS
    # Pass lifespan from FastMCP app as required for session management
    app = FastAPI(title="Toolbox MCP Server", lifespan=fastmcp_app.lifespan)

    # Add CORS middleware for browser-based clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id", "X-Request-Id"],
    )

    # Mount the FastMCP app
    app.mount("/", fastmcp_app)

    # Run with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
