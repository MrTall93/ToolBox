# Tool Registry MCP Server

A comprehensive Model Context Protocol (MCP) server for tool registration, discovery, and management with semantic search capabilities. Built with Python, FastAPI, and PostgreSQL + pgvector for production-ready deployment.

> **Note**: This project is currently under development and is part of a larger toolkit ecosystem.

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
- Support for natural language queries to find relevant tools
- Hybrid search combining keyword and semantic matching

### Production-Ready
- Complete Kubernetes deployment with production-grade Helm chart
- Horizontal Pod Autoscaling with custom metrics
- Comprehensive monitoring with Prometheus and Grafana dashboards
- Zero-trust network security with RBAC and Network Policies

### Enterprise Features
- PostgreSQL with pgvector extension for vector storage
- Multi-environment configurations (development, staging, production)
- Automated database migrations and rolling updates
- Comprehensive health checks and observability

### Container-Native
- UBI8-based Docker containers with security hardening
- Non-root execution with read-only filesystems
- Support for external embedding services (OpenAI, Cohere, custom)
- Optimized for Kubernetes and cloud-native environments

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │───▶│  Tool Registry   │───▶│  PostgreSQL +   │
│  (Any LLM App)  │    │     Server       │    │    pgvector     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Embedding Service │
                       │  (OpenAI/Custom)  │
                       └──────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 16 with pgvector extension
- Docker and Docker Compose (for local development)
- Kubernetes and Helm 3.0+ (for production deployment)
- LiteLLM deployment (optional, for unified LLM access)

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd Toolbox
./scripts/setup-git.sh
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

5. **Start the application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Test the MCP endpoints**
```bash
# Health check
curl http://localhost:8000/health

# List available tools
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" -d '{}'

# Search for tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{"query": "calculator for basic arithmetic"}'
```

### Docker Development

```bash
# Build the image
docker build -f Dockerfile.ubi8 -t tool-registry:latest .

# Run with environment variables
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://tool_registry:password@host.docker.internal:5432/tool_registry" \
  -e SECRET_KEY="your-secret-key" \
  -e EMBEDDING_ENDPOINT_URL="https://api.openai.com/v1/embeddings" \
  -e EMBEDDING_API_KEY="your-openai-api-key" \
  tool-registry:latest
```

## Development

### Project Structure

```
Toolbox/
├── app/                          # Main application code
│   ├── api/                      # FastAPI endpoints
│   │   ├── admin.py              # Admin API endpoints
│   │   ├── mcp.py                # MCP protocol endpoints
│   │   └── health.py             # Health check endpoints
│   ├── core/                     # Core application logic
│   ├── models/                   # Database models
│   ├── registry/                 # Tool registry and search
│   └── main.py                   # Application entry point
├── alembic/                      # Database migrations
├── helm/tool-registry/           # Production Helm chart
├── kubernetes/                   # Kubernetes manifests
├── scripts/                      # Deployment and setup scripts
├── Dockerfile.ubi8              # UBI8 container definition
└── docs/                         # Documentation
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

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

## Deployment

### Kubernetes with Helm

> [!NOTE]
> The production-ready Helm chart includes PostgreSQL with pgvector, monitoring, autoscaling, and security configurations.

1. **Development deployment**
```bash
helm install tool-registry-dev ./helm/tool-registry \
  --namespace tool-registry-dev \
  --create-namespace \
  --values helm/tool-registry/values-dev.yaml
```

2. **Production deployment**
```bash
helm install tool-registry-prod ./helm/tool-registry \
  --namespace tool-registry-prod \
  --create-namespace \
  --values helm/tool-registry/values-prod.yaml \
  --set secrets.embeddingApiKey="your-production-embedding-key" \
  --set secrets.secretKey="your-production-secret-key" \
  --set ingress.hosts[0].host="api.yourdomain.com"
```

3. **Access the application**
```bash
kubectl port-forward svc/tool-registry-prod-service 8000:80 -n tool-registry-prod
curl http://localhost:8000/health
```

### Automated Deployment

Use the provided deployment script for simplified deployments:

```bash
# Deploy to development
./helm/tool-registry/scripts/deploy.sh dev

