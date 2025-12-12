# Tool Registry MCP Server - Implementation Plan

## Project Overview

Build a vector-powered tool registry exposed via an MCP (Model Context Protocol) server using Python, FastAPI, and PostgreSQL with pgvector extension. Designed to run anywhere - locally, on Kubernetes, or cloud platforms.

### Key Features
- **Semantic Tool Search**: Find tools using natural language queries
- **Vector Similarity**: Discover related tools based on embeddings
- **MCP Protocol**: Standard `list_tools`, `find_tool`, `call_tool` endpoints
- **Cloud-Native**: Containerized and Kubernetes-ready
- **Database Agnostic**: Works with any PostgreSQL + pgvector (configurable via env vars)
- **12-Factor App**: Configuration via environment, stateless design

---

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Database**: PostgreSQL 15+ with pgvector extension (any provider)
- **ORM**: SQLAlchemy 2.0 with async support
- **Vector Extension**: pgvector for PostgreSQL
- **Embeddings**: Custom embedding endpoint (configured via env vars)
- **Container Runtime**: Docker / Kubernetes

### Deployment Options
- **Kubernetes**: Production deployment with Helm charts (Primary)
- **Docker Compose**: Local development and small deployments
- **Cloud Platforms**: AWS ECS, Google Cloud Run, Azure Container Apps
- **Serverless**: AWS Lambda, Google Cloud Functions (optional)

### Database Options
All configurable via `DATABASE_URL` environment variable:
- **Development**: Local PostgreSQL with pgvector (Docker)
- **Production**:
  - Self-hosted PostgreSQL + pgvector on Kubernetes
  - AWS RDS PostgreSQL
  - Google Cloud SQL for PostgreSQL
  - Azure Database for PostgreSQL
  - Supabase (managed Postgres with pgvector)
  - Neon, Tembo, or other Postgres providers

### Key Dependencies
```
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.23
psycopg2-binary>=2.9.9
asyncpg>=0.29.0
pgvector>=0.2.4
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.25.2
alembic>=1.13.0
python-dotenv>=1.0.0
gunicorn>=21.2.0  # Production WSGI server
```

---

## Architecture

### Kubernetes Deployment (Primary)

