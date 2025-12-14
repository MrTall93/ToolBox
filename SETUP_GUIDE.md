# Complete Setup Guide: Tool Registry with FastMCP Server and LiteLLM

This guide walks through setting up the Tool Registry with FastMCP Server in front of LiteLLM, using Docker and Kubernetes.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Kubernetes Cluster                              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                            Ingress (nginx)                              │ │
│  │                         tool-registry.local                             │ │
│  └────────────────────────────────┬───────────────────────────────────────┘ │
│                                   │                                          │
│                                   ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │              Tool Registry with FastMCP Server (this project)                    │ │
│  │                        Port: 8000                                       │ │
│  │                                                                          │ │
│  │   • POST /mcp/find_tool  → Semantic search (pgvector)                  │ │
│  │   • POST /mcp/call_tool  → Proxy to LiteLLM or execute locally         │ │
│  │   • POST /mcp/list_tools → List all registered tools                   │ │
│  └────────────────────────────────┬───────────────────────────────────────┘ │
│                                   │                                          │
│              ┌────────────────────┼────────────────────┐                    │
│              │                    │                    │                    │
│              ▼                    ▼                    ▼                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   PostgreSQL     │  │  LiteLLM Gateway │  │ Embedding Service│         │
│  │   + pgvector     │  │   Port: 4000     │  │   Port: 8080     │         │
│  │   Port: 5432     │  │                  │  │  (text-embeddings│         │
│  └──────────────────┘  │  Models:         │  │   -inference)    │         │
│                        │  • gpt-4         │  └──────────────────┘         │
│                        │  • claude-3      │                                │
│                        │  • ollama/local  │                                │
│                        └────────┬─────────┘                                │
│                                 │                                          │
│              ┌──────────────────┼──────────────────┐                       │
│              │                  │                  │                       │
│              ▼                  ▼                  ▼                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  MCP Server 1    │  │  MCP Server 2    │  │  MCP Server 3    │        │
│  │  (filesystem)    │  │  (fetch/web)     │  │  (sqlite)        │        │
│  │  Port: 3001      │  │  Port: 3002      │  │  Port: 3003      │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Local Docker Compose Setup

### Step 1: Create the Docker Compose Stack

Create `docker-compose.full.yml`:

```yaml
version: '3.8'

services:
  # ============================================================================
  # Core Infrastructure
  # ============================================================================

  # PostgreSQL with pgvector for semantic search
  postgres:
    image: pgvector/pgvector:pg16
    container_name: toolbox-postgres
    environment:
      POSTGRES_USER: toolbox
      POSTGRES_PASSWORD: toolbox_secret
      POSTGRES_DB: toolbox
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infrastructure/sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U toolbox"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Text Embeddings Service (using TEI - Text Embeddings Inference)
  embeddings:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.2
    container_name: toolbox-embeddings
    command: --model-id BAAI/bge-small-en-v1.5 --port 8080
    ports:
      - "8080:8080"
    volumes:
      - embeddings_cache:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ============================================================================
  # LiteLLM Gateway
  # ============================================================================

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: toolbox-litellm
    ports:
      - "4000:4000"
    environment:
      - LITELLM_MASTER_KEY=sk-litellm-master-key
      - DATABASE_URL=postgresql://toolbox:toolbox_secret@postgres:5432/litellm
      # Add your API keys here
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: --config /app/config.yaml --port 4000 --detailed_debug
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ============================================================================
  # External MCP Servers (optional)
  # ============================================================================

  # External MCP servers are now configured through the Toolbox admin API
  # See documentation for how to register external MCP servers
  # Example servers below are commented out as they are now external

  # ============================================================================
  # Tool Registry MCP Server (This Project)
  # ============================================================================

  tool-registry:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: tool-registry
    ports:
      - "8000:8000"
    environment:
      # Database
      - DATABASE_URL=postgresql+asyncpg://toolbox:toolbox_secret@postgres:5432/toolbox
      - DB_POOL_SIZE=5
      - DB_MAX_OVERFLOW=10

      # Embedding Service
      - EMBEDDING_ENDPOINT_URL=http://embeddings:8080/embed
      - EMBEDDING_DIMENSION=384  # BGE-small dimension

      # LiteLLM Gateway
      - LITELLM_GATEWAY_URL=http://litellm:4000
      - LITELLM_API_KEY=sk-litellm-master-key
      - LITELLM_TIMEOUT=60
      - LITELLM_DEFAULT_MODEL=gpt-4

      # Application
      - APP_NAME=tool-registry-mcp
      - LOG_LEVEL=DEBUG
      - API_KEY=sk-tool-registry-api-key

      # Search defaults
      - DEFAULT_SIMILARITY_THRESHOLD=0.7
      - USE_HYBRID_SEARCH=true
    depends_on:
      postgres:
        condition: service_healthy
      embeddings:
        condition: service_healthy
      litellm:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  embeddings_cache:
  sqlite_data:
```

