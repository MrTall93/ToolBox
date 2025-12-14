"""Enhanced input validation and error handling utilities."""

import math
import re
from typing import Any, Dict, List

import jsonschema
from pydantic import ValidationError as PydanticValidationError

from app.config import settings


class ValidationError(Exception):
    """Custom validation error for better error handling."""
    pass


def validate_embedding_vector(embedding: List[float]) -> List[float]:
    """Validate embedding vector format and values."""
    if not isinstance(embedding, list):
        raise ValidationError("Embedding must be a list of floats")

    if len(embedding) != settings.EMBEDDING_DIMENSION:
        raise ValidationError(
            f"Embedding dimension {len(embedding)} doesn't match "
            f"configured dimension {settings.EMBEDDING_DIMENSION}"
        )

    # Validate each element is a valid number
    validated_embedding = []
    for i, value in enumerate(embedding):
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Embedding element at index {i} is not a number")

        if math.isnan(value) or math.isinf(value):
            raise ValidationError(f"Embedding element at index {i} is not finite")

        validated_embedding.append(float(value))

    return validated_embedding


def validate_tool_name(name: str) -> str:
    """Validate tool name format."""
    if not isinstance(name, str):
        raise ValidationError("Tool name must be a string")

    name = name.strip()

    if not name:
        raise ValidationError("Tool name cannot be empty")

    if len(name) > 255:
        raise ValidationError("Tool name cannot exceed 255 characters")

    # Allow alphanumeric characters, spaces, hyphens, underscores, and colons
    # (colons are used for namespaced tools like "mcp_server:tool_name")
    if not re.match(r'^[a-zA-Z0-9\s\-_:]+$', name):
        raise ValidationError(
            "Tool name can only contain letters, numbers, spaces, hyphens, underscores, and colons"
        )

    return name


def validate_category(category: str) -> str:
    """Validate tool category format."""
    if not isinstance(category, str):
        raise ValidationError("Category must be a string")

    category = category.strip().lower()

    if not category:
        raise ValidationError("Category cannot be empty")

    if len(category) > 100:
        raise ValidationError("Category cannot exceed 100 characters")

    # Only allow alphanumeric characters, spaces, and hyphens
    if not re.match(r'^[a-z0-9\s\-]+$', category):
        raise ValidationError(
            "Category can only contain lowercase letters, numbers, spaces, and hyphens"
        )

    return category


def validate_tags(tags: List[str]) -> List[str]:
    """Validate tool tags format."""
    if not isinstance(tags, list):
        raise ValidationError("Tags must be a list")

    validated_tags = []
    for i, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise ValidationError(f"Tag at index {i} must be a string")

        tag = tag.strip().lower()

        if not tag:
            continue  # Skip empty tags

        if len(tag) > 50:
            raise ValidationError(f"Tag '{tag}' exceeds 50 characters")

        # Only allow alphanumeric characters and hyphens
        if not re.match(r'^[a-z0-9\-]+$', tag):
            raise ValidationError(
                f"Tag '{tag}' can only contain lowercase letters, numbers, and hyphens"
            )

        validated_tags.append(tag)

    # Remove duplicates and limit to reasonable number
    return list(dict.fromkeys(validated_tags))[:20]  # Max 20 unique tags