```
┌─────────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │                    Ingress                          │    │
│  │         (nginx/traefik/cloud load balancer)         │    │
│  └──────────────────────┬─────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼─────────────────────────────┐    │
│  │              Service (tool-registry)                │    │
│  └──────────────────────┬─────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼─────────────────────────────┐    │
│  │         Deployment (tool-registry-mcp)              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │    │
│  │  │  Pod 1    │  │  Pod 2    │  │  Pod 3    │         │    │
│  │  │ FastAPI  │  │ FastAPI  │  │ FastAPI  │         │    │
│  │  │  Server   │  │  Server   │  │  Server   │         │    │
│  │  └──────────┘  └──────────┘  └──────────┘         │    │
│  └────────────────────┬───────────────────────────────┘    │
│                       │                                      │
│            ┌──────────┴────────────┐                        │
│            ▼                        ▼                        │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │   PostgreSQL     │    │  Your Embedding  │             │
│  │   + pgvector     │    │    Endpoint      │             │
│  │                  │    │  (External/K8s)  │             │
│  │  StatefulSet or  │    └──────────────────┘             │
│  │  External DB     │                                       │
│  └──────────────────┘                                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         ConfigMap / Secrets                           │  │
│  │  - DATABASE_URL                                       │  │
│  │  - EMBEDDING_ENDPOINT_URL                             │  │
│  │  - EMBEDDING_API_KEY                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Docker Compose (Local Development)

```
┌─────────────────────────────────────────────┐
│          Docker Compose Stack                │
│                                              │
│  ┌────────────────────────────────────┐    │
│  │   tool-registry-api                 │    │
│  │   (FastAPI Container)               │    │
│  │   Port: 8000                        │    │
│  └────────┬───────────────────────────┘    │
│           │                                  │
│           ▼                                  │
│  ┌────────────────────────────────────┐    │
│  │   postgres-pgvector                 │    │
│  │   (ankane/pgvector:latest)          │    │
│  │   Port: 5432                        │    │
│  │   Volume: pgdata                    │    │
│  └────────────────────────────────────┘    │
│                                              │
│  External: Your Embedding Endpoint           │
└─────────────────────────────────────────────┘
```

---

## Project Structure

```
toolbox/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + MCP endpoints
│   ├── config.py                    # Configuration & settings
│   │
│   ├── models/                      # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── tool.py                  # Tool model with pgvector
│   │   └── execution.py             # Execution history
│   │
│   ├── schemas/                     # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── tool.py                  # Tool validation schemas
│   │   └── mcp.py                   # MCP protocol schemas
│   │
│   ├── registry/                    # Core registry logic
│   │   ├── __init__.py
│   │   ├── tool_registry.py         # Main registry class
│   │   ├── vector_store.py          # PostgreSQL + pgvector queries
│   │   └── embedding_service.py     # Call embedding endpoint
│   │
│   ├── tools/                       # Tool implementations
│   │   ├── __init__.py
│   │   ├── base.py                  # Base tool interface
│   │   ├── executor.py              # Tool execution engine
│   │   └── examples/
│   │       ├── __init__.py
│   │       ├── calculator.py
│   │       ├── string_utils.py
│   │       └── data_transform.py
│   │
│   ├── db/                          # Database setup
│   │   ├── __init__.py
│   │   ├── session.py               # Async session management
│   │   └── migrations/              # Alembic migrations
│   │       ├── env.py
│   │       └── versions/
│   │           └── 001_initial.py
│   │
│   └── api/                         # API routes
│       ├── __init__.py
│       ├── mcp_routes.py            # MCP protocol endpoints
│       └── health.py                # Health check
│
├── infrastructure/                  # Infrastructure as Code
│   ├── k8s/                         # Kubernetes manifests
│   │   ├── base/                    # Base Kustomize configs
│   │   │   ├── deployment.yaml      # FastAPI deployment
│   │   │   ├── service.yaml         # Service definition
│   │   │   ├── configmap.yaml       # Non-sensitive config
│   │   │   ├── secret.yaml          # Sensitive credentials
│   │   │   └── kustomization.yaml
│   │   ├── overlays/
│   │   │   ├── dev/                 # Dev environment
│   │   │   ├── staging/             # Staging environment
│   │   │   └── prod/                # Production environment
│   │   └── postgres/                # Optional: self-hosted Postgres
│   │       ├── statefulset.yaml
│   │       ├── service.yaml
│   │       └── pvc.yaml
│   │
│   ├── helm/                        # Helm chart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── values-dev.yaml
│   │   ├── values-prod.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── ingress.yaml
│   │       ├── configmap.yaml
│   │       ├── secret.yaml
│   │       ├── hpa.yaml             # Horizontal Pod Autoscaler
│   │       └── _helpers.tpl
│   │
│   └── sql/
│       └── init.sql                 # Initial schema & indexes
│
├── scripts/                         # Utility scripts
│   ├── migrate.py                   # Run database migrations
│   ├── seed_tools.py                # Seed example tools
│   ├── test_search.py               # Test vector search
│   └── local_dev.py                 # Local development server
│
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── test_registry.py
│   ├── test_vector_store.py
│   ├── test_embedding.py
│   └── test_tools.py
│
├── .env.example                     # Environment variables template
├── .gitignore
├── alembic.ini                      # Alembic configuration
├── docker-compose.yml               # Local PostgreSQL + pgvector
├── Dockerfile                       # Container image
├── pyproject.toml                   # Poetry configuration
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── README.md                        # Project documentation
└── PLAN.md                          # This file
```

---

## Database Schema

### Tools Table
```sql
CREATE TABLE tools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    long_description TEXT,
    category VARCHAR(100),
    tags TEXT[],
    examples TEXT[],

    -- JSON schemas
    input_schema JSONB NOT NULL,
    output_schema JSONB,

    -- Vector embedding (1536 dimensions for OpenAI embeddings)
    embedding vector(1536),

    -- Metadata
    version VARCHAR(50) DEFAULT '1.0.0',
    author VARCHAR(255),
    config JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_tools_embedding ON tools
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_tools_category ON tools(category);
CREATE INDEX idx_tools_tags ON tools USING GIN(tags);
CREATE INDEX idx_tools_name ON tools(name);
```

### Tool Executions Table
```sql
CREATE TABLE tool_executions (
    id SERIAL PRIMARY KEY,
    tool_id INTEGER REFERENCES tools(id),
    input_data JSONB NOT NULL,
    output_data JSONB,
    error TEXT,
    duration_ms INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_executions_tool_id ON tool_executions(tool_id);
CREATE INDEX idx_executions_executed_at ON tool_executions(executed_at);
```

---

## Implementation Phases

### Phase 1: Project Setup & Local Development
**Goal**: Set up Python project with local PostgreSQL + pgvector

**Tasks**:
1. Initialize Python project with Poetry/pip
2. Create project structure (directories, __init__.py files)
3. Install dependencies (FastAPI, SQLAlchemy, pgvector, etc.)
4. Set up docker-compose.yml with PostgreSQL + pgvector
5. Create .env.example and configuration management
6. Initialize Git repository with .gitignore

**Deliverables**:
- Working local development environment
- Docker Compose running PostgreSQL with pgvector
- Project structure in place
- Dependencies installed

**Testing**:
- Run `docker-compose up` successfully
- Connect to PostgreSQL and verify pgvector extension
- Import all modules without errors

---

### Phase 2: Database Layer
**Goal**: Set up database models, migrations, and vector operations

**Tasks**:
1. Create SQLAlchemy models (Tool, ToolExecution)
2. Set up Alembic for migrations
3. Create initial migration with pgvector extension
4. Implement async database session management
5. Create indexes for vector search optimization
6. Write database helper functions

**Deliverables**:
- SQLAlchemy models with pgvector support
- Alembic migrations configured
- Database session factory with async support
- Initial migration creates tables and indexes

**Testing**:
- Run migrations successfully
- Insert test tool with vector embedding
- Query tools by vector similarity
- Verify all indexes are created

---

### Phase 3: Vector Store Implementation
**Goal**: Implement vector search and tool storage logic

**Tasks**:
1. Create VectorStore class with pgvector queries
2. Implement semantic search (cosine similarity)
3. Implement hybrid search (vector + full-text)
4. Add filtering by category, tags, metadata
5. Implement find similar tools functionality
6. Add CRUD operations for tools

**Deliverables**:
- VectorStore class with all search methods
- Semantic search using pgvector
- Hybrid search combining vector + text
- Filter and similarity methods

**Testing**:
- Unit tests for vector search
- Test semantic search accuracy
- Test hybrid search ranking
- Test filtering by category/tags
- Benchmark search performance

---

### Phase 4: Embedding Service
**Goal**: Integration with user's embedding endpoint

**Tasks**:
1. Create EmbeddingService class
2. Implement HTTP client for embedding endpoint
3. Add retry logic with exponential backoff
4. Implement batch embedding support
5. Add in-memory caching (LRU cache)
6. Create embedding text preprocessing

**Deliverables**:
- EmbeddingService with async HTTP calls
- Retry and error handling
- Batch processing for efficiency
- Caching layer

**Testing**:
- Test embedding endpoint integration
- Test retry logic on failures
- Test batch embedding
- Test cache hit/miss scenarios
- Mock embedding service for tests

---

### Phase 5: Tool Registry
**Goal**: Core registry logic tying everything together

**Tasks**:
1. Create ToolRegistry class
2. Implement register_tool (embed + index)
3. Implement find_tools (semantic search)
4. Implement get_tool (exact lookup)
5. Implement list_tools (all tools)
6. Implement execute_tool (run + log)
7. Add tool execution tracking

**Deliverables**:
- ToolRegistry class coordinating all operations
- Tool registration with automatic embedding
- All search methods implemented
- Tool execution with logging

**Testing**:
- Test tool registration flow
- Test semantic search end-to-end
- Test tool execution
- Test execution logging
- Integration tests with real database

---

### Phase 6: Example Tools
**Goal**: Create sample tools to test the system

**Tasks**:
1. Define base tool interface/class
2. Create Calculator tool (math operations)
3. Create StringUtils tool (text manipulation)
4. Create DataTransform tool (JSON/CSV conversion)
5. Create tool executor framework
6. Register example tools in system

**Deliverables**:
- Base tool interface
- 3-5 example tools implemented
- Tool executor that runs tool logic
- Tools registered in database

**Testing**:
- Test each example tool independently
- Test tool discovery via semantic search
- Test tool execution through registry
- Verify execution logging

---

### Phase 7: FastAPI MCP Server
**Goal**: Build FastAPI app with MCP protocol endpoints

**Tasks**:
1. Create FastAPI application structure
2. Implement MCP endpoints:
   - POST /mcp/list_tools
   - POST /mcp/find_tool
   - POST /mcp/call_tool
3. Add health check endpoint
4. Add additional utility endpoints
5. Set up dependency injection
6. Add error handling and logging
7. Add CORS middleware

**Deliverables**:
- FastAPI app with MCP endpoints
- Pydantic schemas for request/response validation
- Health check endpoint
- Proper error handling
- API documentation (auto-generated by FastAPI)

**Testing**:
- Test all MCP endpoints with curl/httpx
- Test request validation
- Test error responses
- Load testing with realistic queries
- Test with FastAPI TestClient

---

### Phase 8: Docker & Container Setup
**Goal**: Create production-ready Docker images

**Tasks**:
1. Create optimized Dockerfile (multi-stage build)
2. Add .dockerignore file
3. Create docker-compose.yml for local development
4. Add healthcheck endpoints and container probes
5. Optimize image size (<200MB)
6. Configure proper signal handling (SIGTERM)
7. Set up non-root user in container
8. Add container security scanning

**Deliverables**:
- Production Dockerfile with multi-stage build
- docker-compose.yml for local stack
- Container runs as non-root user
- Healthcheck probes configured
- Documentation for building/running

**Testing**:
- Build Docker image successfully
- Run container locally and test endpoints
- Test with docker-compose stack
- Verify healthcheck endpoints work
- Test graceful shutdown (SIGTERM)

---

### Phase 9: Kubernetes Deployment
**Goal**: Create Kubernetes manifests and Helm chart

**Tasks**:
1. Create Kubernetes deployment manifest
2. Create service and ingress manifests
3. Set up ConfigMap and Secret templates
4. Add HorizontalPodAutoscaler (HPA)
5. Create Helm chart with values files
6. Add liveness and readiness probes
7. Configure resource requests/limits
8. Create separate overlays for dev/staging/prod

**Deliverables**:
- Complete Kubernetes manifests
- Helm chart with templating
- Environment-specific values files
- HPA for auto-scaling
- Kustomize overlays (optional)
- Deployment documentation

**Testing**:
- Deploy to local Kubernetes (minikube/kind)
- Test with external PostgreSQL
- Test HPA scaling
- Verify probes work correctly
- Test rolling updates
- Load test deployed application

---

### Phase 10: Production Features
**Goal**: Add production-ready features

**Tasks**:
1. Add proper logging (structlog or loguru)
2. Add request tracing (correlation IDs)
3. Implement rate limiting
4. Add API authentication (API keys or JWT)
5. Set up CloudWatch alarms
6. Implement backup strategy for RDS
7. Add caching layer (Redis or ElastiCache)
8. Create monitoring dashboards

**Deliverables**:
- Comprehensive logging
- Request tracing
- Rate limiting
- Authentication
- Monitoring and alerts
- Backup/recovery procedures
- Performance optimizations

**Testing**:
- Test logging in production
- Test rate limiting
- Test authentication
- Verify alarms trigger correctly
- Test backup/restore procedures

---

### Phase 11: Documentation & Testing
**Goal**: Complete documentation and comprehensive testing

**Tasks**:
1. Write comprehensive README.md
2. Create API documentation
3. Write developer guide
4. Create deployment guide
5. Write unit tests (90%+ coverage)
6. Write integration tests
7. Write end-to-end tests
8. Create example usage scripts
9. Add inline code documentation

**Deliverables**:
- Complete README with examples
- API documentation
- Developer and deployment guides
- Comprehensive test suite
- Example scripts

**Testing**:
- Achieve 90%+ code coverage
- All tests passing
- Documentation reviewed
- Examples tested

---

## MCP Protocol Endpoints

### 1. List Tools
**Endpoint**: `POST /mcp/list_tools`

**Request**:
```json
{
  "category": "math",  // optional
  "tags": ["numeric"]  // optional
}
```

**Response**:
```json
[
  {
    "name": "calculator",
    "description": "Performs basic math operations",
    "category": "math",
    "tags": ["numeric", "arithmetic"],
    "input_schema": {...},
    "version": "1.0.0",
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

### 2. Find Tool (Semantic Search)
**Endpoint**: `POST /mcp/find_tool`

**Request**:
```json
{
  "query": "tool to add numbers",
  "limit": 5,
  "threshold": 0.7,
  "use_hybrid": true
}
```

**Response**:
```json
[
  {
    "name": "calculator",
    "description": "Performs basic math operations",
    "category": "math",
    "similarity": 0.89,
    "input_schema": {...}
  },
  {
    "name": "math_operations",
    "description": "Advanced mathematical functions",
    "category": "math",
    "similarity": 0.82,
    "input_schema": {...}
  }
]
```

### 3. Call Tool
**Endpoint**: `POST /mcp/call_tool`

**Request**:
```json
{
  "tool_name": "calculator",
  "arguments": {
    "operation": "add",
    "a": 5,
    "b": 3
  }
}
```

**Response**:
```json
{
  "success": true,
  "result": {
    "value": 8
  },
  "duration_ms": 45
}
```

---

## Key Features

### 1. Semantic Search
- Natural language queries to find tools
- Vector embeddings for similarity matching
- Configurable similarity threshold

### 2. Hybrid Search
- Combines vector similarity with full-text search
- Weighted scoring (70% vector, 30% text)
- Better results for mixed queries

### 3. Tool Discovery
- Find similar tools based on existing tool
- Category and tag filtering
- Sorted by relevance

### 4. Tool Execution
- Execute tools with argument validation
- Track execution history
- Performance metrics (duration)
- Error handling and logging

### 5. Extensibility
- Easy to add new tools
- Plugin-like architecture
- Tool versioning support
- Custom metadata

---

## Deployment Options

### Option 1: Kubernetes (Recommended)
**Pros**:
- Portable across cloud providers
- Full control over scaling and resources
- No cold starts
- Industry standard for containerized apps
- Great for complex workflows

**Cons**:
- Requires Kubernetes knowledge
- More initial setup
- Need cluster management

**Cost**:
- Self-managed: $20-50/month (3 small nodes)
- Managed (EKS/GKE/AKS): $70-100/month

### Option 2: Docker Compose
**Pros**:
- Simple deployment model
- Good for small scale / single server
- Easy local development
- No Kubernetes complexity

**Cons**:
- Limited scaling options
- No automatic failover
- Manual container orchestration

**Cost**: ~$10-20/month (single VPS)

### Option 3: Cloud Run / Container Apps
**Pros**:
- Serverless containers
- Auto-scaling
- Pay-per-use
- Managed infrastructure

**Cons**:
- Platform lock-in
- Cold starts possible
- Limited customization

**Cost**: ~$10-30/month for moderate usage

---

## Cost Estimates

### Development Environment (Docker Compose)
- Local PostgreSQL: Free (Docker)
- Development server: Free (local)
- **Total: $0/month**

### Production Environment (Kubernetes)
- Kubernetes cluster (3 nodes): $50/month (self-managed) or $75/month (managed)
- PostgreSQL:
  - Self-hosted on K8s: $10/month (storage)
  - Managed (RDS/CloudSQL): $30-50/month
- Load balancer: $10-20/month
- Monitoring: $5-10/month
- **Total: $75-155/month**

### Production Environment (Serverless)
- Cloud Run / Container Apps: $20/month
- Managed PostgreSQL: $30/month
- **Total: ~$50/month**

---

## Performance Targets

- **Semantic Search**: < 100ms (p95)
- **Exact Lookup**: < 20ms (p95)
- **Tool Execution**: < 500ms (p95, depends on tool)
- **Container Startup**: < 10s
- **Throughput**: 100+ req/s per pod
- **Scalability**: Support up to 100K tools
- **Horizontal Scaling**: 3-10 pods depending on load

---

## Security Considerations

1. **Database**:
   - PostgreSQL credentials in Kubernetes Secrets
   - Encrypted connections (SSL/TLS)
   - Regular automated backups
   - Network policies to restrict access
   - Run PostgreSQL in private network (if self-hosted)

2. **API**:
   - HTTPS/TLS only (via Ingress)
   - API key authentication
   - Rate limiting (via ingress or middleware)
   - Input validation with Pydantic
   - CORS configuration

3. **Container Security**:
   - Non-root user (UID 1000)
   - Read-only root filesystem
   - Security context constraints
   - Image vulnerability scanning
   - Minimal base image (python:3.11-slim)

4. **Kubernetes**:
   - Pod Security Standards (restricted)
   - Network Policies for pod isolation
   - Resource quotas and limits
   - RBAC for service accounts
   - Secrets encrypted at rest

5. **Monitoring**:
   - Centralized logging (ELK/Loki)
   - Failed authentication alerts
   - Error rate monitoring
   - Pod health metrics

---

## Development Workflow

### 1. Local Development (Docker Compose)
```bash
# Start local stack
docker-compose up -d

# Install dependencies
poetry install  # or pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed example tools
python scripts/seed_tools.py

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# View logs
docker-compose logs -f
```

### 2. Testing
```bash
# Run all tests with coverage
pytest tests/ -v --cov=app --cov-report=html

# Run specific test file
pytest tests/test_vector_store.py -v

# Run with markers
pytest -m "not integration" -v
```

### 3. Build & Test Container
```bash
# Build Docker image
docker build -t tool-registry-mcp:latest .

# Run container locally
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e EMBEDDING_ENDPOINT_URL="http://..." \
  tool-registry-mcp:latest

# Test container health
curl http://localhost:8000/health
```

### 4. Deploy to Kubernetes
```bash
# Using kubectl with manifests
kubectl apply -f infrastructure/k8s/base/

# Using Kustomize
kubectl apply -k infrastructure/k8s/overlays/prod/

# Using Helm
helm install tool-registry infrastructure/helm/ \
  -f infrastructure/helm/values-prod.yaml

# Check deployment status
kubectl get pods -l app=tool-registry
kubectl logs -f deployment/tool-registry

# Port forward for testing
kubectl port-forward svc/tool-registry 8000:80
```

### 5. Database Management
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations (in container or K8s job)
kubectl exec -it deployment/tool-registry -- alembic upgrade head

# Rollback migration
alembic downgrade -1

# Seed tools in production
kubectl exec -it deployment/tool-registry -- python scripts/seed_tools.py
```

---

## Success Criteria

- [ ] All 11 phases completed
- [ ] Semantic search returns relevant tools (>0.8 similarity)
- [ ] API responds within performance targets
- [ ] 90%+ test coverage
- [ ] Successfully deployed to Kubernetes
- [ ] Can swap PostgreSQL via environment variable
- [ ] Documentation complete
- [ ] Example tools working
- [ ] Can register and execute custom tools
- [ ] Vector search performs accurately
- [ ] MCP protocol fully implemented
- [ ] Container security best practices followed
- [ ] Helm chart works across environments

---

## Next Steps

1. Review and approve this plan
2. Start with Phase 1: Project Setup
3. Iterate through phases sequentially
4. Test each phase before moving to next
5. Build Docker image in Phase 8
6. Deploy to Kubernetes in Phase 9
7. Add production features in Phase 10
8. Complete documentation in Phase 11

---

## Environment Variables

All configuration via environment variables (12-factor app):

```bash
# Database (required)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Embedding Service (required)
EMBEDDING_ENDPOINT_URL=http://your-embedding-service/embed
EMBEDDING_API_KEY=your-api-key-here  # optional
EMBEDDING_DIMENSION=1536  # default

# Application
APP_NAME=tool-registry-mcp
APP_VERSION=1.0.0
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
WORKERS=4  # Number of uvicorn workers

# Database Connection Pool
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30

# Search Configuration
DEFAULT_SIMILARITY_THRESHOLD=0.7
DEFAULT_SEARCH_LIMIT=5
USE_HYBRID_SEARCH=true

# Security
API_KEY=your-secret-api-key  # optional
CORS_ORIGINS=*  # comma-separated list

# Performance
ENABLE_CACHE=true
CACHE_TTL=300  # seconds
```

---

## Questions to Address

1. **Embedding Endpoint**:
   - What is the exact API format for your embedding endpoint?
   - What embedding dimensions does it return? (assuming 1536)
   - Any authentication required?
   - Rate limits?

2. **Deployment**:
   - Which Kubernetes platform? (EKS, GKE, AKS, self-hosted?)
   - Use managed PostgreSQL or self-host on K8s?
   - Ingress controller preference? (nginx, traefik, istio?)

3. **Tools**:
   - What types of tools should we prioritize for examples?
   - Any specific tool execution requirements?
   - Should tools be sandboxed/isolated?

4. **Scale**:
   - Expected number of tools (100s, 1000s, 10000s)?
   - Expected request volume?
   - Need for caching layer (Redis)?

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Charts Guide](https://helm.sh/docs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [12-Factor App](https://12factor.net/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

## Key Kubernetes Resources

**Deployment Example:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tool-registry
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tool-registry
  template:
    metadata:
      labels:
        app: tool-registry
    spec:
      containers:
      - name: api
        image: tool-registry-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: tool-registry-secret
              key: database-url
        - name: EMBEDDING_ENDPOINT_URL
          valueFrom:
            configMapKeyRef:
              name: tool-registry-config
              key: embedding-url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
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
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
```

**Service Example:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: tool-registry
spec:
  selector:
    app: tool-registry
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

**Ingress Example:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tool-registry
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - tool-registry.yourdomain.com
    secretName: tool-registry-tls
  rules:
  - host: tool-registry.yourdomain.com
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
