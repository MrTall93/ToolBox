"""
MCP Server Discovery Service.

This service discovers and syncs tools from external MCP servers into the Toolbox registry.
It supports both HTTP-based MCP servers and stdio-based MCP servers via command execution.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Tuple
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tool import Tool, ImplementationType
from app.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""
    name: str
    url: Optional[str] = None  # For HTTP-based MCP servers
    command: Optional[List[str]] = None  # For stdio-based MCP servers
    description: Optional[str] = None
    enabled: bool = True
    category: Optional[str] = None  # Default category for tools from this server
    tags: Optional[List[str]] = None  # Default tags for tools from this server


class MCPTool(BaseModel):
    """Tool definition from an MCP server."""
    name: str
    description: str = ""
    inputSchema: Dict[str, Any] = Field(default_factory=dict, alias="input_schema")

    class Config:
        populate_by_name = True


class MCPDiscoveryService:
    """
    Service for discovering and syncing tools from MCP servers.

    This service:
    - Connects to configured MCP servers (HTTP or stdio-based)
    - Fetches available tools from each server
    - Registers tools in the Toolbox registry with embeddings
    - Maintains tool metadata for routing calls back to source servers
    """

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the MCP discovery service.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def discover_tools_from_http_server(
        self,
        server_url: str,
        server_name: str = "unknown"
    ) -> List[MCPTool]:
        """
        Discover tools from an HTTP-based MCP server.

        Args:
            server_url: Base URL of the MCP server
            server_name: Name identifier for the server

        Returns:
            List of discovered tools
        """
        client = await self._get_client()
        server_url = server_url.rstrip('/')

        tools = []

        # Try different endpoints that MCP servers might expose
        endpoints_to_try = [
            f"{server_url}/tools/list",
            f"{server_url}/tools",
            f"{server_url}/mcp",
            f"{server_url}/list_tools",
        ]

        for endpoint in endpoints_to_try:
            try:
                # Try GET first
                response = await client.get(endpoint)
                if response.status_code == 200:
                    data = response.json()
                    tools = self._parse_tools_response(data)
                    if tools:
                        self.logger.info(
                            f"Discovered {len(tools)} tools from {server_name} at {endpoint}"
                        )
                        return tools
            except Exception as e:
                self.logger.debug(f"GET {endpoint} failed: {e}")

            try:
                # Try POST for JSON-RPC style
                response = await client.post(
                    endpoint,
                    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
                )
                if response.status_code == 200:
                    data = response.json()
                    tools = self._parse_tools_response(data)
                    if tools:
                        self.logger.info(
                            f"Discovered {len(tools)} tools from {server_name} at {endpoint} (JSON-RPC)"
                        )
                        return tools
            except Exception as e:
                self.logger.debug(f"POST {endpoint} (JSON-RPC) failed: {e}")

        self.logger.warning(f"No tools found from {server_name} at {server_url}")
        return []

    def _parse_tools_response(self, data: Any) -> List[MCPTool]:
        """Parse tools from various response formats."""
        tools = []

        if isinstance(data, dict):
            # Handle JSON-RPC response
            if "result" in data:
                data = data["result"]

            # Handle {"tools": [...]} format
            if "tools" in data:
                tool_list = data["tools"]
            else:
                tool_list = [data]
        elif isinstance(data, list):
            tool_list = data
        else:
            return []

        for tool_data in tool_list:
            try:
                if isinstance(tool_data, dict):
                    # Normalize field names
                    name = tool_data.get("name", "")
                    description = tool_data.get("description", "")
                    input_schema = tool_data.get("inputSchema") or tool_data.get("input_schema", {})

                    if name:
                        tools.append(MCPTool(
                            name=name,
                            description=description,
                            inputSchema=input_schema
                        ))
            except Exception as e:
                self.logger.warning(f"Failed to parse tool: {e}")
                continue

        return tools

    async def discover_tools_from_stdio_server(
        self,
        command: List[str],
        server_name: str = "unknown"
    ) -> List[MCPTool]:
        """
        Discover tools from a stdio-based MCP server.

        Args:
            command: Command to start the MCP server
            server_name: Name identifier for the server

        Returns:
            List of discovered tools
        """
        try:
            # Start the MCP server process
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Send tools/list request
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 1
            }) + "\n"

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=request.encode()),
                timeout=self.timeout
            )

            if stdout:
                for line in stdout.decode().strip().split('\n'):
                    try:
                        response = json.loads(line)
                        if "result" in response:
                            tools = self._parse_tools_response(response)
                            if tools:
                                self.logger.info(
                                    f"Discovered {len(tools)} tools from {server_name} (stdio)"
                                )
                                return tools
                    except json.JSONDecodeError:
                        continue

            self.logger.warning(f"No tools found from {server_name} (stdio)")
            return []

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout discovering tools from {server_name}")
            return []
        except Exception as e:
            self.logger.error(f"Error discovering tools from {server_name}: {e}")
            return []

    async def sync_tools_to_registry(
        self,
        session: AsyncSession,
        server_config: MCPServerConfig,
        tools: List[MCPTool]
    ) -> Tuple[int, int, int]:
        """
        Sync discovered tools to the Toolbox registry.

        Args:
            session: Database session
            server_config: Configuration of the source MCP server
            tools: List of discovered tools

        Returns:
            Tuple of (created_count, updated_count, skipped_count)
        """
        registry = ToolRegistry(session=session)
        created = 0
        updated = 0
        skipped = 0

        for mcp_tool in tools:
            try:
                # Create unique name with server prefix to avoid conflicts
                tool_name = f"{server_config.name}:{mcp_tool.name}"

                # Check if tool already exists
                existing_tool = await registry.get_tool_by_name(tool_name)

                # Build implementation config for MCP server routing
                if server_config.url:
                    implementation_config = json.dumps({
                        "type": "mcp_http",
                        "server_name": server_config.name,
                        "server_url": server_config.url,
                        "tool_name": mcp_tool.name,
                    })
                elif server_config.command:
                    implementation_config = json.dumps({
                        "type": "mcp_stdio",
                        "server_name": server_config.name,
                        "command": server_config.command,
                        "tool_name": mcp_tool.name,
                    })
                else:
                    self.logger.warning(f"No URL or command for server {server_config.name}")
                    skipped += 1
                    continue

                # Prepare tool metadata
                metadata = {
                    "source": "mcp_discovery",
                    "mcp_server": server_config.name,
                    "mcp_server_description": server_config.description,
                    "original_name": mcp_tool.name,
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }

                if existing_tool:
                    # Update existing tool
                    await registry.update_tool(
                        existing_tool.id,
                        description=mcp_tool.description or f"Tool from {server_config.name}",
                        input_schema=mcp_tool.inputSchema or {"type": "object", "properties": {}},
                        implementation_code=implementation_config,
                        metadata=metadata,
                    )
                    updated += 1
                    self.logger.debug(f"Updated tool: {tool_name}")
                else:
                    # Create new tool
                    await registry.register_tool(
                        name=tool_name,
                        description=mcp_tool.description or f"Tool from {server_config.name}",
                        category=server_config.category or "mcp",
                        input_schema=mcp_tool.inputSchema or {"type": "object", "properties": {}},
                        tags=server_config.tags or ["mcp", server_config.name],
                        implementation_type="mcp_server",
                        implementation_code=implementation_config,
                        metadata=metadata,
                        auto_embed=True,
                    )
                    created += 1
                    self.logger.info(f"Registered new tool: {tool_name}")

            except Exception as e:
                self.logger.error(f"Failed to sync tool {mcp_tool.name}: {e}")
                skipped += 1
                continue

        return created, updated, skipped

    async def sync_all_servers(
        self,
        session: AsyncSession,
        server_configs: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Sync tools from all configured MCP servers.

        Args:
            session: Database session
            server_configs: Optional list of server configs (uses settings if not provided)

        Returns:
            Summary of sync operation
        """
        if server_configs is None:
            server_configs = settings.MCP_SERVERS

        results = {
            "total_servers": len(server_configs),
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_tools_created": 0,
            "total_tools_updated": 0,
            "total_tools_skipped": 0,
            "servers": {}
        }

        for config_dict in server_configs:
            try:
                config = MCPServerConfig(**config_dict)

                if not config.enabled:
                    self.logger.info(f"Skipping disabled server: {config.name}")
                    continue

                self.logger.info(f"Syncing tools from MCP server: {config.name}")

                # Discover tools
                tools = []
                if config.url:
                    tools = await self.discover_tools_from_http_server(
                        config.url, config.name
                    )
                elif config.command:
                    tools = await self.discover_tools_from_stdio_server(
                        config.command, config.name
                    )
                else:
                    self.logger.warning(f"Server {config.name} has no URL or command")
                    results["failed_syncs"] += 1
                    results["servers"][config.name] = {"status": "error", "error": "No URL or command"}
                    continue

                if not tools:
                    results["servers"][config.name] = {
                        "status": "no_tools",
                        "tools_found": 0
                    }
                    continue

                # Sync to registry
                created, updated, skipped = await self.sync_tools_to_registry(
                    session, config, tools
                )

                results["successful_syncs"] += 1
                results["total_tools_created"] += created
                results["total_tools_updated"] += updated
                results["total_tools_skipped"] += skipped
                results["servers"][config.name] = {
                    "status": "success",
                    "tools_found": len(tools),
                    "created": created,
                    "updated": updated,
                    "skipped": skipped
                }

            except Exception as e:
                self.logger.error(f"Failed to sync server {config_dict.get('name', 'unknown')}: {e}")
                results["failed_syncs"] += 1
                results["servers"][config_dict.get("name", "unknown")] = {
                    "status": "error",
                    "error": str(e)
                }

        # Sync from LiteLLM if enabled
        if settings.LITELLM_SYNC_ENABLED:
            self.logger.info("Syncing tools FROM LiteLLM...")
            litellm_results = await self.sync_from_liteLLM(session=session)
            results["litellm_sync"] = litellm_results

        return results

    async def sync_from_liteLLM(
        self,
        session: AsyncSession,
        tools: Optional[List[Tool]] = None
    ) -> Dict[str, Any]:
        """
        Sync tools FROM LiteLLM gateway.

        Note: LiteLLM's MCP integration doesn't expose a REST endpoint to list tools.
        Instead, LiteLLM acts as an MCP client that connects TO MCP servers.

        This method attempts to:
        1. Query LiteLLM's configured MCP servers directly
        2. Fall back to returning info about the current architecture

        Args:
            session: Database session

        Returns:
            Sync results
        """
        if not settings.LITELLM_SYNC_ENABLED:
            self.logger.info("LiteLLM sync is disabled")
            return {"status": "disabled", "message": "LiteLLM sync is disabled"}

        self.logger.info("Syncing tools FROM LiteLLM...")

        results = {
            "status": "info",
            "tools_synced": 0,
            "tools_updated": 0,
            "tools_deleted": 0,
            "errors": [],
            "message": ""
        }

        try:
            tls_cert_path = '/etc/ssl/certs/ca-custom.pem'
            verify_ssl = tls_cert_path if os.path.exists(tls_cert_path) else True
            # LiteLLM exposes MCP tools via /v1/mcp/tools endpoint
            async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                # LiteLLM uses x-litellm-api-key header for authentication
                if settings.LITELLM_MCP_API_KEY:
                    headers["x-litellm-api-key"] = settings.LITELLM_MCP_API_KEY

                # Get list of MCP tools from LiteLLM
                tools_url = f"{settings.LITELLM_MCP_SERVER_URL.rstrip('/')}/v1/mcp/tools"
                self.logger.info(f"Fetching MCP tools from LiteLLM: {tools_url}")

                tools_response = await client.get(tools_url, headers=headers)

                if tools_response.status_code == 200:
                    tools_data = tools_response.json()
                    self.logger.info(f"LiteLLM returned tools data: {type(tools_data)}")

                    # Process each tool from LiteLLM
                    tools_list = tools_data if isinstance(tools_data, list) else tools_data.get("tools", [])

                    # Track tool names from LiteLLM for deletion check
                    litellm_tool_names = set()

                    for tool_info in tools_list:
                        try:
                            tool_name = tool_info.get("name") or tool_info.get("function", {}).get("name")
                            tool_desc = tool_info.get("description") or tool_info.get("function", {}).get("description", "")
                            tool_schema = tool_info.get("inputSchema") or tool_info.get("input_schema") or tool_info.get("function", {}).get("parameters", {})

                            if not tool_name:
                                continue

                            # Track this tool name for deletion check
                            litellm_tool_names.add(tool_name)

                            # Check if tool already exists
                            from sqlalchemy import select
                            stmt = select(Tool).where(Tool.name == tool_name)
                            result = await session.execute(stmt)
                            existing_tool = result.scalar_one_or_none()

                            if existing_tool:
                                # Update existing tool
                                existing_tool.description = tool_desc
                                existing_tool.input_schema = tool_schema
                                existing_tool.implementation_type = ImplementationType.LITELLM
                                existing_tool.implementation_code = json.dumps({
                                    "source": "litellm",
                                    "tool_name": tool_name
                                })
                                results["tools_updated"] += 1
                                self.logger.info(f"Updated tool: {tool_name}")
                            else:
                                # Create new tool
                                new_tool = Tool(
                                    name=tool_name,
                                    description=tool_desc,
                                    input_schema=tool_schema,
                                    implementation_type=ImplementationType.LITELLM,
                                    implementation_code=json.dumps({
                                        "source": "litellm",
                                        "tool_name": tool_name
                                    }),
                                    category="litellm",
                                    tags=["litellm", "mcp"],
                                    is_active=True
                                )
                                session.add(new_tool)
                                results["tools_synced"] += 1
                                self.logger.info(f"Created tool: {tool_name}")

                            # Generate embedding for the tool
                            try:
                                tool_text = f"{tool_name} {tool_desc}"
                                from app.registry.embedding_service import get_embedding_service
                                embedding_service = get_embedding_service()
                                embedding = await embedding_service.generate_embedding(tool_text)

                                if existing_tool:
                                    existing_tool.embedding = embedding
                                else:
                                    new_tool.embedding = embedding
                            except Exception as embed_err:
                                self.logger.warning(f"Failed to generate embedding for {tool_name}: {embed_err}")

                        except Exception as e:
                            error_msg = f"Error processing tool {tool_info.get('name', 'unknown')}: {str(e)}"
                            results["errors"].append(error_msg)
                            self.logger.error(error_msg)

                    # Delete/deactivate tools that no longer exist in LiteLLM
                    # Find all tools that were synced from LiteLLM
                    from sqlalchemy import select
                    stmt = select(Tool).where(
                        Tool.implementation_type == ImplementationType.LITELLM,
                        Tool.is_active == True
                    )
                    result = await session.execute(stmt)
                    existing_litellm_tools = result.scalars().all()

                    for tool in existing_litellm_tools:
                        if tool.name not in litellm_tool_names:
                            # Tool no longer exists in LiteLLM, deactivate it
                            tool.is_active = False
                            results["tools_deleted"] += 1
                            self.logger.info(f"Deactivated tool (no longer in LiteLLM): {tool.name}")

                    # Commit all changes
                    await session.commit()
                    results["status"] = "success"
                    results["message"] = f"Synced {results['tools_synced']} new tools, updated {results['tools_updated']}, deleted {results['tools_deleted']} from LiteLLM"

                else:
                    error_msg = f"Failed to get tools from LiteLLM: {tools_response.status_code} - {tools_response.text}"
                    results["errors"].append(error_msg)
                    results["status"] = "error"
                    self.logger.error(error_msg)

        except Exception as e:
            error_msg = f"Failed to sync from LiteLLM: {str(e)}"
            results["errors"].append(error_msg)
            results["status"] = "error"
            self.logger.error(error_msg)

        self.logger.info(f"LiteLLM sync completed: {results['tools_synced']} created, {results['tools_updated']} updated, {results['tools_deleted']} deleted")
        return results


# Singleton instance
_discovery_service: Optional[MCPDiscoveryService] = None


def get_mcp_discovery_service() -> MCPDiscoveryService:
    """Get or create the MCP discovery service singleton."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = MCPDiscoveryService(timeout=settings.MCP_REQUEST_TIMEOUT)
    return _discovery_service