# Deploy to production
./helm/tool-registry/scripts/deploy.sh prod tool-registry-prod
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
  "query": "calculator for basic math operations"
}
```

#### Execute Tool
```http
POST /mcp/call_tool
Content-Type: application/json

{
  "tool_name": "test-calculator",
  "arguments": {
    "operation": "add",
    "a": 5,
    "b": 3
  }
}
```

### Admin Endpoints

#### Register Tool
```http
POST /admin/tools
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "name": "calculator",
  "description": "A simple calculator tool",
  "category": "utility",
  "tags": ["math", "calculator"],
  "input_schema": {
    "type": "object",
    "properties": {
      "operation": {"type": "string", "enum": ["add", "subtract"]},
      "a": {"type": "number"},
      "b": {"type": "number"}
    },
    "required": ["operation", "a", "b"]
  }
}
```

### Health Endpoints

- `GET /health` - Application health status
- `GET /ready` - Readiness probe
- `GET /live` - Liveness probe
- `GET /metrics` - Prometheus metrics

### Interactive Documentation

Access the interactive API documentation at `http://localhost:8000/docs` when running locally.

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ | - |
| `SECRET_KEY` | Application secret key | ✅ | - |
| `EMBEDDING_ENDPOINT_URL` | Embedding service URL | ✅ | - |
| `EMBEDDING_API_KEY` | Embedding service API key | ✅ | - |
| `LOG_LEVEL` | Logging level | ❌ | `INFO` |
| `WORKERS` | Number of worker processes | ❌ | `4` |
| `EMBEDDING_DIMENSION` | Embedding vector dimension | ❌ | `768` |

### Database Configuration

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Configure pgvector
ALTER SYSTEM SET ivfflat.probes = 10;
```

### Embedding Service Support

The Tool Registry supports various embedding services:

- **OpenAI**: `https://api.openai.com/v1/embeddings`
- **Cohere**: `https://api.cohere.ai/v1/embed`
- **Custom**: Any OpenAI-compatible embedding service

### Production Settings

For production deployments, consider:

- **Database Connection Pool**: Configure `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`
- **Rate Limiting**: Enable with `ENABLE_RATE_LIMIT` and configure limits
- **CORS**: Restrict `CORS_ORIGINS` to your domain
- **Monitoring**: Enable Prometheus metrics and health checks
- **Security**: Use HTTPS and configure proper RBAC

## LiteLLM Integration

The Tool Registry MCP Server integrates seamlessly with LiteLLM for unified access to multiple LLM providers with tool capabilities.

### Quick Integration

Since you already have LiteLLM deployed, simply configure it to connect to your Tool Registry:

```yaml
# Add to your LiteLLM configuration
mcp_servers:
  - name: "tool-registry"
    connection:
      host: "localhost"  # Your Tool Registry host
      port: 8000        # Your Tool Registry port
      api_key: "${TOOL_REGISTRY_API_KEY}"
```

### Setup

1. **Configure your Tool Registry:**
```bash
# Set API key for LiteLLM access
export API_KEY="your-tool-registry-api-key"

# Add LiteLLM to CORS origins
export CORS_ORIGINS="http://your-litellm-host:4000,http://localhost:3000"
```

2. **Update LiteLLM configuration** with the MCP server connection details

3. **Test the integration:**
```bash
# Run the integration test
python scripts/test_litellm_integration.py

# Or use with LiteLLM directly
import litellm
response = litellm.completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Calculate 15 + 27"}],
    tools="auto"  # Auto-discover tools from MCP server
)
```

### Features

- **Semantic Tool Discovery**: Natural language tool search
- **Multiple LLM Providers**: Use tools with OpenAI, Anthropic, Gemini, etc.
- **Automatic Tool Selection**: LiteLLM picks the best tool for the task
- **Error Handling**: Robust retry logic and error recovery
- **Performance Monitoring**: Track tool usage and execution metrics

### Documentation

- **[Integration Guide](docs/litellm_integration_guide.md)** - Comprehensive setup and configuration
- **[Examples](examples/litellm_integration.py)** - Complete usage examples
- **[Test Script](scripts/test_litellm_integration.py)** - Validate your integration

---

Built for the MCP ecosystem