# Toolbox - Tool Registry with MCP & LiteLLM Integration

A comprehensive Model Context Protocol (MCP) server for tool registration, discovery, and management with semantic search capabilities and seamless LiteLLM integration. Built with Python, FastAPI, and PostgreSQL + pgvector for production-ready deployment.

> **Note**: This project provides a centralized tool registry that syncs with external MCP servers and integrates with LiteLLM for unified tool access across multiple LLM providers.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Development](#development)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)

## Features

### Semantic Tool Discovery
- Advanced tool search using vector embeddings and similarity matching
- Support for natural language queries to find relevant tools (e.g., "cacluate addiction" finds calculator)
- Hybrid search combining keyword and semantic matching
- Fuzzy search with typo tolerance

### MCP Server Integration
- **FastMCP Server**: Built on the fastmcp framework for optimal performance
- **Automatic External MCP Server Discovery**: Connects to external MCP servers and syncs their tools
- **Bidirectional Sync**:
  - Syncs tools FROM external MCP servers
  - Syncs tools TO/FROM LiteLLM gateway
- **Namespacing**: Tools are namespaced by server (e.g., `server_name:tool_name`)
- **Hot Reloading**: Automatic re-sync when MCP servers change

### LiteLLM Integration
- **Two-way Integration**:
  - Tools can be discovered from LiteLLM's MCP registry
  - Tools can be registered with LiteLLM for use across multiple LLM providers
- **FastMCP Server**: High-performance MCP server built with fastmcp framework
- **JSON-RPC Support**: Full MCP protocol compliance with proper JSON-RPC messaging

### Production-Ready
- Complete Kubernetes deployment with production-grade manifests
- PostgreSQL with pgvector extension for vector storage
- All configuration externalized via environment variables
- Health checks, metrics, and observability support
- UBI8-based Docker containers with security hardening

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
│   MCP Client    │───▶│  LiteLLM Gateway │◀───┤  Toolbox        │◀───┤ MCP Servers  │
│  (Any LLM App)  │    │                 │    │(FastMCP Registry)│    │  (External)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └──────────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────────┐
                                                   │  PostgreSQL +    │
                                                   │    pgvector     │
                                                   └─────────────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────────┐
                                                   │ Embedding Service│
                                                   │  (Local/OpenAI) │
                                                   └─────────────────┘
```

### Data Flow

1. **MCP Server Discovery**: Toolbox automatically discovers tools from external MCP servers
2. **Tool Registration**: Tools are registered with vector embeddings for semantic search
3. **LiteLLM Sync**: Tools can be synced to/from LiteLLM for unified access
4. **Semantic Search**: Natural language queries find relevant tools using similarity search

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 16 with pgvector extension
- Docker and Docker Compose (for local development)
- Kubernetes (for production deployment)
- Local embedding service (e.g., LM Studio) or OpenAI API key

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd Toolbox
```

2. **Set up the environment**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your configuration
```

3. **Set up PostgreSQL with pgvector**
```bash
# Using Docker
docker run -d \
  --name postgres-pgvector \
  -e POSTGRES_DB=tool_registry \
  -e POSTGRES_USER=tool_registry \
  -e POSTGRES_PASSWORD=tool_registry_pass \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

4. **Run database migrations**
```bash
alembic upgrade head
```

5. **Start the embedding service** (if using local LM Studio)
```bash
# LM Studio should be running with:
# - Model: text-embedding-nomic-embed-text-v1.5
# - URL: http://127.0.0.1:1234/v1/embeddings
```

6. **Start the application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. **Test the MCP endpoints**
```bash
# Health check
curl http://localhost:8000/health

# List available tools
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" -d '{}'

# Semantic search with typos
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{"query": "cacluate addiction numbers", "limit": 5}'

# Execute a tool (example will vary based on available tools)
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "tool_name",
    "arguments": {}
  }'
```

### Docker Development

```bash
# Build the image
docker build -f Dockerfile.ubi8 -t toolbox:latest .

# Run with environment variables
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://tool_registry:password@host.docker.internal:5432/tool_registry" \
  -e SECRET_KEY="your-secret-key" \
  -e EMBEDDING_ENDPOINT_URL="http://host.docker.internal:1234/v1/embeddings" \
  -e EMBEDDING_API_KEY="dummy-key" \
  -e EMBEDDING_DIMENSION="768" \
  toolbox:latest
```

## Development

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
│   └── main.py                   # Application entry point
│   ├── mcp_server.py             # FastMCP server implementation
│   └── mcp_fastmcp_server.py     # Main FastMCP server module
├── mcp-servers/                  # External MCP server configurations
├── k8s/                          # Kubernetes manifests
│   └── toolbox/                  # Toolbox deployment
├── alembic/                      # Database migrations
└── scripts/                      # Deployment and setup scripts
```

### Running Tests

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=app tests/

# Run integration tests
pytest tests/integration/
```

## Deployment

### Kubernetes Deployment

The repository includes complete Kubernetes manifests for production deployment:

1. **Deploy Infrastructure**
```bash
# Deploy all components
kubectl apply -f k8s/
```

This deploys:
- PostgreSQL with pgvector
- Toolbox application (with FastMCP server)
- LiteLLM gateway

2. **Verify Deployment**
```bash
# Check all pods
kubectl get pods -n toolbox

# Check services
kubectl get services -n toolbox

# Port-forward to access services
kubectl port-forward service/toolbox 8000:8000 -n toolbox
kubectl port-forward service/litellm 4000:4000 -n toolbox
```

3. **Test Integration**
```bash
# Test MCP sync from external servers
curl -X POST http://127.0.0.1:8000/admin/mcp/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key"

# Test sync from LiteLLM
curl -X POST http://127.0.0.1:8000/admin/mcp/sync-from-liteLLM \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key"
```

### Manual MCP Server Registration

To add a new MCP server:

1. **Update Configuration**
```yaml
# In k8s/toolbox/configmap.yaml
MCP_SERVERS: '[
  {
    "name": "my-mcp-server",
    "url": "http://my-server:3000",
    "description": "My custom MCP server",
    "category": "custom",
    "tags": ["custom", "tools"]
  }
]'
```

2. **Restart Toolbox**
```bash
kubectl rollout restart deployment/toolbox -n toolbox
```

3. **Trigger Sync**
```bash
curl -X POST http://localhost:8000/admin/mcp/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key"
```

## API Documentation

### MCP Protocol Endpoints

#### List Tools
```http
POST /mcp/list_tools
Content-Type: application/json

{}
```

#### Find Tools (Semantic Search)
```http
POST /mcp/find_tool
Content-Type: application/json

{
  "query": "calculator for basic math operations",
  "limit": 10,
  "threshold": 0.7
}
```

#### Execute Tool
```http
POST /mcp/call_tool
Content-Type: application/json

{
  "tool_name": "example_tool",
  "arguments": {
    // Tool-specific arguments
  }
}
```

### Admin Endpoints

#### Sync from MCP Servers
```http
POST /admin/mcp/sync
Content-Type: application/json
Authorization: Bearer dev-api-key
```

#### Sync from LiteLLM
```http
POST /admin/mcp/sync-from-liteLLM
Content-Type: application/json
Authorization: Bearer dev-api-key
```

#### Sync Specific Server
```http
POST /admin/mcp/sync/server
Content-Type: application/json
Authorization: Bearer dev-api-key

{
  "server_name": "external_server_name"
}
```

### Health Endpoints

- `GET /health` - Application health status
- `GET /ready` - Readiness probe
- `GET /live` - Liveness probe

### Interactive Documentation

Access the interactive API documentation at `http://localhost:8000/docs` when running locally.

## Configuration

### Environment Variables

All configuration is externalized via environment variables:

#### Core Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ | - |
| `SECRET_KEY` | Application secret key | ✅ | - |
| `LOG_LEVEL` | Logging level | ❌ | `DEBUG` |
| `CORS_ORIGINS` | Allowed CORS origins | ❌ | `http://localhost:30800,http://localhost:30400` |

#### Embedding Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `EMBEDDING_ENDPOINT_URL` | Embedding service URL | ✅ | `http://host.docker.internal:1234/v1/embeddings` |
| `EMBEDDING_API_KEY` | Embedding service API key | ✅ | `dummy-key` |
| `EMBEDDING_DIMENSION` | Embedding vector dimension | ❌ | `768` |

#### MCP Server Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MCP_SERVERS` | JSON array of MCP servers to sync from | ❌ | `[]` |
| `MCP_AUTO_SYNC_ON_STARTUP` | Auto-sync on application start | ❌ | `true` |
| `MCP_REQUEST_TIMEOUT` | Request timeout for MCP servers | ❌ | `30.0` |

#### LiteLLM Integration Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LITELLM_SYNC_ENABLED` | Enable LiteLLM sync | ❌ | `true` |
| `LITELLM_MCP_SERVER_URL` | LiteLLM MCP server URL | ❌ | `http://litellm:4000` |
| `LITELLM_MCP_API_KEY` | LiteLLM MCP API key | ❌ | `sk-12345` |

### MCP Server Configuration Format

```json
[
  {
    "name": "server-name",
    "url": "http://server-host:port",
    "description": "Server description",
    "category": "category-name",
    "tags": ["tag1", "tag2"]
  }
]
```

### Database Setup

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Configure pgvector for optimal performance
ALTER SYSTEM SET ivfflat.probes = 10;
```

### Production Settings

For production deployments, ensure:
- Use real secret keys and API keys
- Configure proper database connection pooling
- Set appropriate resource limits
- Enable monitoring and alerting
- Use HTTPS for all communications

## FastMCP Server

The Toolbox application includes a FastMCP server implementation built with the fastmcp framework:

### Features
- **High Performance**: Optimized for speed and efficiency
- **MCP Protocol Compliance**: Full support for MCP standard
- **Tool Registry Integration**: Direct access to all registered tools
- **Semantic Search**: Natural language tool discovery
- **External MCP Server Sync**: Automatically discovers and syncs tools from external MCP servers

### Running the FastMCP Server

The FastMCP server can be run in multiple ways:

1. **As a stdio server** (for MCP clients like Claude Desktop)
2. **As an HTTP server** (for web-based integrations)
3. **Integrated with LiteLLM** (for unified AI tool access)

See [MCP_SERVER.md](MCP_SERVER.md) for detailed instructions on running and using the FastMCP server.

## Troubleshooting

### Common Issues

1. **Tools not syncing from external MCP servers**
   - Check if external MCP servers are accessible
   - Verify network connectivity between services
   - Check server logs for errors

2. **Semantic search not working**
   - Verify embedding service is running and accessible
   - Check EMBEDDING_ENDPOINT_URL and EMBEDDING_API_KEY
   - Ensure vectors are generated in the database

3. **LiteLLM integration issues**
   - Verify LiteLLM is running and accessible
   - Check LITELLM_MCP_API_KEY matches LiteLLM's master_key
   - Ensure MCP servers are properly registered in LiteLLM config

### Debug Commands

```bash
# Check Toolbox logs
kubectl logs -l app=toolbox -n toolbox

# Check FastMCP server logs
kubectl logs -l app=toolbox -n toolbox

# Test database connection
kubectl exec -it deployment/toolbox -n toolbox -- python -c "from app.db.session import engine; print(engine.url)"

# Verify tools in database
kubectl exec -it deployment/postgres -n toolbox -- psql -U tool_registry -d tool_registry -c "SELECT COUNT(*) FROM tools;"
```

---

Built for the MCP ecosystem with LiteLLM integration