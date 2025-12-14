"""Observability module for OpenTelemetry integration."""

from app.observability.otel import (
    init_telemetry,
    get_meter,
    get_tracer,
    create_span,
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