### Step 2: Create LiteLLM Configuration

Create `litellm_config.yaml`:

```yaml
# LiteLLM Configuration
# https://docs.litellm.ai/docs/proxy/configs

model_list:
  # OpenAI Models
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY

  - model_name: gpt-4-turbo
    litellm_params:
      model: openai/gpt-4-turbo-preview
      api_key: os.environ/OPENAI_API_KEY

  - model_name: gpt-3.5-turbo
    litellm_params:
      model: openai/gpt-3.5-turbo
      api_key: os.environ/OPENAI_API_KEY

  # Anthropic Models
  - model_name: claude-3-opus
    litellm_params:
      model: anthropic/claude-3-opus-20240229
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-3-sonnet
    litellm_params:
      model: anthropic/claude-3-sonnet-20240229
      api_key: os.environ/ANTHROPIC_API_KEY

  # Local Ollama (if running)
  - model_name: llama3
    litellm_params:
      model: ollama/llama3
      api_base: http://host.docker.internal:11434

litellm_settings:
  # Enable detailed logging
  set_verbose: true

  # Request timeout
  request_timeout: 120

  # Enable caching
  cache: true
  cache_params:
    type: redis
    host: redis
    port: 6379

general_settings:
  master_key: sk-litellm-master-key
  database_url: postgresql://toolbox:toolbox_secret@postgres:5432/litellm
```

### Step 3: Create Initialization SQL

Create `infrastructure/sql/init.sql`:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create databases for each service
CREATE DATABASE litellm;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE toolbox TO toolbox;
GRANT ALL PRIVILEGES ON DATABASE litellm TO toolbox;
```

### Step 4: Create Environment File

Create `.env`:

```bash
# API Keys (add your own)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Tool Registry
TOOL_REGISTRY_API_KEY=sk-tool-registry-api-key

# LiteLLM
LITELLM_MASTER_KEY=sk-litellm-master-key
```

### Step 5: Start the Stack

```bash
# Create workspace directory for filesystem MCP
mkdir -p workspace

# Build and start all services
docker-compose -f docker-compose.full.yml up --build -d

# Check status
docker-compose -f docker-compose.full.yml ps

# View logs
docker-compose -f docker-compose.full.yml logs -f tool-registry

# Run database migrations
docker-compose -f docker-compose.full.yml exec tool-registry alembic upgrade head
```

### Step 6: Seed Sample Tools

Create `scripts/seed_tools_full.py`:

```python
#!/usr/bin/env python3
"""Seed the tool registry with sample tools and external MCP server proxies."""

import asyncio
import httpx

TOOL_REGISTRY_URL = "http://localhost:8000"
API_KEY = "sk-tool-registry-api-key"

