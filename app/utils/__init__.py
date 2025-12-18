"""Utility package for the Tool Registry MCP Server."""

from .validation import (
    ValidationError,
    validate_embedding_vector,
    validate_tool_name,
    validate_category,
    validate_tags,
    validate_json_schema,
    validate_implementation_code,
    validate_search_query,
    validate_pagination_params,
    validate_similarity_threshold,
    sanitize_string,
    validate_tool_arguments,
    create_safe_error_response,
    SecurityValidator,
)
from .http import (
    get_ssl_verify,
    create_http_client,
    DEFAULT_CUSTOM_CERT_PATH,
)

__all__ = [
    # Validation utilities
    "ValidationError",
    "validate_embedding_vector",
    "validate_tool_name",
    "validate_category",
    "validate_tags",
    "validate_json_schema",
    "validate_implementation_code",
    "validate_search_query",
    "validate_pagination_params",
    "validate_similarity_threshold",
    "sanitize_string",
    "validate_tool_arguments",
    "create_safe_error_response",
    "SecurityValidator",
    # HTTP utilities
    "get_ssl_verify",
    "create_http_client",
    "DEFAULT_CUSTOM_CERT_PATH",
]