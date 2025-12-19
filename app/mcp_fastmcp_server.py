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
from typing import Any

from fastmcp import FastMCP

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.registry import ToolRegistry
from app.execution.executor import ToolExecutor
from app.services.summarization import get_summarization_service

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
    category: str | None = None,
) -> dict[str, Any]:
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
    arguments: dict[str, Any],
) -> dict[str, Any]:
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
async def call_tool_summarized(
    tool_name: str,
    arguments: dict[str, Any],
    max_tokens: int = 2000,
    summarization_context: str | None = None,
) -> dict[str, Any]:
    """
    Execute a registered tool and summarize the output if it exceeds the token limit.

    Use this instead of call_tool when you expect large outputs (logs, documents,
    API responses) and want to reduce token usage. The output will be automatically
    summarized using an LLM if it exceeds max_tokens.

    Args:
        tool_name: The exact name of the tool to execute (e.g., "confluence:search_docs")
        arguments: Dictionary of arguments matching the tool's input_schema
        max_tokens: Maximum output tokens before summarization kicks in (default: 2000)
                   Set higher (e.g., 5000) if you need more detail
                   Set lower (e.g., 500) for brief summaries
        summarization_context: Optional hint about what information is important
                              Example: "Focus on error messages and stack traces"
                              Example: "Extract only the deployment status"

    Returns:
        Dictionary with:
        - success: Whether the tool executed successfully
        - tool_name: Name of the executed tool
        - output: Tool output (possibly summarized)
        - was_summarized: True if output was summarized, False if original
        - original_tokens_estimate: Estimated tokens of original output (if summarized)
        - execution_time_ms: Tool execution time in milliseconds
        - error: Error message if execution failed
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        executor = ToolExecutor()
        summarization_service = get_summarization_service()

        try:
            # Find the tool by name (same as call_tool)
            tool = await registry.get_tool_by_name(tool_name)

            if not tool:
                # Try to find similar tools to suggest
                similar = await registry.find_tool(query=tool_name, limit=3)
                suggestions = [t.name for t, _ in similar] if similar else []

                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "suggestions": suggestions,
                    "was_summarized": False,
                }

            if not tool.is_active:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' is currently inactive",
                    "was_summarized": False,
                }

            # Execute the tool
            result = await executor.execute_tool(
                tool=tool,
                arguments=arguments,
            )

            if not result.get("success"):
                # Don't summarize error responses - return as-is
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "output": result.get("output"),
                    "error": result.get("error_message"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "was_summarized": False,
                }

            # Get the raw output
            raw_output = result.get("output")

            # Summarize if needed
            processed_output, was_summarized = await summarization_service.summarize_if_needed(
                content=raw_output,
                max_tokens=max_tokens,
                user_query=summarization_context,
                tool_name=tool_name,
            )

            response = {
                "success": True,
                "tool_name": tool_name,
                "output": processed_output,
                "was_summarized": was_summarized,
                "execution_time_ms": result.get("execution_time_ms"),
                "error": None,
            }

            # Add original token estimate if summarized
            if was_summarized:
                from app.services.summarization import estimate_tokens, serialize_output
                original_str = serialize_output(raw_output)
                response["original_tokens_estimate"] = estimate_tokens(original_str)
                response["summarized_tokens_estimate"] = estimate_tokens(processed_output)

            return response

        except Exception as e:
            logger.error(f"Error in call_tool_summarized: {e}")
            return {
                "success": False,
                "tool_name": tool_name,
                "error": str(e),
                "was_summarized": False,
            }


@mcp.tool
async def list_tools(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
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
async def get_tool_schema(tool_name: str) -> dict[str, Any]:
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


# ============================================================================
# FastMCP Resources
# ============================================================================

@mcp.resource("toolbox://categories")
async def get_categories() -> str:
    """
    Get all available tool categories in the registry.

    Returns a list of unique categories that can be used to filter tools.
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        try:
            tools = await registry.list_tools(active_only=True, limit=1000)
            categories = sorted(set(tool.category for tool in tools if tool.category))
            return json.dumps({
                "categories": categories,
                "total": len(categories),
            }, indent=2)
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return json.dumps({"error": str(e), "categories": []})


