# ToolBox Improvement Tickets

This document contains detailed improvement tickets for the ToolBox codebase, organized by priority and category. Each ticket includes context, current state, proposed solution, affected files, and acceptance criteria.

---

## Completed Tickets

### Phase 1 (High Priority) - COMPLETED
- [x] TICK-001: Replace Deprecated FastAPI Lifecycle Events
- [x] TICK-002: Fix Readiness Probe HTTP Status Codes
- [x] TICK-003: Add Proper Exception Logging with Stack Traces

### Phase 2 (Medium Priority) - COMPLETED
- [x] TICK-004: Consolidate SSL/TLS Configuration Logic
- [x] TICK-005: Migrate to Pydantic v2 model_config
- [x] TICK-006: Fix Conditional Imports for OpenTelemetry
- [x] TICK-007: Add Database Connection Pool Timeout
- [x] TICK-008: Improve Health Check Error Handling

---

## Table of Contents

1. [High Priority (COMPLETED)](#high-priority)
   - [TICK-001: Replace Deprecated FastAPI Lifecycle Events](#tick-001-replace-deprecated-fastapi-lifecycle-events) ✅
   - [TICK-002: Fix Readiness Probe HTTP Status Codes](#tick-002-fix-readiness-probe-http-status-codes) ✅
   - [TICK-003: Add Proper Exception Logging with Stack Traces](#tick-003-add-proper-exception-logging-with-stack-traces) ✅

2. [Medium Priority (COMPLETED)](#medium-priority)
   - [TICK-004: Consolidate SSL/TLS Configuration Logic](#tick-004-consolidate-ssltls-configuration-logic) ✅
   - [TICK-005: Migrate to Pydantic v2 model_config](#tick-005-migrate-to-pydantic-v2-model_config) ✅
   - [TICK-006: Fix Conditional Imports for OpenTelemetry](#tick-006-fix-conditional-imports-for-opentelemetry) ✅
   - [TICK-007: Add Database Connection Pool Timeout](#tick-007-add-database-connection-pool-timeout) ✅
   - [TICK-008: Improve Health Check Error Handling](#tick-008-improve-health-check-error-handling) ✅

3. [Low Priority](#low-priority)
   - [TICK-009: Add Annotated Type Hints for Dependencies](#tick-009-add-annotated-type-hints-for-dependencies)
   - [TICK-010: Add __all__ Exports to Modules](#tick-010-add-__all__-exports-to-modules)
   - [TICK-011: Fix Optional Type Hints](#tick-011-fix-optional-type-hints)
   - [TICK-012: Add FastMCP Resources and Prompts](#tick-012-add-fastmcp-resources-and-prompts)
   - [TICK-013: Add Response Models for Error Cases](#tick-013-add-response-models-for-error-cases)
   - [TICK-014: Add Configuration Validation](#tick-014-add-configuration-validation)
   - [TICK-015: Add Input Sanitization for Database Queries](#tick-015-add-input-sanitization-for-database-queries)

4. [Future Enhancements](#future-enhancements)
   - [TICK-016: Add Rate Limiting Middleware](#tick-016-add-rate-limiting-middleware)
   - [TICK-017: Create Shared Types Module](#tick-017-create-shared-types-module)
   - [TICK-018: Add Test Fixtures for Authentication](#tick-018-add-test-fixtures-for-authentication)

---

## High Priority

### TICK-001: Replace Deprecated FastAPI Lifecycle Events

**Priority:** 🔴 High
**Category:** FastAPI Best Practices
**Estimated Effort:** Medium
**Breaking Change:** No

#### Description

The `@app.on_event("startup")` and `@app.on_event("shutdown")` decorators are deprecated in FastAPI and will be removed in a future version. The application should migrate to the new `lifespan` context manager pattern.

#### Current State

**File:** `app/main.py` (lines 146-202)

```python
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting...")
    # ... startup logic ...

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown with graceful shutdown."""
    logger.info(f"👋 {settings.APP_NAME} shutting down gracefully...")
    # ... shutdown logic ...
```

#### Proposed Solution

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # ==================== STARTUP ====================
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting...")
    logger.info("Interactive docs: http://localhost:8000/docs")
    logger.info("MCP endpoints ready at /mcp/")
    logger.info("Admin endpoints ready at /admin/")

    # Test database connection
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise

    # Auto-sync MCP servers on startup
    if settings.MCP_AUTO_SYNC_ON_STARTUP and settings.MCP_SERVERS:
        logger.info(f"🔄 Auto-syncing {len(settings.MCP_SERVERS)} MCP servers...")
        try:
            from app.services.mcp_discovery import get_mcp_discovery_service
            discovery_service = get_mcp_discovery_service()

            async with AsyncSessionLocal() as db:
                results = await discovery_service.sync_all_servers(session=db)
                logger.info(
                    f"✅ MCP sync complete: {results['successful_syncs']}/{results['total_servers']} servers, "
                    f"{results['total_tools_created']} created, {results['total_tools_updated']} updated"
                )
        except Exception as e:
            logger.warning(f"⚠️ MCP auto-sync failed (non-fatal): {e}")

    yield  # Application runs here

    # ==================== SHUTDOWN ====================
    logger.info(f"👋 {settings.APP_NAME} shutting down gracefully...")

    # Give existing requests time to complete (grace period)
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=30.0)
        logger.info("🕐 Grace period for active requests completed")
    except asyncio.TimeoutError:
        logger.warning("⏰ Grace period timeout, forcing shutdown")

    # Close database connections
    try:
        await close_db()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database connections: {e}")

    logger.info("🏁 Shutdown complete")


# Create FastAPI application with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Vector-powered tool registry with MCP protocol support",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,  # Add lifespan here
)
```

#### Affected Files

- `app/main.py`

#### Acceptance Criteria

- [ ] `@app.on_event("startup")` decorator is removed
- [ ] `@app.on_event("shutdown")` decorator is removed
- [ ] New `lifespan` async context manager is implemented
- [ ] FastAPI app is initialized with `lifespan` parameter
- [ ] All startup logic executes correctly (database connection, MCP sync)
- [ ] All shutdown logic executes correctly (graceful shutdown, connection cleanup)
- [ ] Application starts and stops without deprecation warnings
- [ ] Existing tests pass
- [ ] Manual testing confirms proper startup/shutdown behavior

#### Testing Steps

1. Start the application and verify startup logs appear
2. Make a health check request to confirm app is running
3. Send SIGTERM and verify graceful shutdown logs appear
4. Verify database connections are closed properly

---

### TICK-002: Fix Readiness Probe HTTP Status Codes

**Priority:** 🔴 High
**Category:** Kubernetes/Operations
**Estimated Effort:** Small
**Breaking Change:** Yes (changes HTTP response codes)

#### Description

The `/ready` endpoint currently returns HTTP 200 even when the service is not ready. Kubernetes readiness probes rely on HTTP status codes to determine if a pod should receive traffic. This can cause traffic to be routed to unhealthy pods.

#### Current State

**File:** `app/main.py` (lines 205-213)

```python
@app.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe for Kubernetes."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "service": settings.APP_NAME}
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        return {"status": "not_ready", "service": settings.APP_NAME}  # Returns 200!
```

#### Proposed Solution

```python
from fastapi import Response, status
from fastapi.responses import JSONResponse

class ReadinessResponse(BaseModel):
    """Response model for readiness check."""
    status: str
    service: str
    error: Optional[str] = None


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"},
    },
)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Readiness probe for Kubernetes.

    Returns:
        200: Service is ready to accept traffic
        503: Service is not ready (database unavailable, etc.)
    """
    try:
        await db.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "service": settings.APP_NAME}
        )
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "service": settings.APP_NAME,
                "error": str(e)
            }
        )
```

#### Affected Files

- `app/main.py`
- `app/schemas/mcp.py` (add ReadinessResponse model)

#### Acceptance Criteria

- [ ] `/ready` returns HTTP 200 when database is available
- [ ] `/ready` returns HTTP 503 when database is unavailable
- [ ] Response body includes status, service name, and error (when applicable)
- [ ] OpenAPI docs show both 200 and 503 response codes
- [ ] Kubernetes readiness probe correctly marks pod as not ready on failure

#### Testing Steps

1. Start application with database running - verify `/ready` returns 200
2. Stop database - verify `/ready` returns 503
3. Restart database - verify `/ready` returns 200 again
4. Test with Kubernetes readiness probe configuration

---

### TICK-003: Add Proper Exception Logging with Stack Traces

**Priority:** 🔴 High
**Category:** Observability/Debugging
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Several places in the codebase log exceptions without stack traces, making debugging difficult. Use `logger.exception()` instead of `logger.error()` when logging caught exceptions.

#### Current State

**File:** `app/execution/executor.py` (lines 167-168)

```python
self.logger.error(
    f"Failed to execute tool '{tool.name}': {error_message}"
)
```

**File:** `app/main.py` (lines 116-117, 124-125, 132-133)

```python
except Exception:
    pass  # Silently swallows ALL errors
```

#### Proposed Solution

**executor.py:**
```python
self.logger.exception(f"Failed to execute tool '{tool.name}'")
# or if you want to include additional context:
self.logger.exception(
    f"Failed to execute tool '{tool.name}' with args: {arguments}"
)
```

**main.py health check:**
```python
# Check database
db_healthy = False
db_error = None
try:
    await db.execute(text("SELECT 1"))
    db_healthy = True
except Exception as e:
    db_error = str(e)
    logger.warning("Database health check failed", exc_info=True)

# Check embedding service
embedding_healthy = False
embedding_error = None
try:
    client = get_embedding_client()
    embedding_healthy = await client.health_check()
except Exception as e:
    embedding_error = str(e)
    logger.warning("Embedding service health check failed", exc_info=True)

# Count indexed tools
indexed_tools = 0
try:
    vector_store = VectorStore(db)
    indexed_tools = await vector_store.count_indexed_tools()
except Exception as e:
    logger.warning("Failed to count indexed tools", exc_info=True)
```

#### Affected Files

- `app/main.py`
- `app/execution/executor.py`
- `app/api/mcp.py`
- `app/api/admin.py`
- `app/mcp_fastmcp_server.py`
- `app/registry/tool_registry.py`

#### Acceptance Criteria

- [ ] All `except Exception` blocks log with stack traces where appropriate
- [ ] Use `logger.exception()` for unexpected errors that need debugging
- [ ] Use `logger.warning(..., exc_info=True)` for expected/handled errors
- [ ] No more bare `except Exception: pass` statements
- [ ] Stack traces appear in logs when errors occur
- [ ] Sensitive information is not logged (passwords, API keys)

#### Testing Steps

1. Trigger an error condition (e.g., invalid tool execution)
2. Check logs for full stack trace
3. Verify stack trace includes file names, line numbers, and call hierarchy

---

## Medium Priority

### TICK-004: Consolidate SSL/TLS Configuration Logic

**Priority:** 🟡 Medium
**Category:** Code Quality/DRY
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

The SSL/TLS certificate verification logic is duplicated 5 times in `executor.py`. This should be consolidated into a reusable utility function.

#### Current State

**File:** `app/execution/executor.py` (repeated at lines 305-309, 454-458, 546-550, 698-702, and more)

```python
tls_cert_path = "/etc/ssl/certs/ca-custom.pem"
if os.path.exists(tls_cert_path):
    verify_ssl = tls_cert_path
else:
    verify_ssl = True
```

#### Proposed Solution

**Create new file:** `app/utils/http.py`

```python
"""HTTP utility functions."""

import os
from functools import lru_cache
from typing import Union

import httpx

# Default custom certificate path for corporate/enterprise environments
DEFAULT_CUSTOM_CERT_PATH = "/etc/ssl/certs/ca-custom.pem"


@lru_cache(maxsize=1)
def get_ssl_verify() -> Union[str, bool]:
    """
    Get SSL verification setting for HTTP clients.

    Returns:
        Path to custom CA certificate if it exists, otherwise True for default verification.

    Note:
        Result is cached since the certificate path doesn't change at runtime.
    """
    if os.path.exists(DEFAULT_CUSTOM_CERT_PATH):
        return DEFAULT_CUSTOM_CERT_PATH
    return True


def create_http_client(
    timeout: float = 30.0,
    **kwargs
) -> httpx.AsyncClient:
    """
    Create an httpx AsyncClient with standard configuration.

    Args:
        timeout: Request timeout in seconds (default: 30.0)
        **kwargs: Additional arguments passed to AsyncClient

    Returns:
        Configured AsyncClient instance

    Usage:
        async with create_http_client() as client:
            response = await client.get("https://example.com")
    """
    return httpx.AsyncClient(
        verify=get_ssl_verify(),
        timeout=httpx.Timeout(timeout),
        **kwargs
    )
```

**Update executor.py:**
```python
from app.utils.http import create_http_client, get_ssl_verify

async def _execute_http_endpoint(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
    """Execute HTTP endpoint implementation."""
    # ... config parsing ...

    async with create_http_client(timeout=30.0) as client:
        response = await client.request(
            method=method,
            url=url,
            json=arguments if method in ["POST", "PUT", "PATCH"] else None,
            params=arguments if method == "GET" else None,
            headers=headers,
        )
        # ... response handling ...
```

#### Affected Files

- Create: `app/utils/http.py`
- Update: `app/execution/executor.py`
- Update: `app/utils/__init__.py` (add export)

#### Acceptance Criteria

- [ ] New `app/utils/http.py` module created
- [ ] `get_ssl_verify()` function implemented with caching
- [ ] `create_http_client()` helper function implemented
- [ ] All 5 duplicate blocks in `executor.py` replaced with utility function
- [ ] SSL verification works correctly with custom certs
- [ ] SSL verification works correctly without custom certs
- [ ] Unit tests for the new utility module

#### Testing Steps

1. Test with custom certificate present
2. Test without custom certificate
3. Verify HTTP requests use correct SSL settings
4. Test caching behavior (function should only check file once)

---

### TICK-005: Migrate to Pydantic v2 model_config

**Priority:** 🟡 Medium
**Category:** Pydantic Best Practices
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Pydantic v2 recommends using `model_config` class variable with `ConfigDict` instead of the inner `Config` class. This ensures forward compatibility and follows current best practices.

#### Current State

**File:** `app/schemas/mcp.py` (lines 30-31)

```python
class ToolSchema(BaseModel):
    """Schema for tool information in MCP responses."""

    id: int
    name: str
    # ...

    class Config:
        from_attributes = True
```

#### Proposed Solution

```python
from pydantic import BaseModel, Field, ConfigDict

class ToolSchema(BaseModel):
    """Schema for tool information in MCP responses."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "calculator:calculate",
                "description": "Perform mathematical calculations",
                "category": "math",
                "tags": ["calculator", "math"],
                "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}},
                "version": "1.0.0",
                "is_active": True
            }
        }
    )

    id: int
    name: str
    description: str
    category: str
    tags: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    version: str = "1.0.0"
    is_active: bool = True
```

#### Affected Files

- `app/schemas/mcp.py`
- Any other schema files using `class Config`

#### Acceptance Criteria

- [ ] All `class Config` inner classes replaced with `model_config`
- [ ] `ConfigDict` imported from pydantic
- [ ] All existing functionality preserved
- [ ] OpenAPI schema generation works correctly
- [ ] Model validation works correctly
- [ ] No deprecation warnings from Pydantic

#### Testing Steps

1. Run existing tests to verify models work
2. Check OpenAPI docs at `/docs` for correct schema
3. Test model validation with valid/invalid data
4. Verify `from_attributes` still works for ORM models

---

### TICK-006: Fix Conditional Imports for OpenTelemetry

**Priority:** 🟡 Medium
**Category:** Code Quality
**Estimated Effort:** Medium
**Breaking Change:** No

#### Description

Module-level conditional imports for OpenTelemetry cause issues with type checkers, IDEs, and make the code harder to test. Refactor to always import but conditionally use.

#### Current State

**File:** `app/api/mcp.py` (lines 17-24)

```python
if settings.OTEL_ENABLED:
    from app.observability import (
        create_span,
        record_search_metrics,
        add_span_attributes,
        add_span_event
    )
```

This pattern is repeated in multiple files.

#### Proposed Solution

**Option 1: Noop implementations (Recommended)**

Update `app/observability/__init__.py` to export functions that check the setting:

```python
"""Observability module with conditional OpenTelemetry support."""

from app.config import settings

if settings.OTEL_ENABLED:
    from app.observability.otel import (
        init_telemetry,
        create_span as _create_span,
        record_search_metrics as _record_search_metrics,
        add_span_attributes as _add_span_attributes,
        add_span_event as _add_span_event,
        record_tool_execution as _record_tool_execution,
        record_registry_operation as _record_registry_operation,
        record_litellm_sync_operation as _record_litellm_sync_operation,
        update_registry_tools_count as _update_registry_tools_count,
    )

    # Re-export with same names
    create_span = _create_span
    record_search_metrics = _record_search_metrics
    add_span_attributes = _add_span_attributes
    add_span_event = _add_span_event
    record_tool_execution = _record_tool_execution
    record_registry_operation = _record_registry_operation
    record_litellm_sync_operation = _record_litellm_sync_operation
    update_registry_tools_count = _update_registry_tools_count
else:
    # Noop implementations when OTEL is disabled
    def init_telemetry(*args, **kwargs):
        """Noop: OpenTelemetry is disabled."""
        pass

    class NoopSpan:
        """Noop span that does nothing."""
        def set_attribute(self, key, value):
            pass
        def end(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def create_span(name: str, attributes: dict = None) -> NoopSpan:
        """Noop: OpenTelemetry is disabled."""
        return NoopSpan()

    def record_search_metrics(*args, **kwargs):
        """Noop: OpenTelemetry is disabled."""
        pass

    def add_span_attributes(attributes: dict):
        """Noop: OpenTelemetry is disabled."""
        pass

    def add_span_event(name: str, attributes: dict = None):
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_tool_execution(*args, **kwargs):
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_registry_operation(*args, **kwargs):
        """Noop: OpenTelemetry is disabled."""
        pass

    def record_litellm_sync_operation(*args, **kwargs):
        """Noop: OpenTelemetry is disabled."""
        pass

    def update_registry_tools_count(*args, **kwargs):
        """Noop: OpenTelemetry is disabled."""
        pass
```

**Then update consumers:**

```python
# app/api/mcp.py
from app.observability import (
    create_span,
    record_search_metrics,
    add_span_attributes,
    add_span_event
)

# No more conditional checks needed!
@router.post("/find_tool")
async def find_tool(request: FindToolRequest, ...) -> FindToolResponse:
    span = create_span(
        name="mcp.find_tool",
        attributes={"query": request.query, ...}
    )

    try:
        # ... search logic ...
        add_span_event("search.completed", {"results_found": len(results)})
    finally:
        span.end()  # Works whether OTEL is enabled or not
```

#### Affected Files

- `app/observability/__init__.py`
- `app/api/mcp.py`
- `app/api/admin.py`
- `app/execution/executor.py`
- `app/main.py`

#### Acceptance Criteria

- [ ] Noop implementations created for all observability functions
- [ ] All conditional imports removed from consumer files
- [ ] All `if settings.OTEL_ENABLED` checks removed from endpoint code
- [ ] Application works correctly with `OTEL_ENABLED=true`
- [ ] Application works correctly with `OTEL_ENABLED=false`
- [ ] Type checkers (mypy) pass without errors
- [ ] IDE autocomplete works correctly

#### Testing Steps

1. Run with `OTEL_ENABLED=false` - verify no errors, noop functions called
2. Run with `OTEL_ENABLED=true` - verify telemetry data collected
3. Run mypy - verify no import errors
4. Test IDE autocomplete on observability functions

---

### TICK-007: Add Database Connection Pool Timeout

**Priority:** 🟡 Medium
**Category:** Database/Performance
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

The database engine is configured with pool size and max overflow, but the `pool_timeout` setting from configuration is not being used. Additionally, `pool_recycle` should be set to prevent stale connections.

#### Current State

**File:** `app/db/session.py` (lines 9-16)

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)
```

**File:** `app/config.py` (lines 33-36)

```python
DB_POOL_SIZE: int = 5
DB_MAX_OVERFLOW: int = 10
DB_POOL_TIMEOUT: int = 30  # This is defined but not used!
```

#### Proposed Solution

```python
# app/db/session.py
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Add this
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
)
```

**Optionally add to config.py:**
```python
# Database
DB_POOL_SIZE: int = 5
DB_MAX_OVERFLOW: int = 10
DB_POOL_TIMEOUT: int = 30
DB_POOL_RECYCLE: int = 3600  # New: seconds before connection is recycled
```

#### Affected Files

- `app/db/session.py`
- `app/config.py` (optional)

#### Acceptance Criteria

- [ ] `pool_timeout` parameter added to engine configuration
- [ ] `pool_recycle` parameter added to engine configuration
- [ ] Application handles connection pool exhaustion gracefully
- [ ] Stale connections are recycled properly
- [ ] Connection acquisition respects timeout setting

#### Testing Steps

1. Set `DB_POOL_SIZE=1` and `DB_MAX_OVERFLOW=0`
2. Make concurrent requests exceeding pool size
3. Verify timeout error after `DB_POOL_TIMEOUT` seconds
4. Test long-running application to verify connection recycling

---

### TICK-008: Improve Health Check Error Handling

**Priority:** 🟡 Medium
**Category:** Observability
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

The health check endpoint silently swallows exceptions without logging or reporting them. This makes it difficult to diagnose why a service is unhealthy.

#### Current State

**File:** `app/main.py` (lines 111-133)

```python
# Check database
db_healthy = False
try:
    await db.execute(text("SELECT 1"))
    db_healthy = True
except Exception:
    pass  # Silently swallowed!

# Check embedding service
embedding_healthy = False
try:
    client = get_embedding_client()
    embedding_healthy = await client.health_check()
except Exception:
    pass  # Silently swallowed!
```

#### Proposed Solution

```python
from typing import Optional
from pydantic import BaseModel

class ComponentHealth(BaseModel):
    """Health status for a single component."""
    healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class DetailedHealthCheckResponse(BaseModel):
    """Detailed health check response with component-level status."""
    status: str  # "healthy", "degraded", "unhealthy"
    service: str
    version: str
    components: Dict[str, ComponentHealth]
    indexed_tools: int


@app.get("/health", response_model=DetailedHealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> DetailedHealthCheckResponse:
    """
    Comprehensive health check endpoint.

    Checks database connectivity, embedding service availability,
    and reports component-level health status.
    """
    import time
    components = {}

    # Check database
    db_start = time.time()
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = ComponentHealth(
            healthy=True,
            latency_ms=round((time.time() - db_start) * 1000, 2)
        )
    except Exception as e:
        logger.warning(f"Database health check failed: {e}", exc_info=True)
        components["database"] = ComponentHealth(
            healthy=False,
            latency_ms=round((time.time() - db_start) * 1000, 2),
            error=str(e)
        )

    # Check embedding service
    embedding_start = time.time()
    try:
        client = get_embedding_client()
        embedding_healthy = await client.health_check()
        components["embedding_service"] = ComponentHealth(
            healthy=embedding_healthy,
            latency_ms=round((time.time() - embedding_start) * 1000, 2),
            error=None if embedding_healthy else "Health check returned False"
        )
    except Exception as e:
        logger.warning(f"Embedding service health check failed: {e}", exc_info=True)
        components["embedding_service"] = ComponentHealth(
            healthy=False,
            latency_ms=round((time.time() - embedding_start) * 1000, 2),
            error=str(e)
        )

    # Count indexed tools
    indexed_tools = 0
    try:
        vector_store = VectorStore(db)
        indexed_tools = await vector_store.count_indexed_tools()
    except Exception as e:
        logger.warning(f"Failed to count indexed tools: {e}", exc_info=True)

    # Determine overall status
    all_healthy = all(c.healthy for c in components.values())
    any_healthy = any(c.healthy for c in components.values())

    if all_healthy:
        status = "healthy"
    elif any_healthy:
        status = "degraded"
    else:
        status = "unhealthy"

    return DetailedHealthCheckResponse(
        status=status,
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        components=components,
        indexed_tools=indexed_tools,
    )
```

#### Affected Files

- `app/main.py`
- `app/schemas/mcp.py` (add new response models)

#### Acceptance Criteria

- [ ] Health check logs warnings for failed components
- [ ] Response includes component-level health status
- [ ] Response includes latency for each component check
- [ ] Response includes error messages for failed components
- [ ] Overall status reflects "healthy", "degraded", or "unhealthy"
- [ ] OpenAPI docs show detailed response schema

#### Testing Steps

1. Test with all components healthy
2. Test with database down
3. Test with embedding service down
4. Test with both down
5. Verify logs contain appropriate warnings

---

## Low Priority

### TICK-009: Add Annotated Type Hints for Dependencies

**Priority:** 🟢 Low
**Category:** Code Quality
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

FastAPI 0.95+ supports `Annotated` type hints for dependencies, which improves code readability and makes dependencies reusable.

#### Current State

**File:** `app/api/admin.py`

```python
async def register_tool(
    request: RegisterToolRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
    api_key: str = Depends(require_auth),
) -> RegisterToolResponse:
```

#### Proposed Solution

```python
from typing import Annotated

# Define reusable dependency types at module level
RegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry)]
AuthDep = Annotated[str, Depends(require_auth)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]

# Use in endpoints
async def register_tool(
    request: RegisterToolRequest,
    registry: RegistryDep,
    api_key: AuthDep,
) -> RegisterToolResponse:
```

#### Affected Files

- `app/api/admin.py`
- `app/api/mcp.py`
- `app/main.py`

#### Acceptance Criteria

- [ ] Common dependencies defined as `Annotated` types
- [ ] All endpoints updated to use annotated dependencies
- [ ] No change in runtime behavior
- [ ] Type checking continues to work

---

### TICK-010: Add __all__ Exports to Modules

**Priority:** 🟢 Low
**Category:** Code Quality
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Add `__all__` to module `__init__.py` files to explicitly define the public API.

#### Proposed Solution

```python
# app/registry/__init__.py
from app.registry.tool_registry import ToolRegistry
from app.registry.vector_store import VectorStore
from app.registry.embedding_client import EmbeddingClient, get_embedding_client

__all__ = [
    "ToolRegistry",
    "VectorStore",
    "EmbeddingClient",
    "get_embedding_client",
]
```

#### Affected Files

- `app/registry/__init__.py`
- `app/api/__init__.py`
- `app/schemas/__init__.py`
- `app/models/__init__.py`
- `app/utils/__init__.py`
- `app/observability/__init__.py`

#### Acceptance Criteria

- [ ] All `__init__.py` files have `__all__` defined
- [ ] Only public APIs are exported
- [ ] `from module import *` works correctly

---

### TICK-011: Fix Optional Type Hints

**Priority:** 🟢 Low
**Category:** Type Safety
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Some function parameters have `None` as default but aren't typed as `Optional`.

#### Current State

**File:** `app/registry/tool_registry.py` (lines 265-272)

```python
async def find_tool(
    self,
    query: str,
    limit: int = None,      # Should be Optional[int]
    threshold: float = None,  # Should be Optional[float]
    category: Optional[str] = None,
    use_hybrid: bool = None,  # Should be Optional[bool]
) -> List[Tuple[Tool, float]]:
```

#### Proposed Solution

```python
from typing import Optional

async def find_tool(
    self,
    query: str,
    limit: Optional[int] = None,
    threshold: Optional[float] = None,
    category: Optional[str] = None,
    use_hybrid: Optional[bool] = None,
) -> list[tuple[Tool, float]]:
```

#### Affected Files

- `app/registry/tool_registry.py`
- Search for other instances with grep: `= None` without `Optional`

#### Acceptance Criteria

- [ ] All parameters with `None` default are typed `Optional[T]`
- [ ] mypy passes without type errors
- [ ] Use Python 3.10+ syntax where possible: `int | None`

---

### TICK-012: Add FastMCP Resources and Prompts

**Priority:** 🟢 Low
**Category:** FastMCP Enhancement
**Estimated Effort:** Medium
**Breaking Change:** No

#### Description

FastMCP supports resources and prompts in addition to tools. Adding these would enhance the MCP server capabilities.

#### Proposed Solution

```python
# app/mcp_fastmcp_server.py

@mcp.resource("tool://{tool_name}")
async def get_tool_resource(tool_name: str) -> str:
    """
    Get tool details as a resource.

    This allows MCP clients to access tool information as resources
    rather than having to call tools.
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        tool = await registry.get_tool_by_name(tool_name)

        if not tool:
            return json.dumps({"error": f"Tool '{tool_name}' not found"})

        return json.dumps({
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "tags": tool.tags or [],
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "version": tool.version,
            "is_active": tool.is_active,
        }, indent=2)


@mcp.resource("tools://list")
async def list_tools_resource() -> str:
    """Get list of all available tools as a resource."""
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        tools = await registry.list_tools(active_only=True, limit=100)

        return json.dumps({
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                }
                for t in tools
            ],
            "total": len(tools),
        }, indent=2)


@mcp.prompt()
def tool_discovery_workflow() -> str:
    """
    Prompt for discovering and using tools in Toolbox.

    Provides guidance on the typical workflow for finding
    and executing tools.
    """
    return """
# Tool Discovery Workflow

To find and use tools in Toolbox, follow these steps:

## 1. Search for Tools
Use `find_tools` with a natural language query:
- "calculate math expressions"
- "get weather information"
- "process text or strings"

## 2. Review Results
Examine the returned tools:
- Check the description to understand what each tool does
- Review the input_schema to see required parameters
- Note the similarity_score to gauge relevance

## 3. Get Detailed Schema
For complex tools, use `get_tool_schema` to see:
- Full input schema with all parameters
- Output schema (what the tool returns)
- Implementation type

## 4. Execute the Tool
Use `call_tool` with:
- The exact tool name (e.g., "calculator:calculate")
- Arguments matching the input schema

## Example Workflow
1. find_tools(query="math calculator")
2. get_tool_schema(tool_name="calculator:calculate")
3. call_tool(tool_name="calculator:calculate", arguments={"expression": "2 + 2"})
"""


@mcp.prompt()
def tool_registration_guide() -> str:
    """Guide for registering new tools via the admin API."""
    return """
# Tool Registration Guide

To register a new tool, send a POST request to `/admin/tools` with:

## Required Fields
- `name`: Unique tool identifier (e.g., "myservice:mytool")
- `description`: Clear description of what the tool does
- `category`: Tool category (e.g., "math", "text", "api")
- `input_schema`: JSON Schema for input validation

## Optional Fields
- `tags`: List of searchable tags
- `output_schema`: JSON Schema for output
- `implementation_type`: How the tool executes
- `implementation_code`: Code or configuration
- `version`: Semantic version (default: "1.0.0")
- `metadata`: Additional key-value data

## Implementation Types
- `python_function`: Module path to Python function
- `http_endpoint`: HTTP API configuration
- `mcp_server`: External MCP server proxy
- `litellm`: LiteLLM gateway integration
"""
```

#### Affected Files

- `app/mcp_fastmcp_server.py`

#### Acceptance Criteria

- [ ] Tool resource endpoint implemented
- [ ] Tools list resource endpoint implemented
- [ ] Discovery workflow prompt added
- [ ] Registration guide prompt added
- [ ] Resources accessible via MCP protocol
- [ ] Prompts accessible via MCP protocol

---

### TICK-013: Add Response Models for Error Cases

**Priority:** 🟢 Low
**Category:** API Documentation
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Add explicit error response models to endpoint decorators for better OpenAPI documentation.

#### Proposed Solution

```python
# app/api/mcp.py

@router.post(
    "/find_tool",
    response_model=FindToolResponse,
    responses={
        200: {"model": FindToolResponse, "description": "Successful search"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Find tools using semantic search",
)
async def find_tool(...):
```

#### Affected Files

- `app/api/mcp.py`
- `app/api/admin.py`
- `app/schemas/mcp.py` (ensure ErrorResponse exists)

#### Acceptance Criteria

- [ ] All endpoints have `responses` parameter defined
- [ ] Error responses documented in OpenAPI
- [ ] Swagger UI shows all possible responses

---

### TICK-014: Add Configuration Validation

**Priority:** 🟢 Low
**Category:** Configuration
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Add Pydantic model validators to ensure configuration values are valid at startup.

#### Proposed Solution

```python
# app/config.py

from pydantic import model_validator

class Settings(BaseSettings):
    # ... existing fields ...

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        """Validate configuration values."""
        # Validate DATABASE_URL
        if not self.DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string "
                "(postgresql:// or postgresql+asyncpg://)"
            )

        # Validate EMBEDDING_ENDPOINT_URL
        if not self.EMBEDDING_ENDPOINT_URL.startswith(("http://", "https://")):
            raise ValueError(
                "EMBEDDING_ENDPOINT_URL must be a valid HTTP(S) URL"
            )

        # Validate EMBEDDING_DIMENSION
        if self.EMBEDDING_DIMENSION <= 0:
            raise ValueError("EMBEDDING_DIMENSION must be positive")

        # Validate pool settings
        if self.DB_POOL_SIZE <= 0:
            raise ValueError("DB_POOL_SIZE must be positive")

        if self.DB_MAX_OVERFLOW < 0:
            raise ValueError("DB_MAX_OVERFLOW cannot be negative")

        return self
```

#### Affected Files

- `app/config.py`

#### Acceptance Criteria

- [ ] Database URL validation added
- [ ] Embedding endpoint URL validation added
- [ ] Numeric settings validation added
- [ ] Invalid configuration fails fast at startup
- [ ] Clear error messages for invalid configuration

---

### TICK-015: Add Input Sanitization for Database Queries

**Priority:** 🟢 Low
**Category:** Security
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Add input sanitization for string parameters used in database queries.

#### Proposed Solution

```python
# app/registry/tool_registry.py

async def get_tool_by_name(self, name: str) -> Optional[Tool]:
    """
    Get tool by name.

    Args:
        name: Tool name to look up (max 255 characters)

    Returns:
        Tool if found, None otherwise
    """
    if not name:
        return None

    # Sanitize input
    name = name.strip()
    if len(name) > 255:
        return None  # Tool names can't be this long

    stmt = select(Tool).where(Tool.name == name)
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()
```

#### Affected Files

- `app/registry/tool_registry.py`

#### Acceptance Criteria

- [ ] Name parameter validated for length
- [ ] Empty/None names handled gracefully
- [ ] Whitespace stripped from inputs
- [ ] No SQL injection possible (already safe via SQLAlchemy)

---

## Future Enhancements

### TICK-016: Add Rate Limiting Middleware

**Priority:** 🔵 Future
**Category:** Security/Performance
**Estimated Effort:** Medium
**Breaking Change:** No

#### Description

Add rate limiting to protect the API from abuse and ensure fair resource usage.

#### Proposed Solution

```python
# app/middleware/rate_limit.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# app/main.py
from app.middleware.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# app/api/mcp.py
@router.post("/call_tool")
@limiter.limit("100/minute")
async def call_tool(request: Request, ...):
```

#### Acceptance Criteria

- [ ] Rate limiting middleware added
- [ ] Configurable limits per endpoint
- [ ] 429 response on limit exceeded
- [ ] Rate limit headers in responses

---

### TICK-017: Create Shared Types Module

**Priority:** 🔵 Future
**Category:** Code Organization
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Create a shared types module to prevent circular imports and improve type safety.

#### Proposed Solution

```python
# app/types.py
from typing import TypeAlias, NewType

ToolId = NewType("ToolId", int)
ExecutionId = NewType("ExecutionId", int)
Embedding: TypeAlias = list[float]
SimilarityScore: TypeAlias = float
```

---

### TICK-018: Add Test Fixtures for Authentication

**Priority:** 🔵 Future
**Category:** Testing
**Estimated Effort:** Small
**Breaking Change:** No

#### Description

Add pytest fixtures for authenticated test clients.

#### Proposed Solution

```python
# tests/conftest.py

@pytest.fixture
async def auth_headers() -> dict:
    """Headers with valid authentication."""
    return {"Authorization": "Bearer test-api-key"}

@pytest.fixture
async def auth_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async client with authentication."""
    async with AsyncClient(
        app=app,
        base_url="http://test",
        headers={"Authorization": "Bearer test-api-key"}
    ) as client:
        yield client
```

---

## Implementation Order

Recommended implementation order based on dependencies and impact:

### Phase 1: Critical Fixes
1. TICK-001: Replace Deprecated FastAPI Lifecycle Events
2. TICK-002: Fix Readiness Probe HTTP Status Codes
3. TICK-003: Add Proper Exception Logging

### Phase 2: Code Quality
4. TICK-004: Consolidate SSL/TLS Configuration
5. TICK-006: Fix Conditional Imports for OpenTelemetry
6. TICK-007: Add Database Connection Pool Timeout
7. TICK-008: Improve Health Check Error Handling

### Phase 3: Modernization
8. TICK-005: Migrate to Pydantic v2 model_config
9. TICK-009: Add Annotated Type Hints
10. TICK-011: Fix Optional Type Hints
11. TICK-010: Add __all__ Exports

### Phase 4: Enhancements
12. TICK-013: Add Response Models for Error Cases
13. TICK-014: Add Configuration Validation
14. TICK-015: Add Input Sanitization
15. TICK-012: Add FastMCP Resources and Prompts

### Phase 5: Future
16. TICK-016: Rate Limiting
17. TICK-017: Shared Types Module
18. TICK-018: Test Fixtures
