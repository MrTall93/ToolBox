"""Tool execution engine for running registered tools."""

import importlib
import json
import logging
import re
import shlex
import time
from typing import Any, Callable, Dict, Optional

import jsonschema

from app.models.execution import ExecutionStatus
from app.models.tool import Tool, ImplementationType
from app.config import settings

logger = logging.getLogger(__name__)

# OpenTelemetry imports (optional, only if enabled)
if settings.OTEL_ENABLED:
    from app.observability import (
        create_span,
        record_tool_execution,
        add_span_attributes,
        add_span_event
    )

# Registry of allowed Python functions for safe execution
_ALLOWED_FUNCTIONS: Dict[str, Callable] = {}


class ToolExecutor:
    """Executes tools based on their implementation type and code."""

    def __init__(self):
        """Initialize the tool executor."""
        self.logger = logging.getLogger(__name__)

    async def execute_tool(
        self,
        tool: Tool,
        arguments: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool with the given arguments.

        Args:
            tool: The tool to execute
            arguments: Input arguments for the tool
            metadata: Optional execution metadata

        Returns:
            Dictionary containing execution results and metadata

        Raises:
            ValueError: If tool configuration is invalid
            RuntimeError: If tool execution fails
        """
        # Create span for tool execution
        span = None
        if settings.OTEL_ENABLED:
            span = create_span(
                name=f"tool.execute.{tool.name}",
                attributes={
                    "tool.name": tool.name,
                    "tool.category": tool.category or "unknown",
                    "tool.implementation_type": tool.implementation_type.value,
                    "tool.id": str(tool.id),
                }
            )

        start_time = time.time()

        # Record execution attempt
        if settings.OTEL_ENABLED and span:
            add_span_event("execution.started", {
                "arguments_count": len(arguments),
                "timestamp": time.time()
            })

        try:
            # Validate input arguments against tool schema
            self._validate_input(tool, arguments)

            if settings.OTEL_ENABLED and span:
                add_span_event("validation.input_completed")

            # Execute based on implementation type
            result = await self._execute_by_type(tool, arguments)

            if settings.OTEL_ENABLED and span:
                add_span_event("execution.completed")

            # Validate output against tool output schema (if present)
            if tool.output_schema:
                self._validate_output(tool, result)

                if settings.OTEL_ENABLED and span:
                    add_span_event("validation.output_completed")

            execution_time_ms = int((time.time() - start_time) * 1000)
            execution_time_seconds = execution_time_ms / 1000.0

            # Record metrics
            if settings.OTEL_ENABLED:
                mcp_server = None
                if tool.implementation_code and isinstance(tool.implementation_code, dict):
                    mcp_server = tool.implementation_code.get("mcp_server_name")

                record_tool_execution(
                    tool_name=tool.name,
                    tool_category=tool.category or "unknown",
                    execution_time=execution_time_seconds,
                    success=True,
                    mcp_server=mcp_server
                )

                if span:
                    span.set_attribute("execution.time_ms", execution_time_ms)
                    span.set_attribute("execution.success", True)

            self.logger.info(
                f"Successfully executed tool '{tool.name}' in {execution_time_ms}ms"
            )

            return {
                "success": True,
                "output": result,
                "execution_time_ms": execution_time_ms,
                "status": ExecutionStatus.SUCCESS,
                "error_message": None,
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            execution_time_seconds = execution_time_ms / 1000.0
            error_message = str(e)
            error_type = type(e).__name__

            # Record metrics for failure
            if settings.OTEL_ENABLED:
                mcp_server = None
                if tool.implementation_code and isinstance(tool.implementation_code, dict):
                    mcp_server = tool.implementation_code.get("mcp_server_name")

                record_tool_execution(
                    tool_name=tool.name,
                    tool_category=tool.category or "unknown",
                    execution_time=execution_time_seconds,
                    success=False,
                    error_type=error_type,
                    mcp_server=mcp_server
                )

                if span:
                    span.set_attribute("execution.time_ms", execution_time_ms)
                    span.set_attribute("execution.success", False)
                    span.set_attribute("error.type", error_type)
                    span.set_attribute("error.message", error_message)
                    add_span_event("execution.failed", {
                        "error": error_message,
                        "error_type": error_type
                    })

            self.logger.error(
                f"Failed to execute tool '{tool.name}': {error_message}"
            )

            return {
                "success": False,
                "output": None,
                "execution_time_ms": execution_time_ms,
                "status": ExecutionStatus.FAILED,
                "error_message": error_message,
            }
        finally:
            # End the span
            if settings.OTEL_ENABLED and span:
                span.end()

    def _validate_input(self, tool: Tool, arguments: Dict[str, Any]) -> None:
        """Validate input arguments against the tool's input schema."""
        if not tool.input_schema:
            return  # No input validation required

        try:
            jsonschema.validate(
                instance=arguments,
                schema=tool.input_schema,
            )
        except jsonschema.ValidationError as e:
            raise ValueError(f"Input validation failed: {e.message}")

    def _validate_output(self, tool: Tool, output: Any) -> None:
        """Validate output against the tool's output schema."""
        try:
            jsonschema.validate(
                instance=output,
                schema=tool.output_schema,
            )
        except jsonschema.ValidationError as e:
            raise ValueError(f"Output validation failed: {e.message}")

    async def _execute_by_type(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """Execute tool based on its implementation type."""
        impl_type = tool.implementation_type
        # Handle both enum and string values
        if isinstance(impl_type, str):
            impl_type_str = impl_type
        else:
            impl_type_str = impl_type.value if hasattr(impl_type, 'value') else str(impl_type)

        if impl_type_str == ImplementationType.PYTHON_CODE.value or impl_type == ImplementationType.PYTHON_CODE:
            return await self._execute_python_code(tool, arguments)
        elif impl_type_str == ImplementationType.HTTP_ENDPOINT.value or impl_type == ImplementationType.HTTP_ENDPOINT:
            return await self._execute_http_endpoint(tool, arguments)
        elif impl_type_str == ImplementationType.COMMAND_LINE.value or impl_type == ImplementationType.COMMAND_LINE:
            return await self._execute_command_line(tool, arguments)
        elif impl_type_str == ImplementationType.WEBHOOK.value or impl_type == ImplementationType.WEBHOOK:
            return await self._execute_webhook(tool, arguments)
        elif impl_type_str == ImplementationType.MCP_SERVER.value or impl_type == ImplementationType.MCP_SERVER or impl_type_str == "mcp_server":
            return await self._execute_mcp_server(tool, arguments)
        else:
            raise NotImplementedError(
                f"Implementation type '{tool.implementation_type}' not supported"
            )

    async def _execute_python_code(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """
        Execute Python code implementation safely.

        Instead of using exec(), this method imports and calls registered functions
        by their module path. The implementation_code should be a fully qualified
        function path like 'app.tools.implementations.calculator.execute'.
        """
        if not tool.implementation_code:
            raise ValueError("Python code implementation is empty")

        implementation_code = tool.implementation_code.strip()

        # Validate the implementation code format (must be a module.function path)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$', implementation_code):
            raise ValueError(
                "Implementation code must be a valid module path "
                "(e.g., 'app.tools.implementations.calculator.execute')"
            )

        try:
            # Split into module path and function name
            module_path, function_name = implementation_code.rsplit('.', 1)

            # Import the module dynamically
            module = importlib.import_module(module_path)

            # Get the function from the module
            if not hasattr(module, function_name):
                raise ValueError(f"Function '{function_name}' not found in module '{module_path}'")

            func = getattr(module, function_name)

            if not callable(func):
                raise ValueError(f"'{implementation_code}' is not callable")

            # Execute the function with arguments
            result = func(arguments)
            return result

        except ImportError as e:
            raise RuntimeError(f"Failed to import module: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Python code execution failed: {str(e)}")

    async def _execute_http_endpoint(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """Execute HTTP endpoint implementation."""
        import httpx

        if not tool.implementation_code:
            raise ValueError("HTTP endpoint configuration is empty")

        try:
            # Parse endpoint configuration
            config = json.loads(tool.implementation_code)
            url = config.get("url")
            method = config.get("method", "POST").upper()
            headers = config.get("headers", {})

            if not url:
                raise ValueError("URL is required for HTTP endpoint")

            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=arguments if method in ["POST", "PUT", "PATCH"] else None,
                    params=arguments if method == "GET" else None,
                    headers=headers,
                    timeout=30.0
                )

                response.raise_for_status()

                # Try to parse JSON response, fall back to text
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"response": response.text}

        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid endpoint configuration: {str(e)}")

    async def _execute_command_line(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """
        Execute command line implementation safely.

        Uses shlex to safely parse command strings and avoids shell=True
        to prevent command injection attacks.
        """
        import subprocess

        if not tool.implementation_code:
            raise ValueError("Command configuration is empty")

        try:
            # Parse command configuration
            config = json.loads(tool.implementation_code)
            command_template = config.get("command")
            working_dir = config.get("working_dir")
            timeout = config.get("timeout", 30)
            allowed_commands = config.get("allowed_commands", [])

            if not command_template:
                raise ValueError("Command template is required")

            # Sanitize arguments to prevent injection
            sanitized_args = {}
            for key, value in arguments.items():
                if isinstance(value, str):
                    # Reject arguments containing shell metacharacters
                    if re.search(r'[;&|`$(){}[\]<>\\\'"]', value):
                        raise ValueError(
                            f"Argument '{key}' contains disallowed shell characters"
                        )
                    sanitized_args[key] = value
                elif isinstance(value, (int, float, bool)):
                    sanitized_args[key] = str(value)
                else:
                    raise ValueError(
                        f"Argument '{key}' must be a string, number, or boolean"
                    )

            # Format command with sanitized arguments
            try:
                command_str = command_template.format(**sanitized_args)
            except KeyError as e:
                raise ValueError(f"Missing required argument: {e}")

            # Parse command into list using shlex (safe parsing)
            try:
                command_parts = shlex.split(command_str)
            except ValueError as e:
                raise ValueError(f"Invalid command format: {e}")

            if not command_parts:
                raise ValueError("Command cannot be empty")

            # Validate the command against allowed commands whitelist
            executable = command_parts[0]
            if allowed_commands and executable not in allowed_commands:
                raise ValueError(
                    f"Command '{executable}' is not in the allowed commands list"
                )

            # Execute command WITHOUT shell=True for security
            result = subprocess.run(
                command_parts,
                shell=False,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=timeout
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Command failed with exit code {result.returncode}: {result.stderr}"
                )

            # Return structured result
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out after {timeout} seconds")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid command configuration JSON: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Command execution failed: {str(e)}")

    async def _execute_webhook(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """Execute webhook implementation."""
        import httpx

        if not tool.implementation_code:
            raise ValueError("Webhook URL is required")

        webhook_url = tool.implementation_code.strip()

        try:
            # Prepare webhook payload
            payload = {
                "tool_name": tool.name,
                "tool_id": tool.id,
                "arguments": arguments,
                "timestamp": time.time(),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=30.0
                )

                response.raise_for_status()

                # Try to parse JSON response
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": "webhook_delivered", "response": response.text}

        except httpx.HTTPError as e:
            raise RuntimeError(f"Webhook delivery failed: {str(e)}")

    async def _execute_mcp_server(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """
        Execute tool on an external MCP server.

        The implementation_code contains JSON config with:
        - type: "mcp_http" or "mcp_stdio"
        - server_url: URL for HTTP-based MCP servers
        - command: Command list for stdio-based MCP servers
        - tool_name: Original tool name on the MCP server
        """
        import asyncio
        import httpx

        if not tool.implementation_code:
            raise ValueError("MCP server configuration is empty")

        try:
            config = json.loads(tool.implementation_code)
            mcp_type = config.get("type", "mcp_http")
            original_tool_name = config.get("tool_name", tool.name.split(":")[-1])

            if mcp_type == "mcp_http":
                return await self._execute_mcp_http(config, original_tool_name, arguments)
            elif mcp_type == "mcp_stdio":
                return await self._execute_mcp_stdio(config, original_tool_name, arguments)
            else:
                raise ValueError(f"Unknown MCP type: {mcp_type}")

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid MCP server configuration: {str(e)}")

    async def _execute_mcp_http(
        self,
        config: Dict[str, Any],
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Execute tool on HTTP-based MCP server."""
        import httpx

        server_url = config.get("server_url", "").rstrip("/")
        if not server_url:
            raise ValueError("MCP server URL is required")

        # Try different endpoint patterns
        endpoints_to_try = [
            (f"{server_url}/tools/call", {"name": tool_name, "arguments": arguments}),
            (f"{server_url}/tools/call/{tool_name}", arguments),
            (f"{server_url}/mcp", {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 1
            }),
        ]

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            last_error = None

            for endpoint, payload in endpoints_to_try:
                try:
                    response = await client.post(endpoint, json=payload)

                    if response.status_code == 200:
                        data = response.json()

                        # Handle JSON-RPC response
                        if "result" in data:
                            result = data["result"]
                            # Extract content from MCP response format
                            if isinstance(result, list) and len(result) > 0:
                                first_item = result[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    return {"result": first_item["text"], "data": data}
                            return {"result": result, "data": data}

                        # Handle direct response
                        if "error" in data and data["error"]:
                            raise RuntimeError(f"MCP server error: {data['error']}")

                        return {"result": data.get("result", data), "data": data}

                except httpx.HTTPError as e:
                    last_error = e
                    self.logger.debug(f"MCP endpoint {endpoint} failed: {e}")
                    continue
                except Exception as e:
                    last_error = e
                    self.logger.debug(f"MCP endpoint {endpoint} error: {e}")
                    continue

            raise RuntimeError(f"All MCP endpoints failed. Last error: {last_error}")

    async def _execute_mcp_stdio(
        self,
        config: Dict[str, Any],
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Execute tool on stdio-based MCP server."""
        import asyncio

        command = config.get("command", [])
        if not command:
            raise ValueError("MCP server command is required")

        try:
            # Start the MCP server process
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Send tools/call request
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 1
            }) + "\n"

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=request.encode()),
                timeout=30.0
            )

            if stdout:
                for line in stdout.decode().strip().split('\n'):
                    try:
                        response = json.loads(line)
                        if "result" in response:
                            result = response["result"]
                            # Extract content from MCP response format
                            if isinstance(result, list) and len(result) > 0:
                                first_item = result[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    return {"result": first_item["text"], "data": response}
                            return {"result": result, "data": response}
                        if "error" in response:
                            raise RuntimeError(f"MCP error: {response['error']}")
                    except json.JSONDecodeError:
                        continue

            raise RuntimeError(f"No valid response from MCP server. stderr: {stderr.decode()}")

        except asyncio.TimeoutError:
            raise RuntimeError("MCP server request timed out")
        except Exception as e:
            raise RuntimeError(f"MCP stdio execution failed: {str(e)}")


# Global executor instance
executor = ToolExecutor()