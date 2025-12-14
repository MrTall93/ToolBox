"""
LiteLLM MCP Adapter for Tool Registry Integration.

This module provides compatibility between your Tool Registry MCP Server
and LiteLLM's gateway, enabling seamless tool discovery and execution
through the LiteLLM interface.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.schemas.mcp import ToolSchema

logger = logging.getLogger(__name__)


class LiteLLMTool(BaseModel):
    """LiteLLM-compatible tool representation."""
    type: str = "function"
    function: Dict[str, Any] = Field(...)

    @classmethod
    def from_mcp_tool(cls, tool: ToolSchema) -> "LiteLLMTool":
        """Convert MCP tool schema to LiteLLM format."""
        return cls(
            function={
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
                # Additional metadata for LiteLLM
                "metadata": {
                    "tool_id": tool.id,
                    "category": tool.category,
                    "tags": tool.tags,
                    "version": tool.version,
                    "implementation_type": tool.implementation_type,
                }
            }
        )


class LiteLLMToolCall(BaseModel):
    """LiteLLM tool call representation."""
    id: str
    type: str = "function"
    function: Dict[str, Any] = Field(...)

    @property
    def tool_name(self) -> str:
        """Extract tool name from function call."""
        return self.function.get("name", "")

    @property
    def arguments(self) -> Dict[str, Any]:
        """Extract arguments from function call."""
        args_str = self.function.get("arguments", "{}")
        try:
            import json
            return json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            return {}


class LiteLLMToolResult(BaseModel):
    """LiteLLM tool execution result."""
    tool_call_id: str
    role: str = "tool"
    content: Optional[Union[str, Dict[str, Any]]] = None
    error: Optional[str] = None

    @classmethod
    def success(cls, tool_call_id: str, result: Any) -> "LiteLLMToolResult":
        """Create successful tool result."""
        return cls(
            tool_call_id=tool_call_id,
            content=result if isinstance(result, str) else {"result": result}
        )

    @classmethod
    def error(cls, tool_call_id: str, error: str) -> "LiteLLMToolResult":
        """Create error tool result."""
        return cls(
            tool_call_id=tool_call_id,
            error=error
        )


class LiteLLMMCPAdapter:
    """
    Adapter for integrating Tool Registry MCP Server with LiteLLM.

    This adapter handles:
    - Tool discovery and formatting for LiteLLM
    - Tool execution through MCP protocol
    - Error handling and retry logic
    - Performance monitoring and logging
    """

    def __init__(
        self,
        mcp_server_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize the LiteLLM MCP adapter.

        Args:
            mcp_server_url: Base URL of the Tool Registry MCP Server
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        # HTTP client for MCP requests
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self._get_headers()
        )

        self.logger = logging.getLogger(__name__)

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for MCP requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LiteLLM-MCP-Adapter/1.0"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def list_tools(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True
    ) -> List[LiteLLMTool]:
        """
        List available tools from the Tool Registry.

        Args:
            limit: Maximum number of tools to return
            category: Filter by tool category
            tags: Filter by tool tags
            active_only: Return only active tools

        Returns:
            List of LiteLLM-compatible tools

        Raises:
            httpx.HTTPError: If MCP request fails
        """
        try:
            request_data = {
                "limit": limit,
                "active_only": active_only
            }

            if category:
                request_data["category"] = category
            if tags:
                request_data["tags"] = tags

            response = await self._make_mcp_request(
                endpoint="/list_tools",
                data=request_data
            )

            tools_data = response.get("tools", [])
            mcp_tools = [ToolSchema(**tool) for tool in tools_data]

            # Convert to LiteLLM format
            litellm_tools = [LiteLLMTool.from_mcp_tool(tool) for tool in mcp_tools]

            self.logger.info(f"Retrieved {len(litellm_tools)} tools from MCP server")
            return litellm_tools

        except Exception as e:
            self.logger.error(f"Failed to list tools: {str(e)}")
            raise

    async def find_tools(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
        use_hybrid_search: bool = True
    ) -> List[LiteLLMTool]:
        """
        Search for tools using semantic search.

        Args:
            query: Search query
            limit: Maximum number of results
            threshold: Similarity threshold (0.0-1.0)
            use_hybrid_search: Use hybrid search (semantic + keyword)

        Returns:
            List of LiteLLM-compatible tools

        Raises:
            httpx.HTTPError: If MCP request fails
        """
        try:
            request_data = {
                "query": query,
                "limit": limit,
                "threshold": threshold,
                "use_hybrid_search": use_hybrid_search
            }

            response = await self._make_mcp_request(
                endpoint="/find_tool",
                data=request_data
            )

            tools_data = response.get("results", [])
            mcp_tools = [ToolSchema(**tool["tool"]) for tool in tools_data]

            # Convert to LiteLLM format
            litellm_tools = [LiteLLMTool.from_mcp_tool(tool) for tool in mcp_tools]

            self.logger.info(f"Found {len(litellm_tools)} tools for query: '{query}'")
            return litellm_tools

        except Exception as e:
            self.logger.error(f"Failed to find tools: {str(e)}")
            raise

    async def call_tool(
        self,
        tool_call: LiteLLMToolCall,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LiteLLMToolResult:
        """
        Execute a tool through the MCP server.

        Args:
            tool_call: Tool call request from LiteLLM
            metadata: Optional execution metadata

        Returns:
            Tool execution result

        Raises:
            httpx.HTTPError: If MCP request fails
        """
        start_time = time.time()

        try:
            request_data = {
                "tool_name": tool_call.tool_name,
                "arguments": tool_call.arguments,
                "metadata": {
                    "litellm_adapter": True,
                    "tool_call_id": tool_call.id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **(metadata or {})
                }
            }

            response = await self._make_mcp_request(
                endpoint="/call_tool",
                data=request_data
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            if response.get("success", False):
                result = response.get("output", {})
                self.logger.info(
                    f"Tool '{tool_call.tool_name}' executed successfully "
                    f"in {execution_time_ms}ms"
                )
                return LiteLLMToolResult.success(tool_call.id, result)
            else:
                error_msg = response.get("error", "Unknown error")
                self.logger.error(
                    f"Tool '{tool_call.tool_name}' execution failed: {error_msg}"
                )
                return LiteLLMToolResult.error(tool_call.id, error_msg)

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Tool execution failed: {str(e)}"

            self.logger.error(f"Tool '{tool_call.tool_name}' error: {error_msg}")
            return LiteLLMToolResult.error(tool_call.id, error_msg)

    async def _make_mcp_request(
        self,
        endpoint: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make HTTP request to MCP server with retry logic.

        Args:
            endpoint: MCP endpoint (e.g., '/list_tools')
            data: Request data

        Returns:
            Response data from MCP server

        Raises:
            httpx.HTTPError: If all retry attempts fail
        """
        url = f"{self.mcp_server_url}/mcp{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.post(url, json=data)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                if attempt == self.max_retries:
                    raise

                wait_time = 2 ** attempt  # Exponential backoff
                self.logger.warning(
                    f"MCP request failed (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

    async def health_check(self) -> bool:
        """
        Check if MCP server is healthy.

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            url = f"{self.mcp_server_url}/health"
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json().get("status") == "healthy"

        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()


# Global adapter instance (can be configured via environment)
_adapter: Optional[LiteLLMMCPAdapter] = None


def get_litellm_mcp_adapter() -> LiteLLMMCPAdapter:
    """
    Get or create the global LiteLLM MCP adapter.

    Returns:
        Configured LiteLLM MCP adapter instance
    """
    global _adapter

    if _adapter is None:
        # Configuration from environment variables
        mcp_server_url = getattr(settings, 'LITELLM_MCP_SERVER_URL', 'http://localhost:8000')
        api_key = getattr(settings, 'LITELLM_MCP_API_KEY', None)
        timeout = getattr(settings, 'LITELLM_MCP_TIMEOUT', 30)
        max_retries = getattr(settings, 'LITELLM_MCP_MAX_RETRIES', 3)

        _adapter = LiteLLMMCPAdapter(
            mcp_server_url=mcp_server_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries
        )

    return _adapter


# Add LiteLLM integration settings to config
def register_litellm_settings():
    """Register LiteLLM-related settings with the application config."""
    # These would be added to app/config.py Settings class
    pass