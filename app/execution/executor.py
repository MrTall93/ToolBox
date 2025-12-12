"""Tool execution engine for running registered tools."""

import json
import logging
import time
from typing import Any, Dict, Optional
import traceback

import jsonschema
from pydantic import ValidationError

from app.schemas.mcp import ExecutionStatus
from app.models.tool import Tool, ImplementationType

logger = logging.getLogger(__name__)


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
        start_time = time.time()

        try:
            # Validate input arguments against tool schema
            self._validate_input(tool, arguments)

            # Execute based on implementation type
            result = await self._execute_by_type(tool, arguments)

            # Validate output against tool output schema (if present)
            if tool.output_schema:
                self._validate_output(tool, result)

            execution_time_ms = int((time.time() - start_time) * 1000)

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
            error_message = str(e)

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
        if tool.implementation_type == ImplementationType.PYTHON_CODE:
            return await self._execute_python_code(tool, arguments)
        elif tool.implementation_type == ImplementationType.HTTP_ENDPOINT:
            return await self._execute_http_endpoint(tool, arguments)
        elif tool.implementation_type == ImplementationType.COMMAND_LINE:
            return await self._execute_command_line(tool, arguments)
        elif tool.implementation_type == ImplementationType.WEBHOOK:
            return await self._execute_webhook(tool, arguments)
        else:
            raise NotImplementedError(
                f"Implementation type '{tool.implementation_type}' not supported"
            )

    async def _execute_python_code(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
        """Execute Python code implementation."""
        if not tool.implementation_code:
            raise ValueError("Python code implementation is empty")

        # Create a safe execution environment
        safe_globals = {
            "__builtins__": {
                # Only allow safe built-ins
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "float": float,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "pow": pow,
                "range": range,
                "reversed": reversed,
                "round": round,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "type": type,
                "zip": zip,
            },
            "math": __import__("math"),
            "json": json,
            "arguments": arguments,
            "result": None,
        }

        try:
            # Execute the code in a restricted environment
            exec(tool.implementation_code, safe_globals)
            return safe_globals.get("result")

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
        """Execute command line implementation."""
        import subprocess

        if not tool.implementation_code:
            raise ValueError("Command configuration is empty")

        try:
            # Parse command configuration
            config = json.loads(tool.implementation_code)
            command_template = config.get("command")
            working_dir = config.get("working_dir")
            timeout = config.get("timeout", 30)

            if not command_template:
                raise ValueError("Command template is required")

            # Format command with arguments (simple string formatting)
            try:
                command = command_template.format(**arguments)
            except KeyError as e:
                raise ValueError(f"Missing required argument: {e}")

            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed with exit code {result.returncode}: {result.stderr}")

            # Return structured result
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out after {timeout} seconds")
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


# Global executor instance
executor = ToolExecutor()