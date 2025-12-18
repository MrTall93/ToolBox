"""Observability module with conditional OpenTelemetry support.

This module provides observability functions that work regardless of whether
OpenTelemetry is enabled. When disabled, noop implementations are used to
avoid conditional checks throughout the codebase.
"""

from typing import Any, Dict, Optional

from app.config import settings

if settings.OTEL_ENABLED:
    # Import real implementations when OTEL is enabled
    from app.observability.otel import (
        init_telemetry,
        get_meter,
        get_tracer,
        create_span as _create_span,
        record_tool_execution,
        record_search_metrics,
        record_embedding_cache_hit,
        record_embedding_cache_miss,
        update_embedding_cache_size,
        add_span_attributes,
        add_span_event,
        record_registry_operation,
        update_registry_tools_count,
        record_litellm_sync_operation,
    )

    # Re-export create_span with same signature
    create_span = _create_span
else:
    # Noop implementations when OTEL is disabled
    class NoopSpan:
        """Noop span that does nothing but provides the span interface."""

        def set_attribute(self, key: str, value: Any) -> None:
            """Noop: Set attribute."""
            pass

        def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
            """Noop: Add event."""
            pass

        def end(self) -> None:
            """Noop: End span."""
            pass

        def is_recording(self) -> bool:
            """Noop: Always returns False."""
            return False

        def __enter__(self) -> "NoopSpan":
            return self

        def __exit__(self, *args) -> None:
            pass

    def init_telemetry(
        service_name: str = "toolbox",
        service_version: str = "1.0.0",
        environment: Optional[str] = None,
    ) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def get_meter():
        """Noop: Returns None when OpenTelemetry is disabled."""
        return None

    def get_tracer():
        """Noop: Returns None when OpenTelemetry is disabled."""
        return None

    def create_span(
        name: str,
        kind: Any = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> NoopSpan:
        """Noop: Returns a NoopSpan when OpenTelemetry is disabled."""
        return NoopSpan()

    def record_tool_execution(
        tool_name: str,
        tool_category: str,
        execution_time: float,
        success: bool,
        error_type: Optional[str] = None,
        mcp_server: Optional[str] = None,
    ) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_search_metrics(
        query_type: str,
        results_count: int,
        search_time: float,
        query_length: int,
        threshold: Optional[float] = None
    ) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_embedding_cache_hit() -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_embedding_cache_miss() -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def update_embedding_cache_size(size: int) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def add_span_attributes(attributes: Dict[str, Any]) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_registry_operation(operation: str, success: bool = True) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def update_registry_tools_count(
        total: int,
        by_category: Optional[Dict[str, int]] = None,
        by_server: Optional[Dict[str, int]] = None
    ) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_litellm_sync_operation(
        server: str,
        tools_count: int,
        duration: float,
        success: bool = True
    ) -> None:
        """Noop: OpenTelemetry is disabled."""
        pass


__all__ = [
    "init_telemetry",
    "get_meter",
    "get_tracer",
    "create_span",
    "record_tool_execution",
    "record_search_metrics",
    "record_embedding_cache_hit",
    "record_embedding_cache_miss",
    "update_embedding_cache_size",
    "add_span_attributes",
    "add_span_event",
    "record_registry_operation",
    "update_registry_tools_count",
    "record_litellm_sync_operation",
]
