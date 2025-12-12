"""
String manipulation tools.

Provides common string operations: uppercase, lowercase, reverse, length, etc.
"""
from typing import Dict, Any


def execute_uppercase(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Convert string to uppercase."""
    text = arguments.get("text", "")
    return {"result": text.upper(), "original": text}


def execute_lowercase(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Convert string to lowercase."""
    text = arguments.get("text", "")
    return {"result": text.lower(), "original": text}


def execute_reverse(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse a string."""
    text = arguments.get("text", "")
    return {"result": text[::-1], "original": text}


def execute_length(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get string length."""
    text = arguments.get("text", "")
    return {"result": len(text), "original": text}


def execute_word_count(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Count words in a string."""
    text = arguments.get("text", "")
    words = text.split()
    return {
        "result": len(words),
        "original": text,
        "words": words,
    }


# Tool metadata for each string operation
STRING_TOOLS = [
    {
        "name": "string_uppercase",
        "description": "Convert a string to uppercase (ALL CAPS)",
        "category": "text",
        "tags": ["string", "text", "uppercase", "format"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to convert to uppercase",
                }
            },
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "original": {"type": "string"},
            },
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.string_tools.execute_uppercase",
        "version": "1.0.0",
    },
    {
        "name": "string_lowercase",
        "description": "Convert a string to lowercase (all lowercase letters)",
        "category": "text",
        "tags": ["string", "text", "lowercase", "format"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to convert to lowercase",
                }
            },
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "original": {"type": "string"},
            },
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.string_tools.execute_lowercase",
        "version": "1.0.0",
    },
    {
        "name": "string_reverse",
        "description": "Reverse the characters in a string (backwards text)",
        "category": "text",
        "tags": ["string", "text", "reverse"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to reverse",
                }
            },
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "original": {"type": "string"},
            },
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.string_tools.execute_reverse",
        "version": "1.0.0",
    },
    {
        "name": "string_length",
        "description": "Get the length of a string (count characters)",
        "category": "text",
        "tags": ["string", "text", "length", "count"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to measure",
                }
            },
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "integer"},
                "original": {"type": "string"},
            },
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.string_tools.execute_length",
        "version": "1.0.0",
    },
    {
        "name": "word_count",
        "description": "Count the number of words in a text string",
        "category": "text",
        "tags": ["string", "text", "words", "count", "analysis"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to count words in",
                }
            },
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "integer"},
                "original": {"type": "string"},
                "words": {"type": "array", "items": {"type": "string"}},
            },
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.string_tools.execute_word_count",
        "version": "1.0.0",
    },
]
