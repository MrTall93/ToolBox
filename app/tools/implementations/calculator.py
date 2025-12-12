"""
Calculator tool implementation.

Provides basic arithmetic operations: add, subtract, multiply, divide.
"""
from typing import Dict, Any


def execute(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute calculator operation.

    Args:
        arguments: Dict with 'operation', 'a', and 'b' keys

    Returns:
        Dict with 'result' key

    Raises:
        ValueError: If operation is invalid or division by zero
    """
    operation = arguments.get("operation")
    a = arguments.get("a")
    b = arguments.get("b")

    if operation not in ["add", "subtract", "multiply", "divide"]:
        raise ValueError(f"Invalid operation: {operation}")

    if a is None or b is None:
        raise ValueError("Both 'a' and 'b' parameters are required")

    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Division by zero")
        result = a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")

    return {
        "result": result,
        "operation": operation,
        "a": a,
        "b": b,
    }


# Tool metadata for registration
TOOL_METADATA = {
    "name": "calculator",
    "description": "Perform basic arithmetic operations: add, subtract, multiply, divide numbers",
    "category": "math",
    "tags": ["math", "arithmetic", "calculator", "numbers"],
    "input_schema": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "subtract", "multiply", "divide"],
                "description": "The arithmetic operation to perform",
            },
            "a": {
                "type": "number",
                "description": "First number",
            },
            "b": {
                "type": "number",
                "description": "Second number",
            },
        },
        "required": ["operation", "a", "b"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "result": {
                "type": "number",
                "description": "The result of the operation",
            },
            "operation": {"type": "string"},
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["result"],
    },
    "implementation_type": "python_function",
    "version": "1.0.0",
}
