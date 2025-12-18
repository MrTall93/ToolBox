"""FastAPI application entry point."""

import asyncio
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.db.session import get_db, close_db, AsyncSessionLocal
from app.api import mcp, admin
from app.registry import VectorStore, get_embedding_client
from app.schemas.mcp import (
    HealthCheckResponse,
    DetailedHealthCheckResponse,
    ComponentHealth,
    ReadinessResponse,
)

# Initialize OpenTelemetry if enabled
if settings.OTEL_ENABLED:
    from app.observability import init_telemetry
    init_telemetry(
        service_name=settings.OTEL_SERVICE_NAME,
        service_version=settings.OTEL_SERVICE_VERSION,
        environment=os.getenv("ENVIRONMENT", "development")
    )

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    This replaces the deprecated @app.on_event("startup") and @app.on_event("shutdown").
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
            logger.info("Database connection established")
    except Exception as e:
        logger.exception("Database connection failed")
        raise

    # Auto-sync MCP servers on startup
    if settings.MCP_AUTO_SYNC_ON_STARTUP and settings.MCP_SERVERS:
        logger.info(f"Auto-syncing {len(settings.MCP_SERVERS)} MCP servers...")
        try:
            from app.services.mcp_discovery import get_mcp_discovery_service
            discovery_service = get_mcp_discovery_service()

            async with AsyncSessionLocal() as db:
                results = await discovery_service.sync_all_servers(session=db)
                logger.info(
                    f"MCP sync complete: {results['successful_syncs']}/{results['total_servers']} servers, "
                    f"{results['total_tools_created']} created, {results['total_tools_updated']} updated"
                )
        except Exception as e:
            # Log with stack trace for debugging, but don't fail startup
            logger.warning(f"MCP auto-sync failed (non-fatal): {e}", exc_info=True)

    yield  # Application runs here

    # ==================== SHUTDOWN ====================
    logger.info(f"{settings.APP_NAME} shutting down gracefully...")

    # Give existing requests time to complete (grace period)
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=30.0)
        logger.info("Grace period for active requests completed")
    except asyncio.TimeoutError:
        logger.warning("Grace period timeout, forcing shutdown")

    # Close database connections
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.exception("Error closing database connections")

    logger.info("Shutdown complete")


# Create FastAPI application with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Vector-powered tool registry with MCP protocol support",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(mcp.router)
app.include_router(admin.router)

# Note: FastMCP server runs separately on port 8080 for MCP Inspector
# Use http://localhost:8080/mcp for MCP clients


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "mcp": {
                "list_tools": "POST /mcp/list_tools",
                "find_tool": "POST /mcp/find_tool",
                "call_tool": "POST /mcp/call_tool",
            },
            "admin": {
                "register": "POST /admin/tools",
                "update": "PUT /admin/tools/{id}",
                "delete": "DELETE /admin/tools/{id}",
                "stats": "GET /admin/tools/{id}/stats",
            },
        },
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthCheckResponse:
    """
    Comprehensive health check endpoint.

    Checks:
    - Database connectivity
    - Embedding service availability
    - Number of indexed tools
    """
    # Check database
    db_healthy = False
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}", exc_info=True)

    # Check embedding service
    embedding_healthy = False
    try:
        client = get_embedding_client()
        embedding_healthy = await client.health_check()
    except Exception as e:
        logger.warning(f"Embedding service health check failed: {e}", exc_info=True)

    # Count indexed tools
    indexed_tools = 0
    try:
        vector_store = VectorStore(db)
        indexed_tools = await vector_store.count_indexed_tools()
    except Exception as e:
        logger.warning(f"Failed to count indexed tools: {e}", exc_info=True)

    return HealthCheckResponse(
        status="healthy" if db_healthy else "unhealthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_healthy,
        embedding_service=embedding_healthy,
        indexed_tools=indexed_tools,
    )


@app.get(
    "/health/detailed",
    response_model=DetailedHealthCheckResponse,
    summary="Detailed health check",
    description="Returns detailed health status including latency for each component.",
)
async def detailed_health_check(
    db: AsyncSession = Depends(get_db)
) -> DetailedHealthCheckResponse:
    """
    Detailed health check endpoint with component-level status.

    Returns health status, latency, and error information for each component.
    Overall status is:
    - "healthy": All components are healthy
    - "degraded": Some components are healthy
    - "unhealthy": No components are healthy
    """
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
        overall_status = "healthy"
    elif any_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return DetailedHealthCheckResponse(
        status=overall_status,
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        components=components,
        indexed_tools=indexed_tools,
    )


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Service is ready to accept traffic"},
        503: {"description": "Service is not ready"},
    },
    summary="Readiness probe",
    description="Kubernetes readiness probe. Returns 503 if service is not ready.",
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
            content={"status": "ready", "service": settings.APP_NAME, "error": None}
        )
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "service": settings.APP_NAME,
                "error": str(e)
            }
        )


@app.get("/live")
async def liveness_check() -> dict:
    """Liveness probe for Kubernetes."""
    return {"status": "alive", "service": settings.APP_NAME}
