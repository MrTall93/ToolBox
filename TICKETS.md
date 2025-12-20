# ToolBox Production Readiness Tickets

> Generated from deep technical review on 2025-12-20
> Total: 18 tickets across Critical, High, Medium, and Low priorities

---

## Table of Contents

1. [Critical Priority](#critical-priority)
   - [TOOL-001: Fix Embedding Dimension Mismatch Between Migration and Model](#tool-001-fix-embedding-dimension-mismatch-between-migration-and-model)
   - [TOOL-002: Fix Batch Embedding Processing Bug](#tool-002-fix-batch-embedding-processing-bug)
   - [TOOL-003: Replace Blocking subprocess.run with Async Implementation](#tool-003-replace-blocking-subprocessrun-with-async-implementation)

2. [High Priority](#high-priority)
   - [TOOL-004: Implement API Rate Limiting](#tool-004-implement-api-rate-limiting)
   - [TOOL-005: Fix API Key Timing Attack Vulnerability](#tool-005-fix-api-key-timing-attack-vulnerability)
   - [TOOL-006: Restrict CORS Origins for Production](#tool-006-restrict-cors-origins-for-production)
   - [TOOL-007: Implement Request Size Limits](#tool-007-implement-request-size-limits)
   - [TOOL-008: Secure Arbitrary Module Import in Python Executor](#tool-008-secure-arbitrary-module-import-in-python-executor)

3. [Medium Priority](#medium-priority)
   - [TOOL-009: Fix Auto-Commit in Database Session Management](#tool-009-fix-auto-commit-in-database-session-management)
   - [TOOL-010: Optimize N+1 Queries in MCP Resources](#tool-010-optimize-n1-queries-in-mcp-resources)
   - [TOOL-011: Externalize Secrets from Kubernetes Manifests](#tool-011-externalize-secrets-from-kubernetes-manifests)
   - [TOOL-012: Fix Graceful Shutdown Logic Bug](#tool-012-fix-graceful-shutdown-logic-bug)
   - [TOOL-013: Add Error Message Sanitization](#tool-013-add-error-message-sanitization)

4. [Low Priority](#low-priority)
   - [TOOL-014: Fix Singleton Race Conditions for Multi-Worker Deployments](#tool-014-fix-singleton-race-conditions-for-multi-worker-deployments)
   - [TOOL-015: Add Embedding Service to Readiness Check](#tool-015-add-embedding-service-to-readiness-check)
   - [TOOL-016: Implement Structured Logging with Correlation IDs](#tool-016-implement-structured-logging-with-correlation-ids)
   - [TOOL-017: Add Retry Logic to MCP Server Discovery](#tool-017-add-retry-logic-to-mcp-server-discovery)
   - [TOOL-018: Fix MCP Resource Return Types](#tool-018-fix-mcp-resource-return-types)

---

# Critical Priority

---

## TOOL-001: Fix Embedding Dimension Mismatch Between Migration and Model

### Priority
**Critical** | **Security Impact**: None | **Data Integrity Impact**: High

### Summary
The Alembic migration hardcodes the embedding vector dimension as 1024, while the SQLAlchemy model uses the configurable `EMBEDDING_DIMENSION` setting (default: 1536). This mismatch causes runtime failures when inserting embeddings.

### Current Behavior
- Migration creates `embedding` column with `Vector(1024)`
- Model expects `Vector(settings.EMBEDDING_DIMENSION)` (1536 by default)
- Attempting to insert a 1536-dimension embedding into a 1024-dimension column fails with a PostgreSQL error

### Expected Behavior
- Migration and model should use the same dimension
- Dimension should be configurable via environment variable
- Existing data should be migrated if dimension changes

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `alembic/versions/20251210_0000_001_initial_schema.py` | 40 | Hardcoded `Vector(1024)` |
| `app/models/tool.py` | 70-72 | Uses `settings.EMBEDDING_DIMENSION` |
| `app/config.py` | 44 | Default `EMBEDDING_DIMENSION = 1536` |

### Acceptance Criteria
- [ ] New migration created to alter embedding column dimension
- [ ] Migration reads dimension from environment variable with sensible default
- [ ] Existing embeddings are handled (either re-generated or dimension validated)
- [ ] CI/CD pipeline includes dimension consistency check
- [ ] Documentation updated with embedding dimension configuration

### Implementation Details

#### Option A: Create New Migration (Recommended for new deployments)

```python
# alembic/versions/YYYYMMDD_fix_embedding_dimension.py
"""Fix embedding dimension mismatch

Revision ID: 002
Revises: 001
"""
import os
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "002"
down_revision = "001"

def upgrade():
    dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    # Drop existing index (required before altering column type)
    op.drop_index("ix_tools_embedding", table_name="tools")

    # Alter column type
    op.execute(f"""
        ALTER TABLE tools
        ALTER COLUMN embedding TYPE vector({dimension})
    """)

    # Recreate index with new dimension
    op.execute(f"""
        CREATE INDEX ix_tools_embedding ON tools
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Clear existing embeddings since dimensions changed
    op.execute("UPDATE tools SET embedding = NULL")

def downgrade():
    # Revert to 1024 (original migration dimension)
    op.drop_index("ix_tools_embedding", table_name="tools")
    op.execute("ALTER TABLE tools ALTER COLUMN embedding TYPE vector(1024)")
    op.execute("""
        CREATE INDEX ix_tools_embedding ON tools
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
```

#### Option B: Fix Original Migration (For fresh deployments only)

```python
# In alembic/versions/20251210_0000_001_initial_schema.py
import os

def upgrade():
    dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    # ... existing code ...

    sa.Column("embedding", Vector(dimension), nullable=True),  # Use variable

    # Update index creation
    op.execute(f"""
        CREATE INDEX ix_tools_embedding ON tools
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
```

### Testing Requirements
- [ ] Unit test: Verify migration applies cleanly with default dimension
- [ ] Unit test: Verify migration applies with custom `EMBEDDING_DIMENSION`
- [ ] Integration test: Insert embedding with configured dimension
- [ ] Integration test: Vector similarity search works after migration
- [ ] Regression test: Existing tools without embeddings remain functional

### Dependencies
- None (can be implemented immediately)

### Rollback Plan
1. Run downgrade migration
2. Clear all embeddings
3. Trigger re-indexing of all tools

### Estimated Effort
**2-4 hours** (including testing)

---

## TOOL-002: Fix Batch Embedding Processing Bug

### Priority
**Critical** | **Performance Impact**: High | **Correctness Impact**: High

### Summary
The `embed_batch` method in `EmbeddingClient` claims to process multiple texts but silently processes only the first text, returning incorrect results for batch operations.

### Current Behavior
```python
# Current buggy implementation
if len(texts) == 1:
    payload = {"input": texts[0], "model": self.model}
else:
    # BUG: Still only processes first text!
    payload = {"input": texts[0], "model": self.model}
```

When called with `["text1", "text2", "text3"]`, only `"text1"` is embedded, and the same embedding is returned for all three.

### Expected Behavior
- All texts in the batch should be processed
- Each text should receive its own unique embedding
- Batch processing should be more efficient than N individual calls

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/registry/embedding_client.py` | 79-89 | Only first text processed |
| `app/registry/embedding_service.py` | 311-341 | Calls buggy `embed_batch` |

### Acceptance Criteria
- [ ] All texts in batch are sent to embedding service
- [ ] Each text receives its own embedding in response
- [ ] Proper handling when embedding service doesn't support batch
- [ ] Fallback to sequential processing if needed
- [ ] Performance improvement measured and documented

### Implementation Details

```python
# app/registry/embedding_client.py

async def embed_batch(self, texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a batch.

    Supports OpenAI-compatible APIs that accept array inputs.
    Falls back to sequential processing if batch fails.
    """
    if not texts:
        return []

    headers = {}
    if self.api_key:
        headers["Authorization"] = f"Bearer {self.api_key}"

    # OpenAI-compatible format supports array input
    payload = {
        "input": texts,  # Send ALL texts as array
        "model": self.model
    }

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        try:
            response = await client.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            # Check if it's a "batch not supported" error
            if self._is_batch_not_supported_error(e):
                return await self._embed_sequential(texts, headers)
            raise

        return self._parse_batch_response(response.json(), texts)

    async def _embed_sequential(
        self,
        texts: List[str],
        headers: dict
    ) -> List[List[float]]:
        """Fallback: Process texts one at a time."""
        embeddings = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                payload = {"input": text, "model": self.model}
                response = await client.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                embedding = self._extract_single_embedding(data)
                embeddings.append(embedding)
        return embeddings

    def _parse_batch_response(
        self,
        data: dict,
        texts: List[str]
    ) -> List[List[float]]:
        """Parse batch response and validate dimensions."""
        # Handle OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
        if "data" in data and isinstance(data["data"], list):
            # Sort by index to ensure correct ordering
            sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
            embeddings = [item["embedding"] for item in sorted_data]
        # Handle alternative formats
        elif "embeddings" in data:
            embeddings = data["embeddings"]
        elif isinstance(data, list):
            embeddings = data
        else:
            raise ValueError(f"Unexpected batch response format: {list(data.keys())}")

        # Validate count matches
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(embeddings)}"
            )

        # Validate dimensions
        for i, embedding in enumerate(embeddings):
            if len(embedding) != self.dimension:
                raise ValueError(
                    f"Embedding {i} has dimension {len(embedding)}, "
                    f"expected {self.dimension}"
                )

        return embeddings

    def _is_batch_not_supported_error(self, error: httpx.HTTPError) -> bool:
        """Check if error indicates batch processing isn't supported."""
        if hasattr(error, 'response') and error.response is not None:
            try:
                data = error.response.json()
                error_msg = str(data.get("error", "")).lower()
                return "batch" in error_msg or "array" in error_msg
            except:
                pass
        return False

    def _extract_single_embedding(self, data: dict) -> List[float]:
        """Extract single embedding from response."""
        if "data" in data and isinstance(data["data"], list):
            return data["data"][0]["embedding"]
        elif "embedding" in data:
            return data["embedding"]
        else:
            raise ValueError(f"Cannot extract embedding from: {data}")
```

### Testing Requirements
- [ ] Unit test: Batch of 1 text returns 1 embedding
- [ ] Unit test: Batch of N texts returns N distinct embeddings
- [ ] Unit test: Empty batch returns empty list
- [ ] Unit test: Sequential fallback works when batch fails
- [ ] Unit test: Dimension validation catches mismatches
- [ ] Integration test: Batch embedding with real embedding service
- [ ] Performance test: Batch is faster than sequential for N > 3

### Test Cases

```python
# tests/test_embedding_client.py

@pytest.mark.asyncio
async def test_embed_batch_processes_all_texts(mock_embedding_service):
    """Verify all texts in batch are processed."""
    client = EmbeddingClient()
    texts = ["hello", "world", "test"]

    embeddings = await client.embed_batch(texts)

    assert len(embeddings) == 3
    # Each should be unique (different texts = different embeddings)
    assert embeddings[0] != embeddings[1]
    assert embeddings[1] != embeddings[2]


@pytest.mark.asyncio
async def test_embed_batch_maintains_order(mock_embedding_service):
    """Verify embedding order matches input order."""
    client = EmbeddingClient()
    texts = ["first", "second", "third"]

    embeddings = await client.embed_batch(texts)

    # Mock should return predictable embeddings based on text
    # Verify order is preserved
    assert mock_embedding_service.call_args_list[0].texts == texts


@pytest.mark.asyncio
async def test_embed_batch_fallback_to_sequential(mock_embedding_service):
    """Verify fallback when batch not supported."""
    mock_embedding_service.configure_batch_not_supported()
    client = EmbeddingClient()
    texts = ["hello", "world"]

    embeddings = await client.embed_batch(texts)

    assert len(embeddings) == 2
    assert mock_embedding_service.sequential_calls == 2
```

### Dependencies
- TOOL-001 (embedding dimension) should be fixed first to ensure tests use correct dimension

### Estimated Effort
**3-4 hours** (implementation + comprehensive testing)

---

## TOOL-003: Replace Blocking subprocess.run with Async Implementation

### Priority
**Critical** | **Performance Impact**: Critical | **Stability Impact**: High

### Summary
The command-line tool executor uses blocking `subprocess.run()` inside an async function, which blocks the entire event loop and can cause request timeouts and degraded performance for all concurrent requests.

### Current Behavior
```python
# BLOCKING CALL - blocks entire event loop!
result = subprocess.run(
    command_parts,
    shell=False,
    capture_output=True,
    text=True,
    cwd=working_dir,
    timeout=timeout
)
```

When a command takes 30 seconds, ALL other requests are blocked for those 30 seconds.

### Expected Behavior
- Command execution should be non-blocking
- Other async operations should continue while command runs
- Timeout handling should be async-compatible
- Process cleanup on timeout should be reliable

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/execution/executor.py` | 398-405 | Blocking `subprocess.run` |

### Acceptance Criteria
- [ ] Command execution uses `asyncio.create_subprocess_exec`
- [ ] Timeout handling uses `asyncio.wait_for`
- [ ] Process is properly killed on timeout
- [ ] stdout/stderr are captured correctly
- [ ] Return code is properly handled
- [ ] No event loop blocking during command execution

### Implementation Details

```python
# app/execution/executor.py

async def _execute_command_line(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
    """
    Execute command line implementation safely using async subprocess.

    Uses asyncio subprocess to avoid blocking the event loop.
    """
    if not tool.implementation_code:
        raise ValueError("Command configuration is empty")

    try:
        # Parse command configuration
        if isinstance(tool.implementation_code, dict):
            config = tool.implementation_code
        elif isinstance(tool.implementation_code, str):
            config = json.loads(tool.implementation_code)
        else:
            raise ValueError(f"Invalid implementation_code type: {type(tool.implementation_code)}")

        command_template = config.get("command")
        working_dir = config.get("working_dir")
        timeout = config.get("timeout", 30)
        allowed_commands = config.get("allowed_commands", [])
        env_vars = config.get("env", None)

        if not command_template:
            raise ValueError("Command template is required")

        # Sanitize arguments (existing logic)
        sanitized_args = self._sanitize_command_arguments(arguments)

        # Format command with sanitized arguments
        try:
            command_str = command_template.format(**sanitized_args)
        except KeyError as e:
            raise ValueError(f"Missing required argument: {e}")

        # Parse command into list using shlex
        try:
            command_parts = shlex.split(command_str)
        except ValueError as e:
            raise ValueError(f"Invalid command format: {e}")

        if not command_parts:
            raise ValueError("Command cannot be empty")

        # Validate against allowed commands whitelist
        executable = command_parts[0]
        if allowed_commands and executable not in allowed_commands:
            raise ValueError(
                f"Command '{executable}' is not in the allowed commands list"
            )

        # Prepare environment
        process_env = os.environ.copy()
        if env_vars:
            process_env.update(env_vars)

        # Create async subprocess
        process = await asyncio.create_subprocess_exec(
            *command_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
            env=process_env,
        )

        try:
            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill process on timeout
            try:
                process.kill()
                await process.wait()  # Ensure process is cleaned up
            except ProcessLookupError:
                pass  # Process already terminated
            raise RuntimeError(f"Command timed out after {timeout} seconds")

        # Decode output
        stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
        stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

        if process.returncode != 0:
            raise RuntimeError(
                f"Command failed with exit code {process.returncode}: {stderr_str}"
            )

        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "return_code": process.returncode
        }

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid command configuration JSON: {str(e)}")
    except asyncio.CancelledError:
        # Handle task cancellation gracefully
        if 'process' in locals() and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        raise
    except Exception as e:
        if not isinstance(e, RuntimeError):
            raise RuntimeError(f"Command execution failed: {str(e)}")
        raise

def _sanitize_command_arguments(
    self,
    arguments: Dict[str, Any]
) -> Dict[str, str]:
    """Sanitize command arguments to prevent injection."""
    sanitized = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            # Reject arguments containing shell metacharacters
            if re.search(r'[;&|`$(){}[\]<>\\\'"]', value):
                raise ValueError(
                    f"Argument '{key}' contains disallowed shell characters"
                )
            sanitized[key] = value
        elif isinstance(value, (int, float, bool)):
            sanitized[key] = str(value)
        else:
            raise ValueError(
                f"Argument '{key}' must be a string, number, or boolean"
            )
    return sanitized
```

### Testing Requirements
- [ ] Unit test: Command executes without blocking event loop
- [ ] Unit test: Timeout kills process and returns error
- [ ] Unit test: Non-zero exit code raises RuntimeError
- [ ] Unit test: stdout/stderr captured correctly
- [ ] Unit test: Unicode output handled properly
- [ ] Integration test: Concurrent commands don't block each other
- [ ] Load test: Multiple simultaneous command executions

### Test Cases

```python
# tests/test_executor_async.py

@pytest.mark.asyncio
async def test_command_does_not_block_event_loop():
    """Verify other tasks can run during command execution."""
    executor = ToolExecutor()
    tool = create_tool_with_command("sleep 2")  # 2-second command

    start = time.time()

    # Start command and a fast task concurrently
    async def fast_task():
        await asyncio.sleep(0.1)
        return "fast_done"

    command_task = asyncio.create_task(
        executor._execute_command_line(tool, {})
    )
    fast_result = await fast_task()

    # Fast task should complete in ~0.1s, not wait 2s
    assert fast_result == "fast_done"
    assert time.time() - start < 0.5

    # Clean up
    command_task.cancel()


@pytest.mark.asyncio
async def test_command_timeout_kills_process():
    """Verify process is killed on timeout."""
    executor = ToolExecutor()
    tool = create_tool_with_command(
        "sleep 60",  # Would run for 60s
        timeout=1    # But timeout at 1s
    )

    with pytest.raises(RuntimeError, match="timed out"):
        await executor._execute_command_line(tool, {})


@pytest.mark.asyncio
async def test_concurrent_commands():
    """Verify multiple commands can run concurrently."""
    executor = ToolExecutor()
    tool1 = create_tool_with_command("sleep 1 && echo done1")
    tool2 = create_tool_with_command("sleep 1 && echo done2")

    start = time.time()
    results = await asyncio.gather(
        executor._execute_command_line(tool1, {}),
        executor._execute_command_line(tool2, {}),
    )
    elapsed = time.time() - start

    # Both should complete in ~1s, not 2s (sequential)
    assert elapsed < 1.5
    assert "done1" in results[0]["stdout"]
    assert "done2" in results[1]["stdout"]
```

### Dependencies
- None

### Rollback Plan
If issues are discovered:
1. Revert to blocking implementation
2. Add warning log when command execution starts
3. Reduce default timeout

### Estimated Effort
**2-3 hours** (straightforward replacement with testing)

---

# High Priority

---

## TOOL-004: Implement API Rate Limiting

### Priority
**High** | **Security Impact**: High | **Stability Impact**: High

### Summary
The API has no rate limiting, making it vulnerable to denial-of-service attacks and resource exhaustion. A malicious or buggy client could overwhelm the service with requests.

### Current Behavior
- No rate limiting on any endpoint
- Unlimited requests per client
- No protection against abuse

### Expected Behavior
- Configurable rate limits per endpoint category
- Rate limit headers in responses
- 429 Too Many Requests response when limits exceeded
- Different limits for authenticated vs unauthenticated requests
- Rate limit bypass for health checks

### Affected Files
| File | Action |
|------|--------|
| `app/main.py` | Add rate limiting middleware |
| `app/config.py` | Add rate limit configuration |
| `app/middleware/rate_limit.py` | New file |

### Acceptance Criteria
- [ ] Rate limiting middleware implemented
- [ ] Configurable limits via environment variables
- [ ] Rate limit headers (X-RateLimit-*) in responses
- [ ] 429 response with Retry-After header
- [ ] Health/readiness endpoints exempt from limits
- [ ] Redis backend for distributed rate limiting (optional)
- [ ] Metrics for rate limit hits

### Implementation Details

```python
# app/config.py - Add configuration

class Settings(BaseSettings):
    # ... existing settings ...

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_BURST: int = 10  # Allow burst above limit
    RATE_LIMIT_REDIS_URL: str | None = None  # For distributed limiting


# app/middleware/rate_limit.py - New file

import time
from collections import defaultdict
from typing import Dict, Optional, Tuple
import asyncio
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class InMemoryRateLimiter:
    """Simple in-memory rate limiter using token bucket algorithm."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.tokens: Dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: Dict[str, float] = defaultdict(time.time)
        self._lock = asyncio.Lock()

        # Token refill rate (tokens per second)
        self.refill_rate = requests_per_minute / 60.0

    async def is_allowed(self, key: str) -> Tuple[bool, Dict[str, str]]:
        """
        Check if request is allowed and return rate limit headers.

        Returns:
            Tuple of (is_allowed, headers_dict)
        """
        async with self._lock:
            now = time.time()
            time_passed = now - self.last_update[key]
            self.last_update[key] = now

            # Refill tokens
            self.tokens[key] = min(
                self.burst,
                self.tokens[key] + time_passed * self.refill_rate
            )

            # Calculate headers
            remaining = int(self.tokens[key])
            reset_time = int(now + (self.burst - self.tokens[key]) / self.refill_rate)

            headers = {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": str(max(0, remaining - 1)),
                "X-RateLimit-Reset": str(reset_time),
            }

            if self.tokens[key] >= 1:
                self.tokens[key] -= 1
                return True, headers
            else:
                headers["Retry-After"] = str(int(1 / self.refill_rate))
                return False, headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI."""

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {
        "/health",
        "/health/detailed",
        "/ready",
        "/live",
        "/metrics",
    }

    def __init__(self, app, limiter: Optional[InMemoryRateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter(
            requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
            burst=settings.RATE_LIMIT_BURST,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip if rate limiting disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get client identifier
        client_key = self._get_client_key(request)

        # Check rate limit
        is_allowed, headers = await self.limiter.is_allowed(client_key)

        if not is_allowed:
            response = Response(
                content='{"error": "rate_limit_exceeded", "message": "Too many requests"}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )
            for key, value in headers.items():
                response.headers[key] = value
            return response

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier for rate limiting."""
        # Use API key if present
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return f"api_key:{auth_header[7:][:16]}"  # First 16 chars of key

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"


# app/main.py - Add middleware

from app.middleware.rate_limit import RateLimitMiddleware

# After CORS middleware
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)
```

### Testing Requirements
- [ ] Unit test: Requests within limit succeed
- [ ] Unit test: Requests exceeding limit get 429
- [ ] Unit test: Rate limit headers present in response
- [ ] Unit test: Retry-After header on 429
- [ ] Unit test: Exempt paths not rate limited
- [ ] Unit test: Token bucket refills over time
- [ ] Load test: Verify rate limiting under high load

### Dependencies
- None (in-memory implementation)
- Optional: Redis for distributed deployments

### Estimated Effort
**4-6 hours** (including Redis support for production)

---

## TOOL-005: Fix API Key Timing Attack Vulnerability

### Priority
**High** | **Security Impact**: High

### Summary
The API key comparison uses standard string equality (`!=`), which is vulnerable to timing attacks. An attacker could potentially discover the API key character by character by measuring response times.

### Current Behavior
```python
if credentials.credentials != settings.API_KEY:  # Vulnerable!
    raise HTTPException(...)
```

String comparison in Python short-circuits, meaning it returns immediately when a mismatch is found. This creates measurable timing differences.

### Expected Behavior
- Use constant-time comparison for API keys
- Response time should be independent of which character mismatches
- No information leakage through timing

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/middleware/auth.py` | 40-46 | String comparison timing attack |

### Acceptance Criteria
- [ ] Use `secrets.compare_digest()` for API key comparison
- [ ] Response time is constant regardless of input
- [ ] All authentication checks use timing-safe comparison

### Implementation Details

```python
# app/middleware/auth.py

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[str]:
    """
    Verify API key if configured, otherwise allow requests.

    Uses constant-time comparison to prevent timing attacks.
    """
    # If no API key configured, allow all requests
    if not settings.API_KEY:
        return None

    # If API key is configured but no credentials provided
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use timing-safe comparison to prevent timing attacks
    # Both values must be the same type and encoding
    provided_key = credentials.credentials.encode('utf-8')
    expected_key = settings.API_KEY.encode('utf-8')

    if not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


def require_auth(
    credentials: Optional[str] = Depends(verify_api_key)
) -> Optional[str]:
    """Dependency wrapper for authentication."""
    return credentials
```

### Testing Requirements
- [ ] Unit test: Valid API key succeeds
- [ ] Unit test: Invalid API key returns 403
- [ ] Unit test: Missing API key returns 401
- [ ] Security test: Timing consistency (optional but recommended)

### Test Case for Timing (Optional)

```python
# tests/test_auth_timing.py

import time
import statistics

@pytest.mark.security
async def test_api_key_comparison_timing_consistency():
    """
    Verify API key comparison has consistent timing.

    Note: This test is probabilistic and may have false positives.
    Run multiple times to verify.
    """
    from app.middleware.auth import verify_api_key

    # Mock credentials with different similarity to actual key
    test_keys = [
        "completely_wrong_key_here",  # 0% match
        settings.API_KEY[:5] + "wrong" + settings.API_KEY[10:],  # Partial match
        settings.API_KEY[:-1] + "X",  # Off by one at end
        "X" + settings.API_KEY[1:],  # Off by one at start
    ]

    timings = {}
    iterations = 100

    for key in test_keys:
        times = []
        for _ in range(iterations):
            mock_creds = MockCredentials(key)
            start = time.perf_counter()
            try:
                await verify_api_key(mock_creds)
            except HTTPException:
                pass
            times.append(time.perf_counter() - start)

        timings[key] = statistics.mean(times)

    # All timings should be within 10% of each other
    mean_time = statistics.mean(timings.values())
    for key, timing in timings.items():
        assert abs(timing - mean_time) / mean_time < 0.1, \
            f"Timing variance too high for key pattern"
```

### Dependencies
- None

### Estimated Effort
**30 minutes** (simple but critical fix)

---

## TOOL-006: Restrict CORS Origins for Production

### Priority
**High** | **Security Impact**: High

### Summary
The FastMCP server uses wildcard CORS (`allow_origins=["*"]`), allowing any website to make requests. This could enable CSRF attacks or data exfiltration.

### Current Behavior
```python
# mcp_fastmcp_server.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows any origin
    allow_credentials=True,  # Dangerous with wildcard!
    ...
)
```

Note: `allow_credentials=True` with `allow_origins=["*"]` is particularly dangerous.

### Expected Behavior
- CORS origins should be explicitly configured
- Different configurations for development vs production
- MCP Inspector origin should be whitelisted
- No wildcard with credentials

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/mcp_fastmcp_server.py` | 607-614 | Wildcard CORS |
| `app/main.py` | 133-139 | Uses settings (good) |
| `app/config.py` | 61-64 | CORS_ORIGINS setting |

### Acceptance Criteria
- [ ] FastMCP uses same CORS settings as main app
- [ ] Production deployments have explicit origin list
- [ ] Development can use permissive settings
- [ ] Warning logged if wildcard CORS used
- [ ] `allow_credentials` is False when using wildcard

### Implementation Details

```python
# app/mcp_fastmcp_server.py

# At module level, after imports
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# In __main__ block:
if __name__ == "__main__":
    # ... existing code ...

    # Validate CORS configuration
    cors_origins = settings.CORS_ORIGINS
    allow_credentials = True

    if "*" in cors_origins or cors_origins == ["*"]:
        logger.warning(
            "CORS wildcard origin detected. This is insecure for production. "
            "Set CORS_ORIGINS to specific origins."
        )
        # Don't allow credentials with wildcard
        allow_credentials = False
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],  # Restrict methods
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id", "X-Request-Id"],
    )


# app/config.py - Add production validation

class Settings(BaseSettings):
    # ... existing ...

    ENVIRONMENT: str = Field(
        default="development",
        description="Environment: development, staging, production"
    )

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_for_production(cls, v, info):
        """Warn about insecure CORS in production."""
        # Access other field values through info.data
        env = info.data.get("ENVIRONMENT", "development")

        if env == "production" and ("*" in v or v == ["*"]):
            import warnings
            warnings.warn(
                "Wildcard CORS origin in production environment is insecure. "
                "Configure explicit origins via CORS_ORIGINS.",
                SecurityWarning
            )
        return v
```

### Environment Configuration

```bash
# Development (.env.development)
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080","http://127.0.0.1:5173"]

# Production (.env.production)
CORS_ORIGINS=["https://your-app.example.com","https://admin.example.com"]
ENVIRONMENT=production
```

### Testing Requirements
- [ ] Unit test: Configured origins are allowed
- [ ] Unit test: Non-configured origins are blocked
- [ ] Unit test: Warning logged for wildcard in production
- [ ] Unit test: Credentials disabled with wildcard
- [ ] Integration test: MCP Inspector can connect with proper CORS

### Dependencies
- None

### Estimated Effort
**1-2 hours**

---

## TOOL-007: Implement Request Size Limits

### Priority
**High** | **Stability Impact**: High | **Security Impact**: Medium

### Summary
No request body size limits are configured, allowing clients to send arbitrarily large payloads. This could cause memory exhaustion, slow processing, or denial of service.

### Current Behavior
- No size limits on request bodies
- Large JSON payloads accepted without validation
- Potential for memory exhaustion with large embeddings/schemas

### Expected Behavior
- Configurable maximum request body size
- 413 Payload Too Large response for oversized requests
- Specific limits for different content types
- Streaming handled appropriately

### Affected Files
| File | Action |
|------|--------|
| `app/main.py` | Add size limit middleware |
| `app/config.py` | Add size limit configuration |
| `app/mcp_fastmcp_server.py` | Add size limits |

### Acceptance Criteria
- [ ] Global request body size limit (default 10MB)
- [ ] Specific limits for tool registration (larger for schemas)
- [ ] 413 response with clear error message
- [ ] Configuration via environment variable
- [ ] Metrics for rejected requests

### Implementation Details

```python
# app/config.py

class Settings(BaseSettings):
    # ... existing ...

    # Request Size Limits (in bytes)
    MAX_REQUEST_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum request body size in bytes"
    )
    MAX_TOOL_REGISTRATION_SIZE: int = Field(
        default=1 * 1024 * 1024,  # 1MB
        description="Maximum size for tool registration requests"
    )


# app/middleware/size_limit.py - New file

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request body size limits."""

    # Path-specific limits (path prefix -> max bytes)
    PATH_LIMITS = {
        "/admin/tools": settings.MAX_TOOL_REGISTRATION_SIZE,
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("content-length")

        if content_length:
            content_length = int(content_length)

            # Get path-specific limit or default
            max_size = self._get_limit_for_path(request.url.path)

            if content_length > max_size:
                return Response(
                    content=f'{{"error": "payload_too_large", "message": "Request body exceeds {max_size} bytes", "max_size": {max_size}}}',
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    media_type="application/json",
                )

        return await call_next(request)

    def _get_limit_for_path(self, path: str) -> int:
        """Get size limit for specific path."""
        for prefix, limit in self.PATH_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return settings.MAX_REQUEST_SIZE


# app/main.py

from app.middleware.size_limit import RequestSizeLimitMiddleware

# Add before other middleware
app.add_middleware(RequestSizeLimitMiddleware)
```

### Testing Requirements
- [ ] Unit test: Request under limit succeeds
- [ ] Unit test: Request over limit returns 413
- [ ] Unit test: Path-specific limits applied correctly
- [ ] Unit test: Missing Content-Length allowed (for streaming)
- [ ] Load test: Large request rejection is fast

### Dependencies
- None

### Estimated Effort
**2-3 hours**

---

## TOOL-008: Secure Arbitrary Module Import in Python Executor

### Priority
**High** | **Security Impact**: Critical

### Summary
The Python code executor uses `importlib.import_module` with user-provided module paths, allowing execution of arbitrary code from any installed Python module. While regex-validated, this is still a significant security risk.

### Current Behavior
```python
# User provides: "app.tools.implementations.calculator.execute"
module_path, function_name = implementation_code.rsplit('.', 1)
module = importlib.import_module(module_path)  # Imports ANY module
func = getattr(module, function_name)
result = func(arguments)  # Executes arbitrary code
```

An attacker could register a tool with `implementation_code="os.system"` and execute shell commands.

### Expected Behavior
- Whitelist of allowed module prefixes
- Explicit registration of callable tools
- Sandbox or container-based execution for untrusted code
- Audit logging for all code execution

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/execution/executor.py` | 235-278 | Arbitrary module import |

### Acceptance Criteria
- [ ] Only whitelisted module prefixes allowed
- [ ] Registered functions validated at registration time
- [ ] Audit logging for all executions
- [ ] Option to disable Python code execution entirely
- [ ] Documentation of security model

### Implementation Details

```python
# app/config.py

class Settings(BaseSettings):
    # ... existing ...

    # Python Executor Security
    PYTHON_EXECUTOR_ENABLED: bool = Field(
        default=True,
        description="Enable Python code execution (disable for maximum security)"
    )
    PYTHON_EXECUTOR_ALLOWED_MODULES: list[str] = Field(
        default=["app.tools.implementations"],
        description="Allowed module prefixes for Python executor"
    )


# app/execution/executor.py

async def _execute_python_code(self, tool: Tool, arguments: Dict[str, Any]) -> Any:
    """
    Execute Python code implementation with security restrictions.

    Only allows importing from whitelisted module prefixes.
    """
    if not settings.PYTHON_EXECUTOR_ENABLED:
        raise RuntimeError(
            "Python code execution is disabled. "
            "Set PYTHON_EXECUTOR_ENABLED=true to enable."
        )

    if not tool.implementation_code:
        raise ValueError("Python code implementation is empty")

    implementation_code = tool.implementation_code.strip()

    # Validate format
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$', implementation_code):
        raise ValueError(
            "Implementation code must be a valid module path "
            "(e.g., 'app.tools.implementations.calculator.execute')"
        )

    # Security: Check against whitelist
    module_path, function_name = implementation_code.rsplit('.', 1)

    is_allowed = any(
        module_path.startswith(allowed_prefix)
        for allowed_prefix in settings.PYTHON_EXECUTOR_ALLOWED_MODULES
    )

    if not is_allowed:
        self.logger.warning(
            f"Blocked execution of non-whitelisted module: {module_path}",
            extra={
                "tool_name": tool.name,
                "module_path": module_path,
                "allowed_prefixes": settings.PYTHON_EXECUTOR_ALLOWED_MODULES,
            }
        )
        raise ValueError(
            f"Module '{module_path}' is not in the allowed modules list. "
            f"Allowed prefixes: {settings.PYTHON_EXECUTOR_ALLOWED_MODULES}"
        )

    # Additional blocklist check
    BLOCKED_MODULES = {
        "os", "sys", "subprocess", "shutil", "socket", "http",
        "ftplib", "smtplib", "telnetlib", "pickle", "marshal",
        "builtins", "__builtins__", "importlib", "code", "codeop",
    }

    module_parts = module_path.split('.')
    if any(part in BLOCKED_MODULES for part in module_parts):
        self.logger.warning(
            f"Blocked execution of dangerous module: {module_path}",
            extra={"tool_name": tool.name}
        )
        raise ValueError(f"Module '{module_path}' is blocked for security reasons")

    try:
        # Audit log
        self.logger.info(
            f"Executing Python function: {implementation_code}",
            extra={
                "tool_id": tool.id,
                "tool_name": tool.name,
                "module_path": module_path,
                "function_name": function_name,
            }
        )

        module = importlib.import_module(module_path)

        if not hasattr(module, function_name):
            raise ValueError(f"Function '{function_name}' not found in module '{module_path}'")

        func = getattr(module, function_name)

        if not callable(func):
            raise ValueError(f"'{implementation_code}' is not callable")

        # Execute with timeout (if needed)
        result = func(arguments)
        return result

    except ImportError as e:
        raise RuntimeError(f"Failed to import module: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Python code execution failed: {str(e)}")
```

### Testing Requirements
- [ ] Unit test: Whitelisted module executes successfully
- [ ] Unit test: Non-whitelisted module blocked with error
- [ ] Unit test: Blocked module names rejected
- [ ] Unit test: Audit log entries created
- [ ] Security test: Cannot import os, subprocess, etc.

### Dependencies
- None

### Estimated Effort
**3-4 hours**

---

# Medium Priority

---

## TOOL-009: Fix Auto-Commit in Database Session Management

### Priority
**Medium** | **Data Integrity Impact**: Medium

### Summary
The `get_db` dependency auto-commits after every request, which can lead to partial commits if an operation fails mid-way through multiple database calls.

### Current Behavior
```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Auto-commits everything
        except Exception:
            await session.rollback()
            raise
```

If an endpoint does: 1) Create tool, 2) Generate embedding, 3) Update tool with embedding, and step 3 fails, step 1 is still committed.

### Expected Behavior
- Remove auto-commit from session dependency
- Operations explicitly manage their own transactions
- All-or-nothing transaction semantics

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/db/session.py` | 33-50 | Auto-commit in get_db |
| `app/registry/tool_registry.py` | Multiple | Needs explicit transactions |

### Acceptance Criteria
- [ ] `get_db` does not auto-commit
- [ ] Critical operations wrapped in explicit transactions
- [ ] Tests verify rollback on failure
- [ ] No partial state from failed operations

### Implementation Details

```python
# app/db/session.py

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get database session.

    NOTE: This does NOT auto-commit. Operations must explicitly
    commit their transactions when appropriate.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# app/registry/tool_registry.py

async def register_tool(self, ...) -> Tool:
    """Register a new tool with explicit transaction management."""
    async with self.session.begin():  # Explicit transaction
        # Validation...

        tool = Tool(...)
        self.session.add(tool)
        await self.session.flush()  # Get ID

        if auto_embed:
            await self.update_tool_embedding(tool.id)

        # Transaction commits here on success

    await self.session.refresh(tool)
    return tool
```

### Testing Requirements
- [ ] Unit test: Failed operation rolls back all changes
- [ ] Unit test: Successful operation commits all changes
- [ ] Integration test: Concurrent operations don't interfere

### Dependencies
- None

### Estimated Effort
**3-4 hours** (requires auditing all database operations)

---

## TOOL-010: Optimize N+1 Queries in MCP Resources

### Priority
**Medium** | **Performance Impact**: Medium

### Summary
MCP resources load entire tool collections into memory to compute simple aggregates like categories and stats. This is inefficient and won't scale.

### Current Behavior
```python
# Loads ALL 1000 tools to get unique categories
tools = await registry.list_tools(active_only=True, limit=1000)
categories = sorted(set(tool.category for tool in tools))

# Loads ALL 10000 tools for stats
all_tools = await registry.list_tools(active_only=False, limit=10000)
```

### Expected Behavior
- Use SQL aggregates (`DISTINCT`, `COUNT`, `GROUP BY`)
- No full table scans for simple queries
- Pagination for large result sets

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/mcp_fastmcp_server.py` | 426-434 | Loads all tools for categories |
| `app/mcp_fastmcp_server.py` | 447-468 | Loads all tools for stats |

### Acceptance Criteria
- [ ] Categories query uses `SELECT DISTINCT`
- [ ] Stats query uses `COUNT` and `GROUP BY`
- [ ] Response time < 100ms for both
- [ ] No full table loads

### Implementation Details

```python
# app/registry/tool_registry.py

async def get_distinct_categories(self, active_only: bool = True) -> List[str]:
    """Get unique categories efficiently."""
    from sqlalchemy import distinct

    stmt = select(distinct(Tool.category))
    if active_only:
        stmt = stmt.where(Tool.is_active == True)
    stmt = stmt.order_by(Tool.category)

    result = await self.session.execute(stmt)
    return [row[0] for row in result.fetchall() if row[0]]


async def get_registry_stats(self) -> Dict[str, Any]:
    """Get registry statistics efficiently."""
    from sqlalchemy import func, case

    # Single query for all stats
    stmt = select(
        func.count(Tool.id).label("total"),
        func.count(case((Tool.is_active == True, 1))).label("active"),
        func.count(case((Tool.is_active == False, 1))).label("inactive"),
    )

    result = await self.session.execute(stmt)
    row = result.one()

    # Get counts by category
    category_stmt = select(
        Tool.category,
        func.count(Tool.id)
    ).where(
        Tool.is_active == True
    ).group_by(Tool.category)

    category_result = await self.session.execute(category_stmt)
    categories = {row[0]: row[1] for row in category_result.fetchall()}

    # Get counts by implementation type
    impl_stmt = select(
        Tool.implementation_type,
        func.count(Tool.id)
    ).where(
        Tool.is_active == True
    ).group_by(Tool.implementation_type)

    impl_result = await self.session.execute(impl_stmt)
    impl_types = {row[0]: row[1] for row in impl_result.fetchall()}

    return {
        "total_tools": row.total,
        "active_tools": row.active,
        "inactive_tools": row.inactive,
        "tools_by_category": categories,
        "tools_by_implementation_type": impl_types,
    }


# app/mcp_fastmcp_server.py

@mcp.resource("toolbox://categories")
async def get_categories() -> str:
    """Get all available tool categories efficiently."""
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        try:
            categories = await registry.get_distinct_categories()
            return json.dumps({
                "categories": categories,
                "total": len(categories),
            }, indent=2)
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return json.dumps({"error": str(e), "categories": []})
```

### Testing Requirements
- [ ] Unit test: Categories query is single SELECT
- [ ] Unit test: Stats query uses aggregates
- [ ] Performance test: < 100ms with 10k tools
- [ ] Integration test: Results match full scan results

### Dependencies
- None

### Estimated Effort
**2-3 hours**

---

## TOOL-011: Externalize Secrets from Kubernetes Manifests

### Priority
**Medium** | **Security Impact**: Medium

### Summary
Kubernetes deployment manifests contain hardcoded secrets (even if marked as dev-only). These could accidentally be promoted to production or committed to public repositories.

### Current Behavior
```yaml
# k8s/toolbox/deployment.yaml
- name: SECRET_KEY
  value: "test-secret-key-for-development-only"
- name: DATABASE_URL
  value: "postgresql+asyncpg://toolregistry:devpassword@postgres:5432/toolregistry"
```

### Expected Behavior
- All secrets in Kubernetes Secrets resources
- Development secrets clearly separated
- Production uses external secret management
- No hardcoded passwords in manifests

### Affected Files
| File | Issue |
|------|-------|
| `k8s/toolbox/deployment.yaml` | Hardcoded secrets |
| `k8s/postgres/secret.yaml` | May need review |

### Acceptance Criteria
- [ ] All sensitive values moved to Secrets
- [ ] Secrets referenced via `secretKeyRef`
- [ ] README documents secret creation
- [ ] Helm chart supports external secrets
- [ ] No passwords in git history going forward

### Implementation Details

```yaml
# k8s/toolbox/secret.yaml (new file, NOT committed to git)
apiVersion: v1
kind: Secret
metadata:
  name: toolbox-secrets
  namespace: toolbox
type: Opaque
stringData:
  database-url: "postgresql+asyncpg://toolregistry:SECURE_PASSWORD@postgres:5432/toolregistry"
  secret-key: "GENERATE_SECURE_RANDOM_KEY"
  api-key: "YOUR_API_KEY"
  embedding-api-key: "YOUR_EMBEDDING_API_KEY"
  honeycomb-team: "YOUR_HONEYCOMB_TEAM"

---

# k8s/toolbox/deployment.yaml (updated)
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: toolbox-secrets
        key: database-url
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: toolbox-secrets
        key: secret-key
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: toolbox-secrets
        key: api-key
        optional: true
  - name: EMBEDDING_API_KEY
    valueFrom:
      secretKeyRef:
        name: toolbox-secrets
        key: embedding-api-key
        optional: true
```

```bash
# scripts/create-secrets.sh (development helper)
#!/bin/bash
set -e

NAMESPACE="${1:-toolbox}"
SECRET_NAME="toolbox-secrets"

# Generate secure random values
SECRET_KEY=$(openssl rand -hex 32)
API_KEY=$(openssl rand -hex 16)

kubectl create secret generic $SECRET_NAME \
  --namespace=$NAMESPACE \
  --from-literal=database-url="postgresql+asyncpg://toolregistry:devpassword@postgres:5432/toolregistry" \
  --from-literal=secret-key="$SECRET_KEY" \
  --from-literal=api-key="$API_KEY" \
  --from-literal=embedding-api-key="" \
  --from-literal=honeycomb-team="" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets created in namespace: $NAMESPACE"
echo "API Key: $API_KEY"
```

### Testing Requirements
- [ ] Deployment works with secret references
- [ ] Missing secrets handled gracefully (optional fields)
- [ ] Script creates valid secrets
- [ ] Documentation is complete

### Dependencies
- None

### Estimated Effort
**2-3 hours**

---

## TOOL-012: Fix Graceful Shutdown Logic Bug

### Priority
**Medium** | **Stability Impact**: Low

### Summary
The graceful shutdown logic waits for `shutdown_event` to be set during shutdown, but this event is already set by the signal handler that triggered the shutdown. The logic always times out.

### Current Behavior
```python
# Signal handler sets the event
def handle_signal(signum: int, frame) -> None:
    shutdown_event.set()  # Event is set here

# In lifespan (during shutdown):
try:
    await asyncio.wait_for(shutdown_event.wait(), timeout=30.0)
    # BUG: Event was already set, so this returns immediately
    # OR if not set (shouldn't happen), times out
```

### Expected Behavior
- Track active requests/connections
- Wait for in-flight requests to complete
- Timeout only if requests don't complete in time

### Affected Files
| File | Line(s) | Issue |
|------|---------|-------|
| `app/main.py` | 104-109 | Incorrect shutdown logic |

### Acceptance Criteria
- [ ] Graceful shutdown waits for active requests
- [ ] Timeout applies to request completion, not signal
- [ ] Logs show requests drained
- [ ] Clean shutdown under normal conditions

### Implementation Details

```python
# app/main.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from typing import Set

# Track active requests
active_requests: Set[int] = set()
request_counter = 0
shutdown_event = asyncio.Event()


class RequestTracker:
    """Middleware to track active requests for graceful shutdown."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            global request_counter
            request_counter += 1
            request_id = request_counter
            active_requests.add(request_id)
            try:
                await self.app(scope, receive, send)
            finally:
                active_requests.discard(request_id)
        else:
            await self.app(scope, receive, send)


async def wait_for_requests_to_complete(timeout: float = 30.0):
    """Wait for all active requests to complete."""
    if not active_requests:
        logger.info("No active requests to drain")
        return

    logger.info(f"Waiting for {len(active_requests)} active requests to complete...")
    start = time.time()

    while active_requests and (time.time() - start) < timeout:
        await asyncio.sleep(0.1)

    if active_requests:
        logger.warning(f"Timeout: {len(active_requests)} requests still active after {timeout}s")
    else:
        elapsed = time.time() - start
        logger.info(f"All requests completed in {elapsed:.2f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with proper graceful shutdown."""
    # Startup
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting...")
    # ... existing startup code ...

    yield

    # Shutdown
    logger.info("Initiating graceful shutdown...")

    # Wait for active requests to complete
    await wait_for_requests_to_complete(timeout=30.0)

    # Close database connections
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.exception("Error closing database connections")

    logger.info("Shutdown complete")


# Add middleware
app = FastAPI(lifespan=lifespan, ...)
app.add_middleware(RequestTracker)
```

### Testing Requirements
- [ ] Unit test: Shutdown waits for active requests
- [ ] Unit test: Timeout triggers after configured time
- [ ] Integration test: Requests complete during shutdown

### Dependencies
- None

### Estimated Effort
**2-3 hours**

---

## TOOL-013: Add Error Message Sanitization

### Priority
**Medium** | **Security Impact**: Low

### Summary
Error responses include raw exception messages that may leak internal implementation details, file paths, or stack traces to clients.

### Current Behavior
```python
raise HTTPException(
    status_code=500,
    detail=f"Failed to register tool: {str(e)}"  # Exposes internal errors
)
```

### Expected Behavior
- Generic error messages for 500 errors in production
- Detailed errors only in debug mode
- Error IDs for correlating logs
- No stack traces in responses

### Affected Files
| File | Issue |
|------|-------|
| `app/api/mcp.py` | Error message exposure |
| `app/api/admin.py` | Error message exposure |
| Multiple | Generic pattern |

### Acceptance Criteria
- [ ] Production errors are generic with error ID
- [ ] Debug mode shows full details
- [ ] Error ID in response correlates with logs
- [ ] No file paths or stack traces in responses

### Implementation Details

```python
# app/utils/errors.py (new file)

import uuid
import logging
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)


class SafeHTTPException(HTTPException):
    """HTTP exception that sanitizes error details in production."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        internal_message: str = None,
        error_id: str = None,
    ):
        self.error_id = error_id or str(uuid.uuid4())[:8]
        self.internal_message = internal_message or detail

        # Log full error
        logger.error(
            f"[{self.error_id}] HTTP {status_code}: {self.internal_message}",
            extra={"error_id": self.error_id, "status_code": status_code}
        )

        # Sanitize for response
        if settings.DEBUG:
            safe_detail = f"[{self.error_id}] {detail}"
        else:
            safe_detail = f"An error occurred. Reference ID: {self.error_id}"

        super().__init__(status_code=status_code, detail=safe_detail)


def handle_internal_error(e: Exception, context: str = "operation") -> HTTPException:
    """Convert exception to safe HTTP error response."""
    error_id = str(uuid.uuid4())[:8]

    logger.exception(
        f"[{error_id}] Internal error during {context}",
        extra={"error_id": error_id}
    )

    if settings.DEBUG:
        detail = f"[{error_id}] {context} failed: {str(e)}"
    else:
        detail = f"Internal server error. Reference ID: {error_id}"

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )


# Usage in app/api/admin.py:

from app.utils.errors import handle_internal_error

@router.post("/tools")
async def register_tool(...):
    try:
        # ... implementation ...
    except ValueError as e:
        # Validation errors can show details
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise handle_internal_error(e, context="tool registration")
```

### Testing Requirements
- [ ] Unit test: Production mode hides details
- [ ] Unit test: Debug mode shows details
- [ ] Unit test: Error ID in response matches logs
- [ ] Integration test: No stack traces in responses

### Dependencies
- None

### Estimated Effort
**2-3 hours**

---

# Low Priority

---

## TOOL-014: Fix Singleton Race Conditions for Multi-Worker Deployments

### Priority
**Low** | **Stability Impact**: Low (single-worker) / Medium (multi-worker)

### Summary
Multiple singleton instances (`_embedding_client`, `_embedding_service`, etc.) use global variables with no thread safety. In multi-worker deployments, each worker has its own instance, and initialization is racy.

### Affected Singletons
- `_embedding_client` in `embedding_client.py`
- `_embedding_service` in `embedding_service.py`
- `_discovery_service` in `mcp_discovery.py`
- `_summarization_service` in `summarization.py`
- `_EMBEDDING_CACHE` in `embedding_service.py`

### Acceptance Criteria
- [ ] Thread-safe singleton initialization
- [ ] Clear documentation of multi-worker behavior
- [ ] Consider dependency injection pattern

### Implementation Details

```python
# app/registry/embedding_client.py

import threading
from functools import lru_cache

_lock = threading.Lock()
_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    """Thread-safe singleton getter."""
    global _embedding_client
    if _embedding_client is None:
        with _lock:
            # Double-check after acquiring lock
            if _embedding_client is None:
                _embedding_client = EmbeddingClient()
    return _embedding_client


# Alternative: Use lru_cache for simpler thread-safety
@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    """Get cached singleton instance."""
    return EmbeddingClient()
```

### Estimated Effort
**2 hours**

---

## TOOL-015: Add Embedding Service to Readiness Check

### Priority
**Low** | **Operability Impact**: Medium

### Summary
The readiness check only verifies database connectivity. If the embedding service is down, tools can be registered but searches will fail. The service should be marked not-ready.

### Acceptance Criteria
- [ ] Readiness includes embedding service check
- [ ] Configurable (embedding check optional)
- [ ] Graceful degradation option

### Implementation Details

```python
# app/main.py

@app.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Kubernetes readiness probe."""
    errors = []

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"database: {str(e)}")

    # Check embedding service (optional)
    if settings.REQUIRE_EMBEDDING_FOR_READINESS:
        try:
            client = get_embedding_client()
            if not await client.health_check():
                errors.append("embedding_service: health check failed")
        except Exception as e:
            errors.append(f"embedding_service: {str(e)}")

    if errors:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "errors": errors}
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready"}
    )
```

### Estimated Effort
**1-2 hours**

---

## TOOL-016: Implement Structured Logging with Correlation IDs

### Priority
**Low** | **Operability Impact**: Medium

### Summary
Current logging uses basic format without request correlation IDs. In production, tracking requests across log entries is difficult.

### Acceptance Criteria
- [ ] Request ID generated for each request
- [ ] Request ID included in all log entries
- [ ] Request ID returned in response headers
- [ ] JSON log format option

### Implementation Details

```python
# app/middleware/logging.py

import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])
        request_id_var.set(request_id)

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get("")
        return True


# Configure in main.py
logging.basicConfig(
    format="%(asctime)s [%(request_id)s] %(name)s %(levelname)s: %(message)s"
)
for handler in logging.root.handlers:
    handler.addFilter(CorrelationIdFilter())
```

### Estimated Effort
**2-3 hours**

---

## TOOL-017: Add Retry Logic to MCP Server Discovery

### Priority
**Low** | **Reliability Impact**: Medium

### Summary
MCP server discovery tries multiple endpoints but doesn't retry on transient failures. Network blips cause sync failures.

### Acceptance Criteria
- [ ] Configurable retry count and backoff
- [ ] Distinguish transient vs permanent failures
- [ ] Metrics for retry attempts

### Implementation Details

```python
# app/services/mcp_discovery.py

import backoff

class MCPDiscoveryService:

    @backoff.on_exception(
        backoff.expo,
        (httpx.ConnectError, httpx.ReadTimeout),
        max_tries=3,
        max_time=30,
    )
    async def discover_tools_from_http_server(
        self,
        server_url: str,
        server_name: str = "unknown"
    ) -> List[MCPTool]:
        # ... existing implementation ...
```

### Estimated Effort
**1-2 hours**

---

## TOOL-018: Fix MCP Resource Return Types

### Priority
**Low** | **Correctness Impact**: Low

### Summary
MCP resources return JSON strings instead of structured data. The FastMCP framework should handle serialization.

### Acceptance Criteria
- [ ] Resources return dict/list, not JSON strings
- [ ] FastMCP handles serialization
- [ ] Consistent with FastMCP conventions

### Implementation Details

```python
# app/mcp_fastmcp_server.py

@mcp.resource("toolbox://categories")
async def get_categories() -> dict:  # Return dict, not str
    """Get all available tool categories."""
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        try:
            categories = await registry.get_distinct_categories()
            return {
                "categories": categories,
                "total": len(categories),
            }
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return {"error": str(e), "categories": []}
```

### Estimated Effort
**1 hour**

---

# Appendix: Quick Reference

## Priority Summary

| Priority | Count | Total Effort |
|----------|-------|--------------|
| Critical | 3 | 7-11 hours |
| High | 5 | 14-21 hours |
| Medium | 5 | 11-16 hours |
| Low | 5 | 7-10 hours |
| **Total** | **18** | **39-58 hours** |

## Recommended Order of Implementation

### Sprint 1: Critical Fixes (Must complete before production)
1. TOOL-001: Embedding dimension mismatch
2. TOOL-002: Batch embedding bug
3. TOOL-003: Async subprocess

### Sprint 2: Security Hardening
4. TOOL-005: Timing attack fix
5. TOOL-008: Secure module import
6. TOOL-006: CORS restrictions
7. TOOL-011: Externalize secrets

### Sprint 3: Stability & Performance
8. TOOL-004: Rate limiting
9. TOOL-007: Request size limits
10. TOOL-009: Transaction management
11. TOOL-010: Query optimization

### Sprint 4: Operability
12. TOOL-012: Graceful shutdown
13. TOOL-013: Error sanitization
14. TOOL-015: Readiness check
15. TOOL-016: Structured logging

### Backlog (As time permits)
16. TOOL-014: Singleton thread safety
17. TOOL-017: Retry logic
18. TOOL-018: Resource return types