SAMPLE_TOOLS = [
    # =========================================================================
    # Local Python Tools
    # =========================================================================
    {
        "name": "calculator",
        "description": "Perform mathematical calculations including addition, subtraction, multiplication, division, and advanced operations like power and square root.",
        "category": "math",
        "tags": ["math", "arithmetic", "calculator", "numbers"],
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide", "power", "sqrt"],
                    "description": "The mathematical operation to perform"
                },
                "a": {"type": "number", "description": "First operand"},
                "b": {"type": "number", "description": "Second operand (not needed for sqrt)"}
            },
            "required": ["operation", "a"]
        },
        "implementation_type": "python_code",
        "implementation_code": "app.tools.implementations.calculator.execute"
    },
    {
        "name": "string_transformer",
        "description": "Transform strings with operations like uppercase, lowercase, reverse, title case, and character counting.",
        "category": "text",
        "tags": ["string", "text", "transform", "format"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to transform"},
                "operation": {
                    "type": "string",
                    "enum": ["upper", "lower", "reverse", "title", "count_chars", "count_words"],
                    "description": "The transformation to apply"
                }
            },
            "required": ["text", "operation"]
        },
        "implementation_type": "python_code",
        "implementation_code": "app.tools.implementations.string_tools.execute"
    },

    # =========================================================================
    # MCP Server Proxy Tools (filesystem)
    # =========================================================================
    {
        "name": "read_file",
        "description": "Read the contents of a file from the workspace. Use this to view file contents, check configurations, or analyze code.",
        "category": "filesystem",
        "tags": ["file", "read", "filesystem", "io"],
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root"
                }
            },
            "required": ["path"]
        },
        "implementation_type": "http_endpoint",
        "implementation_code": '{"url": "http://mcp-filesystem:3000/tools/read_file", "method": "POST"}'
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace. Creates the file if it doesn't exist, overwrites if it does.",
        "category": "filesystem",
        "tags": ["file", "write", "filesystem", "io", "create"],
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to workspace root"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        },
        "implementation_type": "http_endpoint",
        "implementation_code": '{"url": "http://mcp-filesystem:3000/tools/write_file", "method": "POST"}'
    },
    {
        "name": "list_directory",
        "description": "List all files and directories in a given path. Useful for exploring project structure.",
        "category": "filesystem",
        "tags": ["file", "list", "directory", "filesystem", "explore"],
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to workspace root",
                    "default": "."
                }
            }
        },
        "implementation_type": "http_endpoint",
        "implementation_code": '{"url": "http://mcp-filesystem:3000/tools/list_directory", "method": "POST"}'
    },

    # =========================================================================
    # MCP Server Proxy Tools (fetch/web)
    # =========================================================================
    {
        "name": "fetch_url",
        "description": "Fetch content from a URL. Can retrieve web pages, APIs, or any HTTP resource. Returns the response body.",
        "category": "web",
        "tags": ["http", "fetch", "web", "api", "url", "request"],
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "default": "GET",
                    "description": "HTTP method"
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers"
                }
            },
            "required": ["url"]
        },
        "implementation_type": "http_endpoint",
        "implementation_code": '{"url": "http://mcp-fetch:3000/tools/fetch", "method": "POST"}'
    },

    # =========================================================================
    # MCP Server Proxy Tools (sqlite)
    # =========================================================================
    {
        "name": "sql_query",
        "description": "Execute a SQL query against the SQLite database. Use for reading data with SELECT queries.",
        "category": "database",
        "tags": ["sql", "database", "query", "sqlite", "select"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute"
                }
            },
            "required": ["query"]
        },
        "implementation_type": "http_endpoint",
        "implementation_code": '{"url": "http://mcp-sqlite:3000/tools/query", "method": "POST"}'
    },
    {
        "name": "sql_execute",
        "description": "Execute a SQL statement for modifications (INSERT, UPDATE, DELETE, CREATE TABLE).",
        "category": "database",
        "tags": ["sql", "database", "execute", "sqlite", "insert", "update", "delete"],
        "input_schema": {
            "type": "object",
            "properties": {
                "statement": {
                    "type": "string",
                    "description": "SQL statement to execute"
                }
            },
            "required": ["statement"]
        },
        "implementation_type": "http_endpoint",
        "implementation_code": '{"url": "http://mcp-sqlite:3000/tools/execute", "method": "POST"}'
    },

    # =========================================================================
    # LiteLLM Proxy Tools (for AI-powered operations)
    # =========================================================================
    {
        "name": "ai_summarize",
        "description": "Use AI to summarize text content. Supports long documents and maintains key information.",
        "category": "ai",
        "tags": ["ai", "summarize", "nlp", "text", "gpt", "claude"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text content to summarize"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum length of summary in words",
                    "default": 100
                },
                "style": {
                    "type": "string",
                    "enum": ["brief", "detailed", "bullet_points"],
                    "default": "brief",
                    "description": "Style of the summary"
                }
            },
            "required": ["text"]
        },
        "implementation_type": "litellm_proxy",
        "implementation_code": '{"model": "gpt-3.5-turbo", "system_prompt": "You are a helpful assistant that summarizes text concisely."}'
    },
    {
        "name": "ai_code_review",
        "description": "Use AI to review code for bugs, security issues, and best practices. Provides actionable feedback.",
        "category": "ai",
        "tags": ["ai", "code", "review", "security", "best-practices"],
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code to review"
                },
                "language": {
                    "type": "string",
                    "description": "Programming language",
                    "default": "python"
                },
                "focus": {
                    "type": "string",
                    "enum": ["bugs", "security", "performance", "style", "all"],
                    "default": "all",
                    "description": "What to focus the review on"
                }
            },
            "required": ["code"]
        },
        "implementation_type": "litellm_proxy",
        "implementation_code": '{"model": "gpt-4", "system_prompt": "You are an expert code reviewer. Analyze code for bugs, security vulnerabilities, and improvements."}'
    },
    {
        "name": "ai_translate",
        "description": "Translate text between languages using AI. Supports all major languages.",
        "category": "ai",
        "tags": ["ai", "translate", "language", "nlp"],
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to translate"
                },
                "target_language": {
                    "type": "string",
                    "description": "Target language (e.g., 'Spanish', 'French', 'Japanese')"
                },
                "source_language": {
                    "type": "string",
                    "description": "Source language (auto-detect if not specified)",
                    "default": "auto"
                }
            },
            "required": ["text", "target_language"]
        },
        "implementation_type": "litellm_proxy",
        "implementation_code": '{"model": "gpt-3.5-turbo", "system_prompt": "You are a professional translator. Translate text accurately while preserving meaning and tone."}'
    }
]


