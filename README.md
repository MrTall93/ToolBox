# Toolbox - Tool Registry with MCP & LiteLLM Integration

A comprehensive Model Context Protocol (MCP) server for tool registration, discovery, and management with semantic search capabilities and seamless LiteLLM integration. Built with Python 3.11+, FastAPI, FastMCP, and PostgreSQL + pgvector for production-ready deployment.

> **Note**: This project provides a centralized tool registry that syncs with external MCP servers and integrates with LiteLLM for unified tool access across multiple LLM providers.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Kubernetes Deployment](#kubernetes-deployment)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Code Quality](#code-quality)

## Features

### Semantic Tool Discovery
- Advanced tool search using vector embeddings and similarity matching
- Support for natural language queries to find relevant tools (e.g., "calculate addition" finds calculator)
- Hybrid search combining keyword and semantic matching
- Fuzzy search with typo tolerance

### MCP Server Integration
- **FastMCP Server**: Built on the fastmcp framework for optimal performance
- **MCP Resources**: Exposes registry data via MCP resources (`toolbox://categories`, `toolbox://stats`, `toolbox://tools/{category}`)
- **MCP Prompts**: Reusable prompt templates for tool discovery, execution, and workflow planning
- **Automatic External MCP Server Discovery**: Connects to external MCP servers and syncs their tools
- **Bidirectional Sync**:
  - Syncs tools FROM external MCP servers
  - Syncs tools TO/FROM LiteLLM gateway
- **Namespacing**: Tools are namespaced by server (e.g., `server_name:tool_name`)
- **Tool Execution**: Execute tools directly via REST API or MCP protocol

### LiteLLM Integration
- **Two-way Integration**:
  - Tools can be discovered from LiteLLM's MCP registry
  - Tools can be executed via LiteLLM's MCP REST API
- **Automatic Sync**: Syncs tools from LiteLLM MCP servers on startup
- **Tool Deletion**: Deactivates tools that no longer exist in LiteLLM

### Output Summarization
- **Token-Efficient Tool Execution**: `call_tool_summarized` automatically summarizes large tool outputs to reduce token usage by 80-90%
- **Configurable Thresholds**: Set `max_tokens` to control when summarization triggers (default: 2000 tokens)
- **Context-Aware Summaries**: Provide `summarization_context` hints to focus summaries on relevant information (e.g., "Focus on error messages")
- **Graceful Fallback**: Falls back to truncation if LLM summarization fails
- **Transparency**: Response includes `was_summarized` flag and token estimates

### Production-Ready
- Complete Kubernetes deployment with production-grade manifests
- PostgreSQL with pgvector extension for vector storage
- All configuration externalized via environment variables with validation
- Health checks (liveness, readiness with proper HTTP 503 responses), metrics, and OpenTelemetry observability support
- Modern Python 3.11+ with type hints (`X | None`, `list[str]`, `dict[str, Any]`)
- Comprehensive input validation and SQL injection protection
- Python 3.11 slim-based Docker containers

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
│   MCP Client    │───▶│  LiteLLM Gateway │◀──▶│  Toolbox        │◀───┤ MCP Servers  │
│  (Claude, etc.) │    │   (Port 4000)    │    │  (Port 8000)    │    │  (External)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────┘
                                                        │
        ┌───────────────────────────────────────────────┼───────────────────┐
        │                                               │                   │
        ▼                                               ▼                   ▼
┌─────────────────┐                            ┌─────────────────┐  ┌─────────────────┐
│ MCP HTTP Server │                            │  PostgreSQL +   │  │Embedding Service│
│   (Port 8080)   │                            │    pgvector     │  │ (LM Studio/API) │
└─────────────────┘                            └─────────────────┘  └─────────────────┘
```

### Components

| Component | Port | Description |
|-----------|------|-------------|
| Toolbox REST API | 8000 | FastAPI REST endpoints for tool management |
| Toolbox MCP Server | 8080 | FastMCP server for MCP Inspector/clients |
| LiteLLM | 4000 | MCP gateway with multiple MCP servers |
| PostgreSQL | 5432 | Database with pgvector for embeddings |

### Data Flow

1. **LiteLLM Sync**: Toolbox syncs tools from LiteLLM's MCP servers
2. **Tool Registration**: Tools are stored with vector embeddings for semantic search
3. **Tool Execution**: `call_tool` routes to appropriate executor (LiteLLM, MCP, Python, HTTP)
4. **Semantic Search**: Natural language queries find relevant tools using similarity search

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16 with pgvector extension
- Kubernetes (Docker Desktop, minikube, or cloud provider)
- Local embedding service (e.g., LM Studio) or OpenAI API key

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd Toolbox
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up PostgreSQL with pgvector**
```bash
docker run -d \
  --name postgres-pgvector \
  -e POSTGRES_DB=toolregistry \
  -e POSTGRES_USER=toolregistry \
  -e POSTGRES_PASSWORD=devpassword \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

4. **Configure environment**
```bash
export DATABASE_URL="postgresql+asyncpg://toolregistry:devpassword@localhost:5432/toolregistry"
export EMBEDDING_ENDPOINT_URL="http://localhost:1234/v1/embeddings"
export EMBEDDING_API_KEY="dummy-key"
export EMBEDDING_DIMENSION="768"
```

5. **Run migrations**
```bash
alembic upgrade head
```

6. **Start the application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. **Test the endpoints**
```bash
# Health check
curl http://localhost:8000/health

# List tools
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" -d '{}'

# Semantic search
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{"query": "temperature conversion", "limit": 5}'

# Execute a tool
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "converter-convert_temperature", "arguments": {"value": 100, "from_unit": "celsius", "to_unit": "fahrenheit"}}'
```

## Kubernetes Deployment

### Build and Deploy

1. **Build the Docker image**
```bash
docker build -f Dockerfile.otel -t toolbox:latest .
```

2. **Deploy to Kubernetes**
```bash
# Create namespace and deploy all components
kubectl apply -f k8s/namespace/
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/toolbox/
```

3. **Verify deployment**
```bash
kubectl get pods -n toolbox
kubectl get services -n toolbox
```

4. **Access services**
```bash
# REST API
kubectl port-forward svc/toolbox 8000:8000 -n toolbox

# MCP Server (for MCP Inspector)
kubectl port-forward svc/toolbox-mcp-http 8080:8080 -n toolbox
```

### Project Structure

```
Toolbox/
├── app/                          # Main application code
│   ├── api/                      # FastAPI endpoints
│   │   ├── admin.py              # Admin API endpoints
│   │   └── mcp.py                # MCP protocol endpoints
│   ├── models/                   # Database models
│   ├── registry/                 # Tool registry and search
│   ├── services/                 # MCP discovery service
│   ├── adapters/                 # LiteLLM adapter
│   ├── execution/                # Tool execution engine
│   ├── observability/            # OpenTelemetry instrumentation
│   ├── main.py                   # Application entry point
│   └── mcp_fastmcp_server.py     # FastMCP server module
├── k8s/                          # Kubernetes manifests
│   ├── namespace/                # Namespace definition
│   ├── postgres/                 # PostgreSQL deployment
│   └── toolbox/                  # Toolbox deployments
├── helm/                         # Helm chart
├── alembic/                      # Database migrations
├── scripts/                      # Runtime scripts
├── tests/                        # Test suite
├── examples/                     # Example scripts
├── Dockerfile.otel               # Production Dockerfile
└── otel-collector-config.yaml    # OpenTelemetry config
```

## API Documentation

### MCP Protocol Endpoints

#### List Tools
```http
POST /mcp/list_tools
Content-Type: application/json

{"limit": 50}
```

#### Find Tools (Semantic Search)
```http
POST /mcp/find_tool
Content-Type: application/json

{
  "query": "calculator for basic math",
  "limit": 10,
  "threshold": 0.7
}
```

#### Execute Tool
```http
POST /mcp/call_tool
Content-Type: application/json

{
  "tool_name": "converter-convert_temperature",
  "arguments": {
    "value": 100,
    "from_unit": "celsius",
    "to_unit": "fahrenheit"
  }
}
```

### Admin Endpoints

#### Sync from LiteLLM
```http
POST /admin/mcp/sync-from-liteLLM
Content-Type: application/json
X-API-Key: dev-api-key
```

#### Sync from External MCP Servers
```http
POST /admin/mcp/sync
Content-Type: application/json
X-API-Key: dev-api-key
```

### Health Endpoints

- `GET /health` - Application health status
- `GET /ready` - Readiness probe
- `GET /live` - Liveness probe

### Interactive Documentation

Access Swagger UI at `http://localhost:8000/docs` when running locally.

## Configuration

### Environment Variables

#### Core Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | - |
| `SECRET_KEY` | Application secret key | Yes | - |
| `LOG_LEVEL` | Logging level | No | `INFO` |
| `CORS_ORIGINS` | Allowed CORS origins | No | `*` |

#### Embedding Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `EMBEDDING_ENDPOINT_URL` | Embedding service URL | Yes | - |
| `EMBEDDING_API_KEY` | Embedding service API key | Yes | - |
| `EMBEDDING_DIMENSION` | Embedding vector dimension | No | `768` |

#### LiteLLM Integration
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LITELLM_SYNC_ENABLED` | Enable LiteLLM sync | No | `true` |
| `LITELLM_MCP_SERVER_URL` | LiteLLM server URL | No | - |
| `LITELLM_MCP_API_KEY` | LiteLLM API key | No | - |

#### MCP Server Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MCP_SERVERS` | JSON array of MCP servers | No | `[]` |
| `MCP_AUTO_SYNC_ON_STARTUP` | Auto-sync on startup | No | `true` |
| `MCP_REQUEST_TIMEOUT` | Request timeout (seconds) | No | `30.0` |

#### OpenTelemetry Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OTEL_ENABLED` | Enable OpenTelemetry | No | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint | No | - |
| `OTEL_SERVICE_NAME` | Service name | No | `toolbox` |

## MCP Inspector

Connect MCP Inspector to the FastMCP server:

1. Start the MCP HTTP deployment:
```bash
kubectl apply -f k8s/toolbox/mcp-http-deployment.yaml
```

2. Port-forward:
```bash
kubectl port-forward svc/toolbox-mcp-http 8080:8080 -n toolbox
```

3. Connect MCP Inspector to: `http://localhost:8080/mcp`

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `find_tools` | Search for tools using natural language |
| `call_tool` | Execute a tool by name |
| `list_tools` | List all available tools |
| `get_tool_schema` | Get schema for a specific tool |

### Available MCP Resources

| Resource URI | Description |
|--------------|-------------|
| `toolbox://categories` | List all tool categories |
| `toolbox://stats` | Registry statistics (counts by category, implementation type) |
| `toolbox://tools/{category}` | List tools in a specific category |

### Available MCP Prompts

| Prompt | Description |
|--------|-------------|
| `tool_discovery_prompt` | Generate a prompt for discovering tools for a task |
| `tool_execution_prompt` | Generate a prompt for executing a specific tool |
| `workflow_planning_prompt` | Generate a prompt for planning multi-tool workflows |

## Troubleshooting

### Common Issues

1. **Tools not syncing from LiteLLM**
   - Verify LiteLLM is running and accessible
   - Check `LITELLM_MCP_SERVER_URL` and `LITELLM_MCP_API_KEY`
   - Ensure LiteLLM has MCP servers configured

2. **Semantic search not working**
   - Verify embedding service is running
   - Check `EMBEDDING_ENDPOINT_URL` connectivity
   - Ensure vectors are generated in database

3. **Tool execution failing**
   - Check tool's `implementation_type` (LITELLM, MCP_SERVER, PYTHON_CODE, etc.)
   - Verify LiteLLM connectivity for LITELLM type tools
   - Check logs: `kubectl logs -l app=toolbox -n toolbox`

### Debug Commands

```bash
# Check Toolbox logs
kubectl logs deployment/toolbox -n toolbox

# Check MCP HTTP server logs
kubectl logs deployment/toolbox-mcp-http -n toolbox

# Verify database connection
kubectl exec -it deployment/toolbox -n toolbox -- python3 -c \
  "from app.db.session import engine; print('DB OK')"

# Count tools in database
kubectl exec -it deployment/postgres -n toolbox -- psql -U toolregistry \
  -d toolregistry -c "SELECT COUNT(*) FROM tools;"
```

## Code Quality

This project follows FastAPI, FastMCP, and Python best practices:

### FastAPI Best Practices
- **Lifespan Context Manager**: Uses `@asynccontextmanager` for startup/shutdown instead of deprecated `@app.on_event()`
- **Annotated Dependencies**: Uses `Annotated[Type, Depends()]` for cleaner dependency injection
- **Response Models**: All endpoints define response models including error cases (400, 404, 500)
- **Proper HTTP Status Codes**: Readiness probe returns HTTP 503 when not ready

### Python Best Practices
- **Modern Type Hints**: Uses Python 3.11+ syntax (`str | None`, `list[str]`, `dict[str, Any]`)
- **Pydantic v2**: Uses `model_config = ConfigDict()` instead of nested `Config` class
- **Module Exports**: All modules define `__all__` for explicit public API

### Security
- **Input Validation**: Comprehensive validation for all user inputs
- **SQL Injection Protection**: Parameterized queries and identifier validation
- **XSS Prevention**: Input sanitization for string values
- **Configuration Validation**: URL format, positive integers, reasonable ranges

### Observability
- **OpenTelemetry**: Full tracing and metrics with noop fallbacks when disabled
- **Structured Logging**: Exception logging with `logger.exception()` for stack traces
- **Health Checks**: Detailed health endpoints with component-level status

### Database
- **Connection Pooling**: Configurable pool size, overflow, timeout, and connection recycling
- **Async Operations**: Full async/await support with SQLAlchemy 2.0

For detailed improvement history, see [tickets.md](tickets.md).

---

Built for the MCP ecosystem with LiteLLM integration.
