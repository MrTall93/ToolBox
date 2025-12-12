"""
Base tool interface for tool implementations.

This module defines the abstract base class that all tools should inherit from,
providing a consistent interface for tool execution and metadata.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import json
import time
from datetime import datetime

from pydantic import BaseModel, ValidationError


class ToolResult(BaseModel):
    """Standard result format for tool execution."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ToolInput(BaseModel):
    """Base model for tool input validation."""

    class Config:
        extra = "allow"  # Allow additional fields


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    All tool implementations should inherit from this class to ensure
    consistent behavior and interface across the tool registry.
    """

    def __init__(self):
        """Initialize the tool."""
        self._name: Optional[str] = None
        self._description: Optional[str] = None
        self._category: Optional[str] = None
        self._tags: List[str] = []
        self._version: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Get the tool category."""
        pass

    @property
    def tags(self) -> List[str]:
        """Get the tool tags."""
        return self._tags

    @property
    def version(self) -> str:
        """Get the tool version."""
        return self._version

    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for input validation.

        Returns:
            JSON schema dictionary
        """
        pass

    @abstractmethod
    def get_output_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for output validation.

        Returns:
            JSON schema dictionary
        """
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given arguments.

        Args:
            arguments: Dictionary of input arguments

        Returns:
            ToolResult with execution outcome
        """
        pass

    def validate_input(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input arguments against the input schema.

        Args:
            arguments: Input arguments to validate

        Returns:
            Validated arguments

        Raises:
            ValidationError: If arguments are invalid
        """
        schema = self.get_input_schema()
        # Create a dynamic Pydantic model for validation
        try:
            # Use Pydantic's create_model for dynamic validation
            from pydantic import create_model, Field
            fields = {}

            # Convert JSON schema properties to Pydantic fields
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            for field_name, field_spec in properties.items():
                field_type = self._json_type_to_python_type(field_spec.get("type", "string"))
                default = ... if field_name in required else Field(default=None)
                fields[field_name] = (field_type, default)

            # Create and validate the model
            DynamicModel = create_model(f"{self.name}_Input", **fields)
            validated = DynamicModel(**arguments)
            return validated.dict(exclude_unset=True)

        except Exception as e:
            raise ValidationError(f"Input validation failed: {str(e)}")

    def _json_type_to_python_type(self, json_type: str):
        """Convert JSON schema type to Python type."""
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return type_mapping.get(json_type, str)

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get tool metadata for registration.

        Returns:
            Dictionary with tool metadata
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "input_schema": self.get_input_schema(),
            "output_schema": self.get_output_schema(),
            "implementation_type": "python_class",
            "version": self.version,
        }

    async def safe_execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Safely execute the tool with error handling and timing.

        Args:
            arguments: Input arguments

        Returns:
            ToolResult with execution outcome and metrics
        """
        start_time = time.time()

        try:
            # Validate input
            validated_args = self.validate_input(arguments)

            # Execute the tool
            result = await self.execute(validated_args)

            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            result.execution_time_ms = execution_time_ms

            return result

        except ValidationError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=f"Input validation error: {str(e)}",
                execution_time_ms=execution_time_ms
            )
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    def __repr__(self) -> str:
        """String representation of the tool."""
        return f"<{self.__class__.__name__}(name='{self.name}', category='{self.category}')>"


class SimpleFunctionTool(BaseTool):
    """
    Simple wrapper for function-based tools.

    This allows existing function-based tools to work with the new interface
    without requiring extensive refactoring.
    """

    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        tags: List[str],
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
        execute_function,
        version: str = "1.0.0"
    ):
        """
        Initialize simple function tool.

        Args:
            name: Tool name
            description: Tool description
            category: Tool category
            tags: List of tags
            input_schema: JSON schema for input
            output_schema: JSON schema for output
            execute_function: Function to execute
            version: Tool version
        """
        super().__init__()
        self._name = name
        self._description = description
        self._category = category
        self._tags = tags
        self._version = version
        self._input_schema = input_schema
        self._output_schema = output_schema
        self._execute_function = execute_function

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> str:
        return self._category

    def get_input_schema(self) -> Dict[str, Any]:
        return self._input_schema

    def get_output_schema(self) -> Dict[str, Any]:
        return self._output_schema

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the wrapped function."""
        try:
            # Call the function
            result = self._execute_function(arguments)

            return ToolResult(
                success=True,
                data=result,
                metadata={"tool_type": "simple_function"}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool_type": "simple_function"}
            )