async def seed_tools():
    """Seed all sample tools."""
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    async with httpx.AsyncClient() as client:
        for tool in SAMPLE_TOOLS:
            print(f"Registering tool: {tool['name']}...")

            try:
                response = await client.post(
                    f"{TOOL_REGISTRY_URL}/admin/tools",
                    json=tool,
                    headers=headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    print(f"  ✓ Successfully registered: {tool['name']}")
                elif response.status_code == 409:
                    print(f"  - Already exists: {tool['name']}")
                else:
                    print(f"  ✗ Failed: {response.status_code} - {response.text}")

            except Exception as e:
                print(f"  ✗ Error: {str(e)}")

        print("\n" + "=" * 50)
        print("Seeding complete!")

        # List all tools
        response = await client.post(
            f"{TOOL_REGISTRY_URL}/mcp/list_tools",
            json={"limit": 100},
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"Total tools registered: {data['total']}")
            print("\nTools by category:")

            categories = {}
            for tool in data['tools']:
                cat = tool['category']
                categories[cat] = categories.get(cat, 0) + 1

            for cat, count in sorted(categories.items()):
                print(f"  • {cat}: {count} tools")


if __name__ == "__main__":
    asyncio.run(seed_tools())
```

Run the seeding script:

```bash
# Make sure services are healthy first
docker-compose -f docker-compose.full.yml ps

# Run the seed script
python scripts/seed_tools_full.py
```

---

## Part 2: Testing the Setup

### Test 1: Health Check

```bash
# Tool Registry health
curl http://localhost:8000/health | jq

# LiteLLM health
curl http://localhost:4000/health | jq

# Embeddings health
curl http://localhost:8080/health
```

### Test 2: Semantic Search (find_tool)

```bash
# Find math-related tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "query": "I need to add two numbers together",
    "limit": 5,
    "threshold": 0.5
  }' | jq

# Find file operation tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "query": "read contents of a file",
    "limit": 5
  }' | jq

# Find AI tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "query": "summarize a long document using AI",
    "limit": 3
  }' | jq

