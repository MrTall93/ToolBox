# OpenTelemetry Integration

Toolbox now includes comprehensive OpenTelemetry instrumentation for observability and monitoring.

## Features

### Traces
- **Tool Execution**: Spans for each tool execution with timing, success/failure status
- **Search Operations**: Spans for semantic, keyword, and hybrid searches
- **Registry Operations**: Spans for tool registration, updates, and deletions
- **LiteLLM Sync**: Spans for synchronization operations with LiteLLM
- **HTTP Requests**: Automatic tracing of incoming HTTP requests
- **Database Queries**: Automatic tracing of database operations

### Metrics
- **Tool Execution Metrics**:
  - `tool_executions_total`: Total number of tool executions
  - `tool_execution_duration_seconds`: Duration of tool executions
- **Search Metrics**:
  - `tool_searches_total`: Total number of tool searches
  - `tool_search_duration_seconds`: Duration of search operations
- **Registry Metrics**:
  - `tool_registry_operations_total`: Registry CRUD operations
  - `tool_registry_tools_total`: Total number of tools in registry
  - `tool_registry_tools_by_category_total`: Tools count by category
  - `tool_registry_tools_by_server_total`: Tools count by MCP server
- **LiteLLM Sync Metrics**:
  - `litellm_sync_operations_total`: Sync operations count
  - `litellm_tools_synced_total`: Number of tools synced
  - `litellm_sync_duration_seconds`: Sync operation duration
- **Embedding Cache Metrics**:
  - `embedding_cache_hits_total`: Cache hit count
  - `embedding_cache_misses_total`: Cache miss count
  - `embedding_cache_size`: Current cache size

## Configuration

### Environment Variables

```bash
# Enable/Disable OpenTelemetry
OTEL_ENABLED=true

# OTLP Exporter Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://localhost:4317

# Service Information
OTEL_SERVICE_NAME=toolbox
OTEL_SERVICE_VERSION=1.0.0
OTEL_RESOURCE_ATTRIBUTES=service.name=toolbox,service.namespace=tool-registry

# Optional: Honeycomb Configuration
OTEL_HONEYCOMB_TEAM=your-honeycomb-api-key
```

### Using with Docker

The included `Dockerfile.ubi8` already includes OpenTelemetry support:

```bash
# Build with OpenTelemetry
docker build -f Dockerfile.ubi8 -t toolbox:otel .

# Run with OTel configuration
docker run -p 8000:8000 -p 8888:8888 \
  -e OTEL_ENABLED=true \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://your-otel-collector:4317 \
  toolbox:otel
```

### Using with Kubernetes

The Kubernetes manifests have been updated with OpenTelemetry support:

```bash
# Apply the updated configuration
kubectl apply -f k8s/toolbox/
```

## Accessing Metrics

### Prometheus Metrics
Available at `http://localhost:8888/metrics` (or `http://<node>:30888` on Kubernetes)

### Health Checks
- Application Health: `http://localhost:8000/health`
- OTel Collector Health: `http://localhost:13133/`

## View in Observability Backends

### Honeycomb
If you configure `OTEL_HONEYCOMB_TEAM`, traces and metrics will be automatically sent to Honeycomb.

### Jaeger
Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger-collector:4317` to send traces to Jaeger.

### Grafana Tempo
Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317` to send traces to Tempo.

### Generic OTLP Backend
Any OTLP-compatible backend can receive the telemetry data.

## Custom Metrics

You can add custom metrics using the provided functions:

```python
from app.observability import record_tool_execution, create_span

# Record a custom tool execution
record_tool_execution(
    tool_name="my_tool",
    tool_category="custom",
    execution_time=1.23,
    success=True,
    mcp_server="my-server"
)

# Create custom spans
with create_span("custom.operation") as span:
    span.set_attribute("custom.attr", "value")
    # Your code here
```

## Performance Considerations

- OpenTelemetry adds minimal overhead (~5-10%)
- The collector batches traces/metrics for efficient export
- Resource limits have been increased in Kubernetes to accommodate the collector
- Metrics are exported every 30 seconds by default

## Troubleshooting

1. **No traces/metrics appearing**:
   - Check `OTEL_ENABLED=true`
   - Verify OTLP endpoint is reachable
   - Check collector logs

2. **High resource usage**:
   - Adjust sampling rate in collector config
   - Increase export interval
   - Reduce batch size

3. **Connection errors**:
   - Ensure firewall allows OTLP ports (4317/4318)
   - Check network policies in Kubernetes