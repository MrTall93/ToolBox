"""
OpenTelemetry configuration and initialization.

This module sets up comprehensive observability with OpenTelemetry including:
- Automatic instrumentation for FastAPI, HTTPx, SQLAlchemy
- Custom metrics and spans for tool operations
- Proper resource detection and labeling
- OTLP exporter for sending traces to backend
"""

import logging
import os
import time
from typing import Dict, Any, Optional

from opentelemetry import metrics, trace, baggage, context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind

from app.config import settings

logger = logging.getLogger(__name__)

# Global variables
_meter: Optional[metrics.Meter] = None
_tracer: Optional[trace.Tracer] = None
_tool_counter: Optional[metrics.Counter] = None
_tool_duration_histogram: Optional[metrics.Histogram] = None
_search_counter: Optional[metrics.Counter] = None
_search_duration_histogram: Optional[metrics.Histogram] = None
_embedding_cache_metrics: Optional[Dict[str, Any]] = None
_registry_metrics: Optional[Dict[str, Any]] = None
_sync_metrics: Optional[Dict[str, Any]] = None
_db_metrics: Optional[Dict[str, Any]] = None


def get_meter() -> metrics.Meter:
    """Get the OpenTelemetry meter."""
    global _meter
    if _meter is None:
        raise RuntimeError("OpenTelemetry not initialized. Call init_telemetry() first.")
    return _meter


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer."""
    global _tracer
    if _tracer is None:
        raise RuntimeError("OpenTelemetry not initialized. Call init_telemetry() first.")
    return _tracer


def init_telemetry(
    service_name: str = "toolbox",
    service_version: str = "1.0.0",
    environment: Optional[str] = None,
) -> None:
    """
    Initialize OpenTelemetry with proper configuration.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        environment: Environment (dev, staging, prod)
    """
    global _meter, _tracer, _tool_counter, _tool_duration_histogram
    global _search_counter, _search_duration_histogram, _embedding_cache_metrics
    global _registry_metrics, _sync_metrics, _db_metrics

    # Note: Propagators disabled for Python 3.9 compatibility

    # Create resource with service information
    resource = Resource.create(
        attributes={
            "service.name": service_name,
            "service.version": service_version,
            "service.namespace": "tool-registry",
            "deployment.environment": environment or os.getenv("ENVIRONMENT", "development"),
            "process.pid": os.getpid(),
        }
    )

    # Set up tracer provider
    trace_provider = TracerProvider(resource=resource)

    # Add OTLP exporter for traces
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers={
                "x-honeycomb-team": settings.OTEL_HONEYCOMB_TEAM
            } if settings.OTEL_HONEYCOMB_TEAM else None,
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace_provider.add_span_processor(span_processor)

    # Set trace provider as global
    trace.set_tracer_provider(trace_provider)
    _tracer = trace_provider.get_tracer(__name__)

    # Set up meter provider
    metric_reader = PeriodicExportingMetricReader(
        exporter=OTLPMetricExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT or settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers={
                "x-honeycomb-team": settings.OTEL_HONEYCOMB_TEAM
            } if settings.OTEL_HONEYCOMB_TEAM else None,
        ),
        export_interval_millis=30000,  # Export every 30 seconds
    )

    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    _meter = meter_provider.get_meter(__name__)

    # Initialize custom metrics
    _init_custom_metrics()

    # Instrument libraries
    _setup_instrumentation()

    logger.info(
        "OpenTelemetry initialized",
        extra={
            "service_name": service_name,
            "otel_endpoint": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            "environment": environment or os.getenv("ENVIRONMENT", "development")
        }
    )


def _init_custom_metrics() -> None:
    """Initialize custom metrics for tool operations."""
    global _tool_counter, _tool_duration_histogram, _search_counter, _search_duration_histogram, _embedding_cache_metrics
    global _registry_metrics, _sync_metrics, _db_metrics

    if not _meter:
        return

    # Tool execution metrics
    _tool_counter = _meter.create_counter(
        name="tool_executions_total",
        description="Total number of tool executions",
        unit="1"
    )

    _tool_duration_histogram = _meter.create_histogram(
        name="tool_execution_duration_seconds",
        description="Duration of tool executions",
        unit="s"
    )

    # Search metrics
    _search_counter = _meter.create_counter(
        name="tool_searches_total",
        description="Total number of tool searches",
        unit="1"
    )

    _search_duration_histogram = _meter.create_histogram(
        name="tool_search_duration_seconds",
        description="Duration of tool searches",
        unit="s"
    )

    # Embedding cache metrics
    _embedding_cache_metrics = {
        "hits": _meter.create_counter(
            name="embedding_cache_hits_total",
            description="Total number of embedding cache hits",
            unit="1"
        ),
        "misses": _meter.create_counter(
            name="embedding_cache_misses_total",
            description="Total number of embedding cache misses",
            unit="1"
        ),
        "size": _meter.create_up_down_counter(
            name="embedding_cache_size",
            description="Current size of embedding cache",
            unit="1"
        )
    }

    # Tool registry metrics
    _registry_metrics = {
        "operations": _meter.create_counter(
            name="tool_registry_operations_total",
            description="Total number of tool registry operations",
            unit="1"
        ),
        "tools_total": _meter.create_up_down_counter(
            name="tool_registry_tools_total",
            description="Total number of tools in registry",
            unit="1"
        ),
        "tools_by_category": _meter.create_up_down_counter(
            name="tool_registry_tools_by_category_total",
            description="Number of tools by category",
            unit="1"
        ),
        "tools_by_server": _meter.create_up_down_counter(
            name="tool_registry_tools_by_server_total",
            description="Number of tools by MCP server",
            unit="1"
        )
    }

    # LiteLLM sync metrics
    _sync_metrics = {
        "operations": _meter.create_counter(
            name="litellm_sync_operations_total",
            description="Total number of LiteLLM sync operations",
            unit="1"
        ),
        "tools_synced": _meter.create_counter(
            name="litellm_tools_synced_total",
            description="Number of tools synced with LiteLLM",
            unit="1"
        ),
        "sync_duration": _meter.create_histogram(
            name="litellm_sync_duration_seconds",
            description="Duration of LiteLLM sync operations",
            unit="s"
        )
    }

    # Database metrics
    _db_metrics = {
        "connection_pool_active": _meter.create_up_down_counter(
            name="db_connection_pool_active",
            description="Number of active database connections",
            unit="1"
        ),
        "connection_pool_idle": _meter.create_up_down_counter(
            name="db_connection_pool_idle",
            description="Number of idle database connections",
            unit="1"
        )
    }

    logger.info("Custom OpenTelemetry metrics initialized")


def _setup_instrumentation() -> None:
    """Set up automatic instrumentation for common libraries."""
    # FastAPI instrumentation
    FastAPIInstrumentor().instrument()

    # HTTP client instrumentation (for MCP server calls)
    HTTPXClientInstrumentor().instrument()

    # SQLAlchemy instrumentation
    SQLAlchemyInstrumentor().instrument()

    # AsyncPG instrumentation
    AsyncPGInstrumentor().instrument()

    logger.info("Automatic instrumentation configured")


def create_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None
) -> trace.Span:
    """
    Create a new span with common attributes.

    Args:
        name: Name of the span
        kind: Kind of span (client, server, internal, etc.)
        attributes: Additional attributes to add to the span

    Returns:
        The created span
    """
    tracer = get_tracer()

    span_attrs = {
        "service.name": "toolbox",
        "service.namespace": "tool-registry",
    }
    if attributes:
        span_attrs.update(attributes)

    return tracer.start_span(name, kind=kind, attributes=span_attrs)


def record_tool_execution(
    tool_name: str,
    tool_category: str,
    execution_time: float,
    success: bool,
    error_type: Optional[str] = None,
    mcp_server: Optional[str] = None,
) -> None:
    """
    Record metrics for a tool execution.

    Args:
        tool_name: Name of the tool executed
        tool_category: Category of the tool
        execution_time: Time taken to execute the tool in seconds
        success: Whether the execution was successful
        error_type: Type of error if execution failed
        mcp_server: MCP server name if applicable
    """
    if not _tool_counter or not _tool_duration_histogram:
        return

    # Record execution count
    _tool_counter.add(
        1,
        attributes={
            "tool_name": tool_name,
            "tool_category": tool_category,
            "success": str(success),
            "error_type": error_type or "none",
            "mcp_server": mcp_server or "none"
        }
    )

    # Record execution duration
    _tool_duration_histogram.record(
        execution_time,
        attributes={
            "tool_name": tool_name,
            "tool_category": tool_category,
            "success": str(success),
            "mcp_server": mcp_server or "none"
        }
    )


def record_search_metrics(
    query_type: str,
    results_count: int,
    search_time: float,
    query_length: int,
    threshold: Optional[float] = None
) -> None:
    """
    Record metrics for a tool search operation.

    Args:
        query_type: Type of search (semantic, keyword, hybrid)
        results_count: Number of results returned
        search_time: Time taken for search in seconds
        query_length: Length of the search query
        threshold: Similarity threshold used
    """
    if not _search_counter or not _search_duration_histogram:
        return

    # Record search count
    _search_counter.add(
        1,
        attributes={
            "query_type": query_type,
            "results_count_bucket": _bucket_results_count(results_count)
        }
    )

    # Record search duration
    _search_duration_histogram.record(
        search_time,
        attributes={
            "query_type": query_type,
            "query_length_bucket": _bucket_query_length(query_length)
        }
    )


def record_embedding_cache_hit() -> None:
    """Record an embedding cache hit."""
    if _embedding_cache_metrics and "hits" in _embedding_cache_metrics:
        _embedding_cache_metrics["hits"].add(1)


def record_embedding_cache_miss() -> None:
    """Record an embedding cache miss."""
    if _embedding_cache_metrics and "misses" in _embedding_cache_metrics:
        _embedding_cache_metrics["misses"].add(1)


def update_embedding_cache_size(size: int) -> None:
    """Update the current embedding cache size."""
    if _embedding_cache_metrics and "size" in _embedding_cache_metrics:
        _embedding_cache_metrics["size"].set(size)


def _bucket_results_count(count: int) -> str:
    """Bucket the results count for metrics."""
    if count == 0:
        return "0"
    elif count <= 5:
        return "1-5"
    elif count <= 10:
        return "6-10"
    elif count <= 20:
        return "11-20"
    else:
        return "20+"


def _bucket_query_length(length: int) -> str:
    """Bucket the query length for metrics."""
    if length <= 10:
        return "short"
    elif length <= 30:
        return "medium"
    else:
        return "long"


def add_span_attributes(attributes: Dict[str, Any]) -> None:
    """
    Add attributes to the current active span.

    Args:
        attributes: Dictionary of attributes to add
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, str(value))


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """
    Add an event to the current active span.

    Args:
        name: Name of the event
        attributes: Event attributes
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes or {})


# Tool Registry Metrics Functions
def record_registry_operation(operation: str, success: bool = True) -> None:
    """
    Record a tool registry operation.

    Args:
        operation: Type of operation (register, update, delete, sync)
        success: Whether the operation was successful
    """
    if _registry_metrics and "operations" in _registry_metrics:
        _registry_metrics["operations"].add(1, attributes={
            "operation": operation,
            "success": str(success)
        })


def update_registry_tools_count(total: int, by_category: Optional[Dict[str, int]] = None,
                               by_server: Optional[Dict[str, int]] = None) -> None:
    """
    Update the total number of tools in registry.

    Args:
        total: Total number of tools
        by_category: Tools count by category
        by_server: Tools count by MCP server
    """
    if not _registry_metrics:
        return

    _registry_metrics["tools_total"].set(total)

    if by_category:
        for category, count in by_category.items():
            _registry_metrics["tools_by_category"].set(count, attributes={"category": category})

    if by_server:
        for server, count in by_server.items():
            _registry_metrics["tools_by_server"].set(count, attributes={"server": server})


# LiteLLM Sync Metrics Functions
def record_litellm_sync_operation(server: str, tools_count: int, duration: float, success: bool = True) -> None:
    """
    Record a LiteLLM sync operation.

    Args:
        server: MCP server name
        tools_count: Number of tools synced
        duration: Sync duration in seconds
        success: Whether sync was successful
    """
    if not _sync_metrics:
        return

    _sync_metrics["operations"].add(1, attributes={
        "server": server,
        "success": str(success)
    })

    _sync_metrics["tools_synced"].add(tools_count, attributes={
        "server": server,
        "success": str(success)
    })

    _sync_metrics["sync_duration"].record(duration, attributes={
        "server": server,
        "success": str(success)
    })


# Database Metrics Functions
def update_db_connection_stats(active: int, idle: int) -> None:
    """
    Update database connection pool statistics.

    Args:
        active: Number of active connections
        idle: Number of idle connections
    """
    if not _db_metrics:
        return

    _db_metrics["connection_pool_active"].set(active)
    _db_metrics["connection_pool_idle"].set(idle)