# Find database tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "query": "query a database table",
    "limit": 3
  }' | jq
```

### Test 3: Execute Tools (call_tool)

```bash
# Test calculator (local Python)
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "tool_name": "calculator",
    "arguments": {
      "operation": "add",
      "a": 15,
      "b": 27
    }
  }' | jq

# Test string transformer (local Python)
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "tool_name": "string_transformer",
    "arguments": {
      "text": "hello world from tool registry",
      "operation": "upper"
    }
  }' | jq

# Test list directory (MCP filesystem server)
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "tool_name": "list_directory",
    "arguments": {
      "path": "."
    }
  }' | jq

# Test URL fetch (MCP fetch server)
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "tool_name": "fetch_url",
    "arguments": {
      "url": "https://httpbin.org/json"
    }
  }' | jq
```

### Test 4: List All Tools

```bash
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-tool-registry-api-key" \
  -d '{
    "limit": 100,
    "active_only": true
  }' | jq
```

---

## Part 3: Kubernetes Deployment

### Step 1: Create Namespace

```bash
kubectl create namespace toolbox
```

### Step 2: Create Secrets

```bash
# Create secrets
kubectl create secret generic toolbox-secrets \
  --namespace toolbox \
  --from-literal=DATABASE_URL="postgresql+asyncpg://toolbox:toolbox_secret@postgres:5432/toolbox" \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --from-literal=API_KEY="sk-tool-registry-api-key" \
  --from-literal=LITELLM_MASTER_KEY="sk-litellm-master-key"
```

### Step 3: Create ConfigMap

Create `kubernetes/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: toolbox-config
  namespace: toolbox
data:
  APP_NAME: "tool-registry-mcp"
  LOG_LEVEL: "INFO"
  EMBEDDING_ENDPOINT_URL: "http://embeddings:8080/embed"
  EMBEDDING_DIMENSION: "384"
  LITELLM_GATEWAY_URL: "http://litellm:4000"
  LITELLM_TIMEOUT: "60"
  LITELLM_DEFAULT_MODEL: "gpt-4"
  DEFAULT_SIMILARITY_THRESHOLD: "0.7"
  USE_HYBRID_SEARCH: "true"
  DB_POOL_SIZE: "5"
  DB_MAX_OVERFLOW: "10"
```

### Step 4: PostgreSQL StatefulSet

Create `kubernetes/postgres.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: toolbox
spec:
  ports:
    - port: 5432
  selector:
    app: postgres
  clusterIP: None
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: toolbox
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: pgvector/pgvector:pg16
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_USER
              value: toolbox
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: DATABASE_URL
            - name: POSTGRES_DB
              value: toolbox
          volumeMounts:
            - name: postgres-data
              mountPath: /var/lib/postgresql/data
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
  volumeClaimTemplates:
    - metadata:
        name: postgres-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

### Step 5: Tool Registry Deployment

Create `kubernetes/tool-registry.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tool-registry
  namespace: toolbox
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tool-registry
  template:
    metadata:
      labels:
        app: tool-registry
    spec:
      containers:
        - name: tool-registry
          image: tool-registry-mcp:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: toolbox-config
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: DATABASE_URL
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: API_KEY
            - name: LITELLM_API_KEY
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: LITELLM_MASTER_KEY
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: tool-registry
  namespace: toolbox
spec:
  selector:
    app: tool-registry
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tool-registry
  namespace: toolbox
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: tool-registry.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: tool-registry
                port:
                  number: 80
```

### Step 6: LiteLLM Deployment

Create `kubernetes/litellm.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm
  namespace: toolbox
spec:
  replicas: 1
  selector:
    matchLabels:
      app: litellm
  template:
    metadata:
      labels:
        app: litellm
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:main-latest
          ports:
            - containerPort: 4000
          env:
            - name: LITELLM_MASTER_KEY
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: LITELLM_MASTER_KEY
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: OPENAI_API_KEY
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: toolbox-secrets
                  key: ANTHROPIC_API_KEY
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
      volumes:
        - name: config
          configMap:
            name: litellm-config
---
apiVersion: v1
kind: Service
metadata:
  name: litellm
  namespace: toolbox
spec:
  selector:
    app: litellm
  ports:
    - port: 4000
      targetPort: 4000
  type: ClusterIP
```

