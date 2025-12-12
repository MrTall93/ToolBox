## Tool Registry MCP Server - Usage Guide

Complete guide for using the Tool Registry MCP Server.

## Table of Contents

- [Quick Start](#quick-start)
- [MCP Protocol Endpoints](#mcp-protocol-endpoints)
- [Admin API](#admin-api)
- [Python SDK Examples](#python-sdk-examples)
- [REST API Examples](#rest-api-examples)
- [Tool Development](#tool-development)

---

## Quick Start

### 1. Start the Server

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Or manually
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### 2. Access the API

- **API Base URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 3. Register Example Tools

```bash
python examples/register_tools.py
```

This registers:
- Calculator (add, subtract, multiply, divide)
- String tools (uppercase, lowercase, reverse, length, word_count)

### 4. Search for Tools

```bash
# Python script
python examples/search_tools.py "calculate numbers"

# Or via API
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{"query": "calculate numbers", "limit": 5}'
```

---

## MCP Protocol Endpoints

The three core MCP endpoints for tool discovery and execution.

### POST /mcp/list_tools

List all available tools with optional filtering.

**Request:**
```json
{
  "category": "math",
  "active_only": true,
  "limit": 10,
  "offset": 0
}
```

**Response:**
```json
{
  "tools": [
    {
      "id": 1,
      "name": "calculator",
      "description": "Perform basic arithmetic operations",
      "category": "math",
      "tags": ["math", "arithmetic"],
      "input_schema": {...},
      "version": "1.0.0",
      "is_active": true
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

**Python Example:**
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/mcp/list_tools",
        json={"limit": 10, "active_only": true}
    )
    tools = response.json()
```

---

### POST /mcp/find_tool

Semantic search for tools using natural language queries.

**Request:**
```json
{
  "query": "tool to add numbers together",
  "limit": 5,
  "threshold": 0.7,
  "category": null,
  "use_hybrid": true
}
```

**Response:**
```json
{
  "results": [
    {
      "tool": {
        "id": 1,
        "name": "calculator",
        "description": "Perform basic arithmetic operations",
        "category": "math",
        "tags": ["math", "arithmetic", "calculator"],
        "input_schema": {...}
      },
      "score": 0.8934
    }
  ],
  "query": "tool to add numbers together",
  "count": 1
}
```

**Key Parameters:**
- `query`: Natural language search query
- `limit`: Maximum number of results (default: 5)
- `threshold`: Minimum similarity score 0-1 (default: 0.7)
- `use_hybrid`: Combine vector + text search (default: true)
- `category`: Filter by category (optional)

**Python Example:**
```python
response = await client.post(
    "http://localhost:8000/mcp/find_tool",
    json={
        "query": "calculate numbers",
        "limit": 3,
        "threshold": 0.6,
        "use_hybrid": True
    }
)
results = response.json()["results"]
for item in results:
    print(f"{item['tool']['name']}: {item['score']:.3f}")
```

---

### POST /mcp/call_tool

Execute a tool by name with arguments.

**Request:**
```json
{
  "tool_name": "calculator",
  "arguments": {
    "operation": "add",
    "a": 5,
    "b": 3
  },
  "metadata": {
    "user_id": "user123"
  }
}
```

**Response:**
```json
{
  "success": true,
  "tool_name": "calculator",
  "execution_id": 42,
  "output": {
    "message": "Tool execution not yet implemented"
  },
  "execution_time_ms": 12
}
```

**Note**: Actual tool execution is tracked but not yet implemented. Phase 6 will add actual execution logic.

---

## Admin API

Endpoints for managing tools (registration, updates, deletion).

### POST /admin/tools

Register a new tool with automatic embedding generation.

**Request:**
```json
{
  "name": "temperature_converter",
  "description": "Convert temperatures between Celsius, Fahrenheit, and Kelvin",
  "category": "conversion",
  "tags": ["temperature", "conversion", "celsius", "fahrenheit"],
  "input_schema": {
    "type": "object",
    "properties": {
      "value": {"type": "number"},
      "from_unit": {"type": "string", "enum": ["C", "F", "K"]},
      "to_unit": {"type": "string", "enum": ["C", "F", "K"]}
    },
    "required": ["value", "from_unit", "to_unit"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "result": {"type": "number"},
      "unit": {"type": "string"}
    }
  },
  "implementation_type": "python_function",
  "version": "1.0.0",
  "auto_embed": true
}
```

**Response:**
```json
{
  "success": true,
  "tool": {...},
  "message": "Tool 'temperature_converter' registered successfully"
}
```

---

### GET /admin/tools/{id}

Get detailed information about a specific tool.

```bash
curl http://localhost:8000/admin/tools/1
```

---

### PUT /admin/tools/{id}

Update tool properties. Automatically regenerates embeddings if content changes.

**Request:**
```json
{
  "description": "Updated description",
  "tags": ["new", "tags"],
  "is_active": true
}
```

Only provided fields are updated.

---

### DELETE /admin/tools/{id}

Permanently delete a tool.

```bash
curl -X DELETE http://localhost:8000/admin/tools/1
```

---

### POST /admin/tools/{id}/deactivate

Soft delete - mark tool as inactive without removing it.

```bash
curl -X POST http://localhost:8000/admin/tools/1/deactivate
```

---

### POST /admin/tools/{id}/activate

Reactivate a previously deactivated tool.

```bash
curl -X POST http://localhost:8000/admin/tools/1/activate
```

---

### GET /admin/tools/{id}/stats

Get execution statistics for a tool.

**Response:**
```json
{
  "tool_id": 1,
  "tool_name": "calculator",
  "total_executions": 142,
  "successful_executions": 138,
  "failed_executions": 4,
  "success_rate": 0.9718,
  "avg_execution_time_ms": 23.5
}
```

---

### POST /admin/tools/{id}/reindex

Manually regenerate the embedding for a tool.

```bash
curl -X POST http://localhost:8000/admin/tools/1/reindex
```

---

## Python SDK Examples

### Direct Database Access

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.registry import ToolRegistry

async def main():
    # Create engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        registry = ToolRegistry(session=session)

        # Register a tool
        tool = await registry.register_tool(
            name="my_tool",
            description="My custom tool",
            category="custom",
            input_schema={"type": "object", "properties": {}},
            tags=["custom"],
            auto_embed=True
        )

        # Search for tools
        results = await registry.find_tool(
            query="my custom tool",
            limit=5,
            use_hybrid=True
        )

        for tool, score in results:
            print(f"{tool.name}: {score:.3f}")

    await engine.dispose()

asyncio.run(main())
```

---

## REST API Examples

### Using curl

See [examples/mcp_api_examples.sh](examples/mcp_api_examples.sh) for complete examples.

```bash
# Health check
curl http://localhost:8000/health

# List tools
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'

# Find tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{"query": "calculate", "limit": 5}'

# Call a tool
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculator",
    "arguments": {"operation": "add", "a": 5, "b": 3}
  }'
```

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8000"

# Find tools
response = requests.post(
    f"{BASE_URL}/mcp/find_tool",
    json={
        "query": "manipulate text",
        "limit": 3,
        "threshold": 0.6
    }
)
results = response.json()

# Register tool
response = requests.post(
    f"{BASE_URL}/admin/tools",
    json={
        "name": "my_tool",
        "description": "Description",
        "category": "utility",
        "input_schema": {"type": "object"},
        "tags": ["example"]
    }
)
tool = response.json()["tool"]
```

---

## Tool Development

### Creating a New Tool

1. **Create the implementation** in `app/tools/implementations/`:

```python
# app/tools/implementations/my_tool.py

def execute(arguments: dict) -> dict:
    """Execute the tool."""
    result = arguments.get("input") * 2
    return {"result": result}

TOOL_METADATA = {
    "name": "my_tool",
    "description": "Doubles the input value",
    "category": "math",
    "tags": ["math", "multiply"],
    "input_schema": {
        "type": "object",
        "properties": {
            "input": {"type": "number"}
        },
        "required": ["input"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "result": {"type": "number"}
        }
    },
    "implementation_type": "python_function",
    "version": "1.0.0"
}
```

2. **Register the tool**:

```python
from app.registry import ToolRegistry

tool = await registry.register_tool(**TOOL_METADATA)
```

3. **The tool is now searchable** via semantic search and ready for use!

---

## Configuration

All configuration via environment variables (`.env` file):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/toolregistry

# Embedding Service
EMBEDDING_ENDPOINT_URL=http://localhost:8001/embed
EMBEDDING_API_KEY=your-api-key
EMBEDDING_DIMENSION=1536

# Search
DEFAULT_SIMILARITY_THRESHOLD=0.7
DEFAULT_SEARCH_LIMIT=5
USE_HYBRID_SEARCH=true

# Application
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

See [.env.example](.env.example) for all options.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_vector_store.py -v
```

---

## Deployment

### Docker Compose

```bash
docker-compose up -d
```

### Kubernetes

```bash
kubectl apply -f infrastructure/k8s/base/
```

See [infrastructure/k8s/README.md](infrastructure/k8s/README.md) for details.

---

## Troubleshooting

### Tool not found in search

1. Check if tool has an embedding: `GET /admin/tools/{id}`
2. Regenerate embedding: `POST /admin/tools/{id}/reindex`
3. Lower the similarity threshold in search
4. Check embedding service is running: `GET /health`

### Database connection errors

1. Verify DATABASE_URL is correct
2. Check PostgreSQL is running: `docker-compose ps`
3. Run migrations: `alembic upgrade head`

### Embedding service errors

1. Check EMBEDDING_ENDPOINT_URL is reachable
2. Verify API key if required
3. Test with health check: `GET /health`

---

## Support

- **Documentation**: See [README.md](README.md) and [PLAN.md](PLAN.md)
- **API Docs**: http://localhost:8000/docs
- **Issues**: GitHub Issues

---

## License

MIT
