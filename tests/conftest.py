"""Pytest configuration and fixtures for test suite."""
import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from pgvector.sqlalchemy import Vector
from sqlalchemy import text

from app.models import Tool, ToolExecution, ExecutionStatus
from app.db.session import Base, get_db
from app.config import Settings


# Test database URL (SQLite in memory for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )

    # Create tables
    async with engine.begin() as conn:
        # Mock pgvector extension for SQLite
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tools (id INTEGER PRIMARY KEY, name TEXT, description TEXT, category TEXT, tags TEXT, input_schema TEXT, output_schema TEXT, implementation_type TEXT, implementation_code TEXT, embedding BLOB, is_active BOOLEAN, version TEXT, created_at DATETIME, updated_at DATETIME, metadata TEXT)"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_executions (id INTEGER PRIMARY KEY, tool_id INTEGER, tool_name TEXT, input_data TEXT, output_data TEXT, status TEXT, error_message TEXT, execution_time_ms INTEGER, started_at DATETIME, completed_at DATETIME, metadata TEXT)"))

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Begin transaction
        transaction = await session.begin()
        try:
            yield session
        finally:
            # Rollback transaction after test
            await transaction.rollback()


@pytest.fixture
def test_settings():
    """Override settings for testing."""
    return Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        EMBEDDING_ENDPOINT_URL="http://test-embedding-service/embed",
        EMBEDDING_API_KEY="test-api-key",
        EMBEDDING_DIMENSION=1536,
        DEBUG=True,
        LOG_LEVEL="DEBUG",
    )


@pytest.fixture
def mock_embedding_client():
    """Mock embedding client for testing."""
    client = AsyncMock()
    client.embed.return_value = [0.1] * 1536  # Mock 1536-dimensional vector
    client.embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]
    client.health_check.return_value = True
    return client


@pytest.fixture
def sample_tool_data():
    """Sample tool data for testing."""
    return {
        "name": "test_calculator",
        "description": "A test calculator tool that performs basic math operations",
        "category": "math",
        "tags": ["calculator", "math", "basic"],
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
                "a": {"type": "number"},
                "b": {"type": "number"}
            },
            "required": ["operation", "a", "b"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "number"}
            }
        },
        "implementation_type": "python_function",
        "implementation_code": "def calculator(operation, a, b): ...",
        "is_active": True,
        "version": "1.0.0",
        "metadata_": {"author": "test", "license": "MIT"}
    }


@pytest.fixture
def sample_embedding():
    """Sample embedding vector for testing."""
    return [0.1] * 1536


@pytest.fixture
async def sample_tool(test_db_session: AsyncSession, sample_tool_data, sample_embedding):
    """Create a sample tool in the database."""
    tool = Tool(**sample_tool_data)
    tool.embedding = sample_embedding
    test_db_session.add(tool)
    await test_db_session.commit()
    await test_db_session.refresh(tool)
    return tool


@pytest.fixture
async def sample_execution(test_db_session: AsyncSession, sample_tool):
    """Create a sample tool execution in the database."""
    execution = ToolExecution(
        tool_id=sample_tool.id,
        tool_name=sample_tool.name,
        input_data={"operation": "add", "a": 5, "b": 3},
        output_data={"result": 8},
        status=ExecutionStatus.SUCCESS,
        execution_time_ms=45,
    )
    test_db_session.add(execution)
    await test_db_session.commit()
    await test_db_session.refresh(execution)
    return execution


@pytest.fixture
def override_get_db(test_db_session):
    """Override database dependency for testing."""
    async def _override_get_db():
        try:
            yield test_db_session
        finally:
            pass  # Don't close the test session

    return _override_get_db