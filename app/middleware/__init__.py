"""Middleware package for the Tool Registry MCP Server."""

from .auth import require_auth, verify_api_key

__all__ = ["require_auth", "verify_api_key"]