### Step 7: Deploy Everything

```bash
# Apply all manifests
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/postgres.yaml
kubectl apply -f kubernetes/litellm.yaml
kubectl apply -f kubernetes/tool-registry.yaml

# Check status
kubectl get pods -n toolbox
kubectl get svc -n toolbox

# Port forward for testing
kubectl port-forward svc/tool-registry 8000:80 -n toolbox

# View logs
kubectl logs -f deployment/tool-registry -n toolbox
```

---

## Part 4: Integration with LLM Clients

### Using with OpenAI SDK

```python
import openai
import httpx

# Step 1: Find the right tool using semantic search
async def find_tool(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/mcp/find_tool",
            json={"query": query, "limit": 1},
            headers={"X-API-Key": "sk-tool-registry-api-key"}
        )
        return response.json()["results"][0]["tool"]

# Step 2: Execute the tool
async def execute_tool(tool_name: str, arguments: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/mcp/call_tool",
            json={"tool_name": tool_name, "arguments": arguments},
            headers={"X-API-Key": "sk-tool-registry-api-key"}
        )
        return response.json()

# Example usage
async def main():
    # User asks: "Add 15 and 27"
    tool = await find_tool("add two numbers")
    print(f"Found tool: {tool['name']}")

    result = await execute_tool("calculator", {"operation": "add", "a": 15, "b": 27})
    print(f"Result: {result}")

asyncio.run(main())
```

### Using with LangChain

```python
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
import httpx

class MCPToolRegistry:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def find_tool(self, query: str) -> dict:
        response = httpx.post(
            f"{self.base_url}/mcp/find_tool",
            json={"query": query, "limit": 1},
            headers={"X-API-Key": self.api_key}
        )
        return response.json()["results"][0]["tool"]

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        response = httpx.post(
            f"{self.base_url}/mcp/call_tool",
            json={"tool_name": tool_name, "arguments": arguments},
            headers={"X-API-Key": self.api_key}
        )
        return response.json()

# Create LangChain tool wrapper
registry = MCPToolRegistry("http://localhost:8000", "sk-tool-registry-api-key")

calculator_tool = Tool(
    name="calculator",
    func=lambda args: registry.call_tool("calculator", eval(args)),
    description="Perform mathematical calculations"
)

# Initialize agent
llm = ChatOpenAI(model="gpt-4")
agent = initialize_agent(
    [calculator_tool],
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Run
agent.run("What is 15 + 27?")
```

---

## Troubleshooting

### Common Issues

1. **Embeddings service not starting**
   ```bash
   # Check logs
   docker-compose logs embeddings

   # May need more memory for the model
   # Try using a smaller model or increase Docker memory
   ```

2. **Database connection refused**
   ```bash
   # Check if postgres is healthy
   docker-compose ps postgres

   # Check logs
   docker-compose logs postgres
   ```

3. **Tool not found in semantic search**
   ```bash
   # Check if embeddings were generated
   curl -X POST http://localhost:8000/admin/tools/1/reindex \
     -H "X-API-Key: sk-tool-registry-api-key"

   # Lower the similarity threshold
   curl -X POST http://localhost:8000/mcp/find_tool \
     -H "Content-Type: application/json" \
     -d '{"query": "your query", "threshold": 0.3}'
   ```

4. **MCP servers not responding**
   ```bash
   # Check if MCP containers are running
   docker-compose ps mcp-filesystem mcp-fetch mcp-sqlite

   # Test MCP server directly
   curl http://localhost:3001/health
   ```

---

## Next Steps

1. **Add more MCP servers**: GitHub, Slack, Google Drive, etc.
2. **Implement the LITELLM_PROXY executor**: For AI-powered tools
3. **Add authentication**: OAuth2/JWT for production
4. **Set up monitoring**: Prometheus + Grafana dashboards
5. **Configure autoscaling**: HPA based on request rate
