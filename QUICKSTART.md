# Tool Registry MCP Server - Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (optional, for local development)
- An embedding service endpoint (or use a mock for testing)

## 1. Clone and Configure

```bash
# Clone the repository
cd Toolbox

# Copy environment template
cp .env.example .env

# Edit .env with your settings (or use defaults for testing)
# Required: DATABASE_URL, EMBEDDING_ENDPOINT_URL
```

**Default .env for testing:**
```bash
DATABASE_URL=postgresql+asyncpg://toolregistry:devpassword@postgres:5432/toolregistry
EMBEDDING_ENDPOINT_URL=http://localhost:8001/embed
EMBEDDING_API_KEY=dev-key
LOG_LEVEL=DEBUG
```

## 2. Start the Server

```bash
# Start all services (PostgreSQL + migrations + API)
docker-compose up -d

# Check logs
docker-compose logs -f api

# Verify services are running
docker-compose ps
```

**Expected output:**
```
tool-registry-postgres     running
tool-registry-migrations   exited (0)
tool-registry-api          running
```

## 3. Verify It's Working

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "service": "tool-registry-mcp",
  "version": "1.0.0",
  "database": true,
  "embedding_service": false,  # false if no embedding service yet
  "indexed_tools": 0
}
```

## 4. Register Example Tools

```bash
# Install dependencies (if not using Docker)
pip install -r requirements.txt

# Register calculator and string tools
python examples/register_tools.py
```

**Expected output:**
```
🔧 Tool Registry - Registration Example
==================================================

📊 Registering Calculator tool...
✅ Registered: calculator (ID: 1)

📝 Registering String tools...
✅ Registered: string_uppercase (ID: 2)
✅ Registered: string_lowercase (ID: 3)
✅ Registered: string_reverse (ID: 4)
✅ Registered: string_length (ID: 5)
✅ Registered: word_count (ID: 6)

📊 Tool Registry Statistics:
   Total active tools: 6
   Tools with embeddings: 6

✅ Registration complete!
```

## 5. Test Semantic Search

```bash
# Search for tools
python examples/search_tools.py "calculate numbers"
```

**Expected output:**
```
Tool Registry - Semantic Search Example
==================================================
Query: 'calculate numbers'

Vector Search Results:
--------------------------------------------------

1. calculator (score: 0.893)
   Category: math
   Description: Perform basic arithmetic operations...
   Tags: math, arithmetic, calculator, numbers
```

## 6. Use the REST API

### Interactive Documentation

Open in your browser:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Example API Calls

**List all tools:**
```bash
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "active_only": true}' | jq
```

**Find tools (semantic search):**
```bash
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{
    "query": "tool to manipulate text",
    "limit": 5,
    "threshold": 0.6,
    "use_hybrid": true
  }' | jq
```

**Call a tool:**
```bash
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculator",
    "arguments": {
      "operation": "add",
      "a": 5,
      "b": 3
    }
  }' | jq
```

**Register a new tool:**
```bash
curl -X POST http://localhost:8000/admin/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "json_formatter",
    "description": "Format and validate JSON strings",
    "category": "utility",
    "tags": ["json", "format", "validate"],
    "input_schema": {
      "type": "object",
      "properties": {
        "json_string": {"type": "string"}
      },
      "required": ["json_string"]
    },
    "auto_embed": true
  }' | jq
```

**Get tool statistics:**
```bash
curl http://localhost:8000/admin/tools/1/stats | jq
```

## 7. Run All Examples

```bash
# Complete API walkthrough
bash examples/mcp_api_examples.sh
```

## Common Tasks

### View Logs

```bash
# API logs
docker-compose logs -f api

# Migration logs
docker-compose logs migrations

# Database logs
docker-compose logs postgres
```

### Restart Services

```bash
# Restart just the API
docker-compose restart api

# Restart everything
docker-compose restart
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

### Run Migrations Manually

```bash
# Inside the API container
docker-compose exec api alembic upgrade head

# Check migration status
docker-compose exec api alembic current

# View migration history
docker-compose exec api alembic history
```

### Access Database

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U toolregistry -d toolregistry

# Inside psql:
\dt                    # List tables
\d tools               # Describe tools table
SELECT * FROM tools;   # View all tools
```

## Troubleshooting

### API Won't Start

**Check logs:**
```bash
docker-compose logs api
```

**Common issues:**
1. Database not ready - wait a few seconds and retry
2. Migrations failed - check `docker-compose logs migrations`
3. Port 8000 already in use - change port in docker-compose.yml

### Database Connection Errors

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Embedding Service Errors

If you don't have an embedding service yet:

1. Health check will show `"embedding_service": false` (this is OK)
2. Tools will still register but won't have embeddings
3. Semantic search won't work until embeddings are generated

**To test without embeddings:**
- Use `POST /mcp/list_tools` instead of find_tool
- Set up a mock embedding service (see USAGE.md)

### Search Returns No Results

```bash
# Check if tools have embeddings
curl http://localhost:8000/admin/tools/1 | jq .embedding

# Regenerate embeddings
curl -X POST http://localhost:8000/admin/tools/1/reindex

# Lower the similarity threshold
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "threshold": 0.3}'
```

## Next Steps

1. **Set up your embedding service** - Configure EMBEDDING_ENDPOINT_URL
2. **Register your tools** - Use the admin API or Python SDK
3. **Explore the API** - Check out http://localhost:8000/docs
4. **Read the full guide** - See [USAGE.md](USAGE.md) for complete documentation
5. **Deploy to production** - See [infrastructure/k8s/README.md](infrastructure/k8s/README.md)

## Production Deployment

### Docker

```bash
# Build production image
docker build -t tool-registry-mcp:latest .

# Run with production settings
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e EMBEDDING_ENDPOINT_URL="https://..." \
  tool-registry-mcp:latest
```

### Kubernetes

```bash
# Update secrets and config
vim infrastructure/k8s/base/secret.yaml
vim infrastructure/k8s/base/configmap.yaml

# Deploy
kubectl apply -f infrastructure/k8s/base/

# Check status
kubectl get pods -l app=tool-registry
kubectl logs -f <pod-name> -c migrations
kubectl logs -f <pod-name> -c api
```

See [infrastructure/k8s/README.md](infrastructure/k8s/README.md) for full deployment guide.

## Resources

- **Documentation**: [USAGE.md](USAGE.md) - Comprehensive usage guide
- **Architecture**: [PLAN.md](PLAN.md) - Full implementation plan
- **Progress**: [TICKETS.md](TICKETS.md) - Development tickets
- **API Docs**: http://localhost:8000/docs (when running)

## Support

- **Issues**: Report bugs or request features on GitHub
- **Questions**: See USAGE.md or check the API documentation

---

**You're all set!** The Tool Registry MCP Server is ready to use.
