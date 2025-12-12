"""Test tool interface and executor framework."""
import pytest
from unittest.mock import AsyncMock, patch
from typing import Dict, Any

from app.tools.base import BaseTool, ToolResult, SimpleFunctionTool
from app.tools.executor import ToolExecutor


class MockTool(BaseTool):
    """Mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def category(self) -> str:
        return "test"

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            }
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute mock tool."""
        input_text = arguments.get("input", "")
        return ToolResult(
            success=True,
            data={"result": f"processed: {input_text}"}
        )


class TestBaseTool:
    """Test BaseTool class."""

    def test_tool_properties(self, mock_tool):
        """Test tool properties."""
        assert mock_tool.name == "mock_tool"
        assert mock_tool.description == "A mock tool for testing"
        assert mock_tool.category == "test"
        assert isinstance(mock_tool.tags, list)
        assert mock_tool.version == "1.0.0"

    def test_tool_metadata(self, mock_tool):
        """Test tool metadata generation."""
        metadata = mock_tool.get_metadata()

        assert metadata["name"] == "mock_tool"
        assert metadata["description"] == "A mock tool for testing"
        assert metadata["category"] == "test"
        assert "input_schema" in metadata
        assert "output_schema" in metadata
        assert metadata["implementation_type"] == "python_class"

    def test_tool_validation(self, mock_tool):
        """Test input validation."""
        # Valid input
        args = {"input": "test"}
        validated = mock_tool.validate_input(args)
        assert validated["input"] == "test"

        # Invalid input (missing required field)
        with pytest.raises(Exception):  # Should raise ValidationError
            mock_tool.validate_input({})

    def test_tool_string_representation(self, mock_tool):
        """Test tool string representation."""
        repr_str = repr(mock_tool)
        assert "MockTool" in repr_str
        assert "mock_tool" in repr_str
        assert "test" in repr_str

    @pytest.mark.asyncio
    async def test_tool_safe_execute_success(self, mock_tool):
        """Test safe execution with success."""
        args = {"input": "test_input"}
        result = await mock_tool.safe_execute(args)

        assert result.success is True
        assert result.data is not None
        assert "processed: test_input" == result.data["result"]
        assert result.execution_time_ms is not None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_tool_safe_execute_validation_error(self, mock_tool):
        """Test safe execution with validation error."""
        args = {}  # Missing required 'input' field
        result = await mock_tool.safe_execute(args)

        assert result.success is False
        assert result.error is not None
        assert "validation error" in result.error.lower()
        assert result.execution_time_ms is not None
        assert result.data is None


class TestSimpleFunctionTool:
    """Test SimpleFunctionTool wrapper."""

    def test_simple_function_tool_creation(self):
        """Test creating simple function tool."""
        def mock_execute(args):
            return {"result": args.get("input", "").upper()}

        tool = SimpleFunctionTool(
            name="uppercase_tool",
            description="Converts text to uppercase",
            category="text",
            tags=["text", "uppercase"],
            input_schema={
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "string"}
                }
            },
            execute_function=mock_execute
        )

        assert tool.name == "uppercase_tool"
        assert tool.description == "Converts text to uppercase"
        assert tool.category == "text"

    @pytest.mark.asyncio
    async def test_simple_function_tool_execute(self):
        """Test simple function tool execution."""
        def mock_execute(args):
            return {"result": args.get("input", "").upper()}

        tool = SimpleFunctionTool(
            name="uppercase_tool",
            description="Converts text to uppercase",
            category="text",
            tags=["text", "uppercase"],
            input_schema={
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "string"}
                }
            },
            execute_function=mock_execute
        )

        result = await tool.execute({"input": "hello"})
        assert result.success is True
        assert result.data["result"] == "HELLO"

    @pytest.mark.asyncio
    async def test_simple_function_tool_execute_error(self):
        """Test simple function tool execution with error."""
        def mock_execute(args):
            raise ValueError("Test error")

        tool = SimpleFunctionTool(
            name="error_tool",
            description="Tool that errors",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            execute_function=mock_execute
        )

        result = await tool.execute({})
        assert result.success is False
        assert "Test error" in result.error


class TestToolExecutor:
    """Test ToolExecutor class."""

    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """Test executor initialization."""
        executor = ToolExecutor()
        assert isinstance(executor, ToolExecutor)

    @pytest.mark.asyncio
    async def test_execute_calculator_tool(self):
        """Test executing calculator tool."""
        executor = ToolExecutor()

        result = await executor.execute_tool(
            tool_name="calculator",
            arguments={
                "operation": "add",
                "a": 5,
                "b": 3
            }
        )

        assert result.success is True
        assert result.data["result"] == 8

    @pytest.mark.asyncio
    async def test_execute_string_uppercase_tool(self):
        """Test executing string uppercase tool."""
        executor = ToolExecutor()

        result = await executor.execute_tool(
            tool_name="string_uppercase",
            arguments={
                "text": "hello world"
            }
        )

        assert result.success is True
        assert result.data["result"] == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing non-existent tool."""
        executor = ToolExecutor()

        result = await executor.execute_tool(
            tool_name="nonexistent_tool",
            arguments={}
        )

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_list_loaded_tools(self):
        """Test listing loaded tools."""
        executor = ToolExecutor()

        # Initially empty
        tools = await executor.list_loaded_tools()
        assert isinstance(tools, list)

        # Execute a tool to load it
        await executor.execute_tool("calculator", {"operation": "add", "a": 1, "b": 1})

        # Should now have loaded tools
        tools = await executor.list_loaded_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test executor health check."""
        executor = ToolExecutor()
        health = await executor.health_check()

        assert health["status"] == "healthy"
        assert isinstance(health["loaded_tools_count"], int)
        assert isinstance(health["registered_classes_count"], int)
        assert isinstance(health["loaded_tools"], list)


class TestToolIntegration:
    """Integration tests for tool framework."""

    @pytest.mark.asyncio
    async def test_calculator_integration(self):
        """Test full calculator integration."""
        executor = ToolExecutor()

        test_cases = [
            {"operation": "add", "a": 5, "b": 3, "expected": 8},
            {"operation": "subtract", "a": 10, "b": 4, "expected": 6},
            {"operation": "multiply", "a": 7, "b": 6, "expected": 42},
            {"operation": "divide", "a": 15, "b": 3, "expected": 5},
        ]

        for case in test_cases:
            result = await executor.execute_tool(
                tool_name="calculator",
                arguments={
                    "operation": case["operation"],
                    "a": case["a"],
                    "b": case["b"]
                }
            )

            assert result.success is True
            assert result.data["result"] == case["expected"]

    @pytest.mark.asyncio
    async def test_string_tools_integration(self):
        """Test string tools integration."""
        executor = ToolExecutor()

        test_cases = [
            {
                "tool": "string_uppercase",
                "args": {"text": "hello"},
                "expected": "HELLO"
            },
            {
                "tool": "string_lowercase",
                "args": {"text": "WORLD"},
                "expected": "world"
            },
            {
                "tool": "string_reverse",
                "args": {"text": "python"},
                "expected": "nohtyp"
            },
            {
                "tool": "string_length",
                "args": {"text": "testing"},
                "expected": 7
            },
            {
                "tool": "word_count",
                "args": {"text": "hello world test"},
                "expected": 3
            },
        ]

        for case in test_cases:
            result = await executor.execute_tool(
                tool_name=case["tool"],
                arguments=case["args"]
            )

            assert result.success is True
            assert result.data["result"] == case["expected"]


@pytest.fixture
def mock_tool():
    """Create a mock tool for testing."""
    return MockTool()