@mcp.resource("toolbox://stats")
async def get_registry_stats() -> str:
    """
    Get overall statistics about the tool registry.

    Returns counts of tools by category, active/inactive status, etc.
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        try:
            all_tools = await registry.list_tools(active_only=False, limit=10000)
            active_tools = [t for t in all_tools if t.is_active]

            # Count by category
            categories: dict[str, int] = {}
            for tool in active_tools:
                cat = tool.category or "uncategorized"
                categories[cat] = categories.get(cat, 0) + 1

            # Count by implementation type
            impl_types: dict[str, int] = {}
            for tool in active_tools:
                impl = str(tool.implementation_type) if tool.implementation_type else "unknown"
                impl_types[impl] = impl_types.get(impl, 0) + 1

            return json.dumps({
                "total_tools": len(all_tools),
                "active_tools": len(active_tools),
                "inactive_tools": len(all_tools) - len(active_tools),
                "tools_by_category": categories,
                "tools_by_implementation_type": impl_types,
            }, indent=2)
        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return json.dumps({"error": str(e)})


@mcp.resource("toolbox://tools/{category}")
async def get_tools_by_category(category: str) -> str:
    """
    Get all tools in a specific category.

    Args:
        category: The category name to filter by
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        try:
            tools = await registry.list_tools(
                category=category,
                active_only=True,
                limit=1000,
            )
            tools_data = [
                {
                    "name": t.name,
                    "description": t.description,
                    "tags": t.tags or [],
                    "version": t.version,
                }
                for t in tools
            ]
            return json.dumps({
                "category": category,
                "total": len(tools_data),
                "tools": tools_data,
            }, indent=2)
        except Exception as e:
            logger.error(f"Error getting tools by category: {e}")
            return json.dumps({"error": str(e), "tools": []})


# ============================================================================
# FastMCP Prompts
# ============================================================================

@mcp.prompt
def tool_discovery_prompt(task_description: str) -> str:
    """
    Generate a prompt for discovering relevant tools for a task.

    Args:
        task_description: Description of what the user wants to accomplish
    """
    return f"""I need to find tools that can help with the following task:

Task: {task_description}

Please use the find_tools function to search for relevant tools. Consider:
1. Breaking down the task into sub-tasks if needed
2. Searching with different query variations
3. Checking tool input schemas to ensure they match requirements

After finding tools, summarize:
- Which tools are most relevant
- What arguments each tool requires
- Any limitations or considerations"""


@mcp.prompt
def tool_execution_prompt(tool_name: str, task_context: str) -> str:
    """
    Generate a prompt for executing a specific tool.

    Args:
        tool_name: Name of the tool to execute
        task_context: Context about what the user wants to accomplish
    """
    return f"""I need to execute the tool "{tool_name}" for the following purpose:

Context: {task_context}

Please:
1. First use get_tool_schema to get the full input schema for "{tool_name}"
2. Construct the appropriate arguments based on the schema and context
3. Execute the tool using call_tool
4. Interpret and summarize the results

If the tool fails, suggest alternative approaches or tools."""


@mcp.prompt
def workflow_planning_prompt(goal: str, constraints: str | None = None) -> str:
    """
    Generate a prompt for planning a multi-tool workflow.

    Args:
        goal: The end goal to achieve
        constraints: Optional constraints or requirements
    """
    constraints_section = f"\nConstraints: {constraints}" if constraints else ""
    return f"""I need to plan a workflow to achieve the following goal:

Goal: {goal}{constraints_section}

Please:
1. Use list_tools or find_tools to discover available capabilities
2. Identify which tools can contribute to the goal
3. Plan the sequence of tool calls needed
4. Consider data flow between tools (output of one as input to another)
5. Identify any gaps where no suitable tool exists

Provide a step-by-step plan with:
- Tool name for each step
- Required inputs and where they come from
- Expected outputs
- Error handling considerations"""


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