def validate_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JSON schema format."""
    if not isinstance(schema, dict):
        raise ValidationError("Schema must be a dictionary")

    if not schema:
        raise ValidationError("Schema cannot be empty")

    # Basic schema validation
    required_fields = ["type"]
    for field in required_fields:
        if field not in schema:
            raise ValidationError(f"Schema missing required field: {field}")

    if schema["type"] not in ["object", "array", "string", "number", "boolean", "null"]:
        raise ValidationError(f"Invalid schema type: {schema['type']}")

    try:
        # Validate that it's a valid JSON Schema
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        raise ValidationError(f"Invalid JSON Schema: {e.message}")

    return schema


def validate_implementation_code(code: str, implementation_type: str) -> str:
    """Validate implementation code based on type."""
    if not isinstance(code, str):
        raise ValidationError("Implementation code must be a string")

    code = code.strip()

    if not code and implementation_type not in ["webhook", "http_endpoint"]:
        raise ValidationError("Implementation code cannot be empty")

    # Size limits for different implementation types
    size_limits = {
        "python_code": 100000,  # 100KB
        "command_line": 1000,   # 1KB
        "http_endpoint": 2000,  # 2KB JSON config
        "webhook": 2000,        # 2KB URL
    }

    max_size = size_limits.get(implementation_type, 10000)
    if len(code) > max_size:
        raise ValidationError(
            f"Implementation code exceeds {max_size} characters for type '{implementation_type}'"
        )

    # Additional validation based on type
    if implementation_type == "webhook":
        # Basic URL validation
        if not code.startswith(("http://", "https://")):
            raise ValidationError("Webhook URL must start with http:// or https://")

    elif implementation_type == "python_code":
        # Basic Python syntax validation (avoid exec on user input)
        if any(keyword in code.lower() for keyword in ["import os", "import sys", "subprocess", "eval(", "exec("]):
            raise ValidationError("Python code contains potentially unsafe operations")

    return code


def validate_search_query(query: str) -> str:
    """Validate search query format."""
    if not isinstance(query, str):
        raise ValidationError("Search query must be a string")

    query = query.strip()

    if not query:
        raise ValidationError("Search query cannot be empty")

    if len(query) > 1000:
        raise ValidationError("Search query cannot exceed 1000 characters")

    # Remove excessive whitespace
    query = re.sub(r'\s+', ' ', query)

    return query


def validate_pagination_params(limit: int, offset: int = 0) -> tuple[int, int]:
    """Validate pagination parameters."""
    if not isinstance(limit, int) or limit <= 0:
        raise ValidationError("Limit must be a positive integer")

    if not isinstance(offset, int) or offset < 0:
        raise ValidationError("Offset must be a non-negative integer")

    # Apply reasonable limits
    limit = min(max(limit, 1), settings.DEFAULT_SEARCH_LIMIT * 10)  # Max 10x default
    offset = max(offset, 0)

    return limit, offset


def validate_similarity_threshold(threshold: float) -> float:
    """Validate similarity threshold."""
    if not isinstance(threshold, (int, float)):
        raise ValidationError("Similarity threshold must be a number")

    threshold = float(threshold)

    if not 0.0 <= threshold <= 1.0:
        raise ValidationError("Similarity threshold must be between 0.0 and 1.0")

    # Round to reasonable precision
    return round(threshold, 4)


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input by removing potentially harmful content."""
    if not isinstance(value, str):
        raise ValidationError("Value must be a string")

    # Remove null bytes and control characters except newlines and tabs
    value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]

    return value.strip()


def validate_tool_arguments(arguments: Dict[str, Any], input_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate tool arguments against input schema."""
    if not isinstance(arguments, dict):
        raise ValidationError("Arguments must be a dictionary")

    if not isinstance(input_schema, dict):
        raise ValidationError("Input schema must be a dictionary")

    try:
        # Use jsonschema for validation
        jsonschema.validate(
            instance=arguments,
            schema=input_schema,
            format_checker=jsonschema.Draft7Validator.FORMAT_CHECKER
        )
    except jsonschema.ValidationError as e:
        raise ValidationError(f"Argument validation failed: {e.message}")

    return arguments


def create_safe_error_response(error: Exception, include_details: bool = False) -> Dict[str, Any]:
    """Create a safe error response that doesn't expose sensitive information."""
    error_type = type(error).__name__

    # Log the full error for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(f"Error occurred: {error_type}: {error}")

    # Base error response
    response = {
        "error": error_type,
        "message": "An internal error occurred"
    }

    # Include specific details in development or for validation errors
    if include_details or isinstance(error, ValidationError):
        response["message"] = str(error)
        if isinstance(error, ValidationError):
            response["error_type"] = "validation_error"

    return response


class SecurityValidator:
    """Security-focused validation for user inputs."""

    @staticmethod
    def validate_no_sql_injection(value: str) -> str:
        """Check for potential SQL injection patterns."""
        if not isinstance(value, str):
            return value

        # Common SQL injection patterns
        dangerous_patterns = [
            r"'|\"|`",
            r"union\s+select",
            r"drop\s+table",
            r"insert\s+into",
            r"delete\s+from",
            r"update\s+set",
            r"exec\s*\(",
            r"script\s*>",
            r"<\s*script",
        ]

        value_lower = value.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, value_lower):
                raise ValidationError("Input contains potentially dangerous content")

        return value

    @staticmethod
    def validate_no_xss(value: str) -> str:
        """Check for potential XSS patterns."""
        if not isinstance(value, str):
            return value

        # Common XSS patterns
        dangerous_patterns = [
            r"<\s*script[^>]*>",
            r"javascript:",
            r"on\w+\s*=",
            r"<\s*iframe[^>]*>",
            r"<\s*object[^>]*>",
            r"<\s*embed[^>]*>",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, value.lower(), re.IGNORECASE):
                raise ValidationError("Input contains potentially dangerous content")

        return value

    @staticmethod
    def sanitize_input(value: str) -> str:
        """Apply comprehensive sanitization to user input."""
        if not isinstance(value, str):
            return value

        # Apply all security validations
        value = SecurityValidator.validate_no_sql_injection(value)
        value = SecurityValidator.validate_no_xss(value)

        return sanitize_string(value)