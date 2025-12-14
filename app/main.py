"""FastAPI application entry point."""

import asyncio
import logging
import os
import signal

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.db.session import get_db, close_db
from app.api import mcp, admin
from app.registry import VectorStore, get_embedding_client
from app.schemas.mcp import HealthCheckResponse
# FastMCP server is run separately on port 8080 for MCP Inspector compatibility
# from app.mcp_fastmcp_server import mcp as fastmcp_server

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

# Signal handlers for graceful shutdown
def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Vector-powered tool registry with MCP protocol support",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
    except Exception:
        pass

    # Check embedding service
    embedding_healthy = False
    try:
        client = get_embedding_client()
        embedding_healthy = await client.health_check()
    except Exception:
        pass

    # Count indexed tools
    indexed_tools = 0
    try:
        vector_store = VectorStore(db)
        indexed_tools = await vector_store.count_indexed_tools()
    except Exception:
        pass

    return HealthCheckResponse(
        status="healthy" if db_healthy else "unhealthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_healthy,
        embedding_service=embedding_healthy,
        indexed_tools=indexed_tools,
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting...")
    logger.info("Interactive docs: http://localhost:8000/docs")
    logger.info("MCP endpoints ready at /mcp/")
    logger.info("Admin endpoints ready at /admin/")

    # Test database connection
    try:
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            logger.info("✅ Database connection established")
            break
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise

    # Auto-sync MCP servers on startup
    if settings.MCP_AUTO_SYNC_ON_STARTUP and settings.MCP_SERVERS:
        logger.info(f"🔄 Auto-syncing {len(settings.MCP_SERVERS)} MCP servers...")
        try:
            from app.services.mcp_discovery import get_mcp_discovery_service
            discovery_service = get_mcp_discovery_service()

            async for db in get_db():
                results = await discovery_service.sync_all_servers(session=db)
                logger.info(
                    f"✅ MCP sync complete: {results['successful_syncs']}/{results['total_servers']} servers, "
                    f"{results['total_tools_created']} created, {results['total_tools_updated']} updated"
                )
                break
        except Exception as e:
            logger.warning(f"⚠️ MCP auto-sync failed (non-fatal): {e}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown with graceful shutdown."""
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


@app.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe for Kubernetes."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "service": settings.APP_NAME}
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        return {"status": "not_ready", "service": settings.APP_NAME}


@app.get("/live")
async def liveness_check() -> dict:
    """Liveness probe for Kubernetes."""
    return {"status": "alive", "service": settings.APP_NAME}
