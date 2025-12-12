"""
Tool execution engine.

This module provides the executor for running tools with proper error handling,
validation, and instrumentation.
"""
import asyncio
import importlib
import time
from typing import Dict, Any, Optional, List, Type, Union
import traceback
from datetime import datetime, timezone

from app.tools.base import BaseTool, ToolResult, SimpleFunctionTool
from app.models.tool import Tool as ToolModel
from app.models.execution import ToolExecution, ExecutionStatus
from app.db.session import AsyncSession


class ToolExecutor:
    """
    Tool execution engine.

    Handles dynamic loading and execution of tools with proper error handling,
    validation, and execution tracking.
    """

    def __init__(self):
        """Initialize the tool executor."""
        self._loaded_tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}

    async def load_tool_from_model(self, tool_model: ToolModel) -> BaseTool:
        """
        Load a tool from a database model.

        Args:
            tool_model: Tool model from database

        Returns:
            Loaded tool instance

        Raises:
            ValueError: If tool cannot be loaded
        """
        tool_name = tool_model.name

        # Check if tool is already loaded
        if tool_name in self._loaded_tools:
            return self._loaded_tools[tool_name]

        # Create tool based on implementation type
        if tool_model.implementation_type == "python_function":
            tool = await self._load_function_tool(tool_model)
        elif tool_model.implementation_type == "python_class":
            tool = await self._load_class_tool(tool_model)
        else:
            raise ValueError(f"Unsupported implementation type: {tool_model.implementation_type}")

        # Cache the loaded tool
        self._loaded_tools[tool_name] = tool
        return tool

    async def _load_function_tool(self, tool_model: ToolModel) -> SimpleFunctionTool:
        """Load a function-based tool from model."""
        if not tool_model.implementation_code:
            raise ValueError(f"Tool {tool_model.name} has no implementation code")

        try:
            # Import the module and get the function
            module_path, function_name = tool_model.implementation_code.rsplit(".", 1)
            module = importlib.import_module(module_path)
            execute_function = getattr(module, function_name)

            # Create simple function tool wrapper
            tool = SimpleFunctionTool(
                name=tool_model.name,
                description=tool_model.description,
                category=tool_model.category,
                tags=tool_model.tags,
                input_schema=tool_model.input_schema,
                output_schema=tool_model.output_schema,
                execute_function=execute_function,
                version=tool_model.version
            )

            return tool

        except Exception as e:
            raise ValueError(f"Failed to load function tool {tool_model.name}: {str(e)}")

    async def _load_class_tool(self, tool_model: ToolModel) -> BaseTool:
        """Load a class-based tool from model."""
        if not tool_model.implementation_code:
            raise ValueError(f"Tool {tool_model.name} has no implementation code")

        try:
            # Import the module and get the class
            module_path, class_name = tool_model.implementation_code.rsplit(".", 1)
            module = importlib.import_module(module_path)
            tool_class = getattr(module, class_name)

            # Verify it's a BaseTool subclass
            if not issubclass(tool_class, BaseTool):
                raise ValueError(f"{class_name} is not a BaseTool subclass")

            # Instantiate the tool
            tool = tool_class()

            return tool

        except Exception as e:
            raise ValueError(f"Failed to load class tool {tool_model.name}: {str(e)}")

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        db_session: Optional[AsyncSession] = None,
        record_execution: bool = True
    ) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            arguments: Input arguments for the tool
            db_session: Database session for execution tracking
            record_execution: Whether to record execution in database

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool is not found or cannot be executed
        """
        start_time = time.time()
        execution_id = None

        try:
            # Load the tool
            # For now, we'll load from a known tool model
            # In a real implementation, you'd fetch from database
            tool = await self._get_tool_by_name(tool_name)

            # Record execution start
            if db_session and record_execution:
                execution = ToolExecution(
                    tool_name=tool_name,
                    tool_id=0,  # Would be set after loading tool model
                    input_data=arguments,
                    status=ExecutionStatus.RUNNING,
                    started_at=datetime.now(timezone.utc)
                )
                db_session.add(execution)
                await db_session.commit()
                await db_session.refresh(execution)
                execution_id = execution.id

            # Execute the tool
            result = await tool.safe_execute(arguments)

            # Update execution record
            if db_session and record_execution and execution_id:
                execution = await db_session.get(ToolExecution, execution_id)
                if execution:
                    execution.status = ExecutionStatus.SUCCESS if result.success else ExecutionStatus.FAILED
                    execution.output_data = result.data
                    execution.error_message = result.error
                    execution.execution_time_ms = result.execution_time_ms
                    execution.completed_at = datetime.now(timezone.utc)
                    await db_session.commit()

            return result

        except Exception as e:
            # Record error in execution log
            if db_session and record_execution and execution_id:
                execution = await db_session.get(ToolExecution, execution_id)
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = str(e)
                    execution.execution_time_ms = int((time.time() - start_time) * 1000)
                    execution.completed_at = datetime.now(timezone.utc)
                    await db_session.commit()

            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

    async def _get_tool_by_name(self, tool_name: str) -> BaseTool:
        """Get tool by name (placeholder implementation)."""
        # This is a placeholder - in a real implementation, you'd:
        # 1. Query the database for the tool model
        # 2. Load the appropriate tool implementation
        # 3. Return the tool instance

        # For now, return a mock tool if it's one of our known tools
        if tool_name == "calculator":
            from app.tools.implementations.calculator import TOOL_METADATA
            from app.tools.implementations.calculator import execute

            # Create a SimpleFunctionTool for calculator
            return SimpleFunctionTool(
                name=TOOL_METADATA["name"],
                description=TOOL_METADATA["description"],
                category=TOOL_METADATA["category"],
                tags=TOOL_METADATA["tags"],
                input_schema=TOOL_METADATA["input_schema"],
                output_schema=TOOL_METADATA["output_schema"],
                execute_function=execute,
                version=TOOL_METADATA["version"]
            )
        elif tool_name.startswith("string_"):
            from app.tools.implementations.string_tools import STRING_TOOLS
            for tool_meta in STRING_TOOLS:
                if tool_meta["name"] == tool_name:
                    # Get the function
                    module_path, func_name = tool_meta["implementation_code"].rsplit(".", 1)
                    module = importlib.import_module(module_path)
                    execute_function = getattr(module, func_name)

                    return SimpleFunctionTool(
                        name=tool_meta["name"],
                        description=tool_meta["description"],
                        category=tool_meta["category"],
                        tags=tool_meta["tags"],
                        input_schema=tool_meta["input_schema"],
                        output_schema=tool_meta["output_schema"],
                        execute_function=execute_function,
                        version=tool_meta["version"]
                    )

        raise ValueError(f"Tool '{tool_name}' not found")

    async def list_loaded_tools(self) -> List[str]:
        """
        Get list of currently loaded tools.

        Returns:
            List of tool names
        """
        return list(self._loaded_tools.keys())

    async def unload_tool(self, tool_name: str) -> bool:
        """
        Unload a tool from memory.

        Args:
            tool_name: Name of tool to unload

        Returns:
            True if tool was unloaded, False if not found
        """
        if tool_name in self._loaded_tools:
            del self._loaded_tools[tool_name]
            return True
        return False

    async def reload_tool(self, tool_name: str, tool_model: ToolModel) -> BaseTool:
        """
        Reload a tool with updated model.

        Args:
            tool_name: Name of tool to reload
            tool_model: Updated tool model

        Returns:
            Reloaded tool instance
        """
        # Unload existing tool
        await self.unload_tool(tool_name)

        # Load new version
        return await self.load_tool_from_model(tool_model)

    def register_tool_class(self, tool_class: Type[BaseTool]) -> None:
        """
        Register a tool class for dynamic loading.

        Args:
            tool_class: Tool class to register
        """
        if not issubclass(tool_class, BaseTool):
            raise ValueError(f"{tool_class.__name__} is not a BaseTool subclass")

        # Store the class for later instantiation
        self._tool_classes[tool_class.__name__] = tool_class

    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a loaded tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information dictionary or None if not found
        """
        if tool_name in self._loaded_tools:
            tool = self._loaded_tools[tool_name]
            return tool.get_metadata()
        return None

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the executor.

        Returns:
            Health check results
        """
        return {
            "status": "healthy",
            "loaded_tools_count": len(self._loaded_tools),
            "registered_classes_count": len(self._tool_classes),
            "loaded_tools": list(self._loaded_tools.keys())
        }


# Global executor instance
_executor = ToolExecutor()


async def get_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    return _executor


async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    db_session: Optional[AsyncSession] = None
) -> ToolResult:
    """
    Execute a tool using the global executor.

    Args:
        tool_name: Name of the tool to execute
        arguments: Input arguments
        db_session: Database session for tracking

    Returns:
        Tool execution result
    """
    executor = await get_executor()
    return await executor.execute_tool(tool_name, arguments, db_session)