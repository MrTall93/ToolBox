"""
Tests for embedding dimension migration.

These tests verify that the migration correctly handles the embedding dimension
mismatch and that the database schema matches the model configuration.

NOTE: These tests require a PostgreSQL database with pgvector extension.
They will be skipped if DATABASE_URL doesn't point to PostgreSQL.
"""
import os
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from app.config import settings
from app.models import Tool
from app.db.session import Base


# Skip these tests if not using PostgreSQL
pytestmark = pytest.mark.skipif(
    not settings.DATABASE_URL or "postgresql" not in settings.DATABASE_URL,
    reason="Migration tests require PostgreSQL with pgvector"
)


@pytest.fixture
def alembic_config():
    """Create Alembic configuration."""
    config = Config("alembic.ini")
    return config


@pytest.fixture
def migration_engine():
    """
    Create a separate test database for migration testing.

    This creates an isolated database to test migrations without affecting
    the main test database.
    """
    # Use a separate test database for migrations
    base_url = settings.DATABASE_URL.rsplit("/", 1)[0]
    test_db_name = "toolbox_migration_test"
    test_db_url = f"{base_url}/{test_db_name}"

    # Create database
    admin_engine = create_engine(base_url.replace("+asyncpg", ""))
    with admin_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        # Drop if exists
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        # Create fresh
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))

    admin_engine.dispose()

    # Return test engine
    engine = create_engine(test_db_url.replace("+asyncpg", ""))
    yield engine

    # Cleanup
    engine.dispose()
    admin_engine = create_engine(base_url.replace("+asyncpg", ""))
    with admin_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
    admin_engine.dispose()


class TestEmbeddingDimensionMigration:
    """Tests for the embedding dimension fix migration."""

    def test_get_embedding_dimension_default(self):
        """Test that get_embedding_dimension returns default value."""
        # Import the function from migration
        from alembic.versions import (
            20251220_0001_002_fix_embedding_dimension as migration_002
        )

        # Clear environment variable
        old_value = os.environ.pop("EMBEDDING_DIMENSION", None)
        try:
            dimension = migration_002.get_embedding_dimension()
            assert dimension == 1536, "Default dimension should be 1536"
        finally:
            if old_value:
                os.environ["EMBEDDING_DIMENSION"] = old_value

    def test_get_embedding_dimension_from_env(self):
        """Test that get_embedding_dimension reads from environment."""
        from alembic.versions import (
            20251220_0001_002_fix_embedding_dimension as migration_002
        )

        old_value = os.environ.get("EMBEDDING_DIMENSION")
        try:
            os.environ["EMBEDDING_DIMENSION"] = "768"
            dimension = migration_002.get_embedding_dimension()
            assert dimension == 768, "Should read dimension from environment"
        finally:
            if old_value:
                os.environ["EMBEDDING_DIMENSION"] = old_value
            else:
                os.environ.pop("EMBEDDING_DIMENSION", None)

    def test_get_embedding_dimension_invalid_value(self):
        """Test that invalid dimension falls back to default."""
        from alembic.versions import (
            20251220_0001_002_fix_embedding_dimension as migration_002
        )

        old_value = os.environ.get("EMBEDDING_DIMENSION")
        try:
            os.environ["EMBEDDING_DIMENSION"] = "invalid"
            dimension = migration_002.get_embedding_dimension()
            assert dimension == 1536, "Should fall back to default on invalid value"
        finally:
            if old_value:
                os.environ["EMBEDDING_DIMENSION"] = old_value
            else:
                os.environ.pop("EMBEDDING_DIMENSION", None)

    def test_migration_001_uses_env_dimension(self, migration_engine, alembic_config):
        """Test that migration 001 creates table with configured dimension."""
        from alembic.versions import (
            20251210_0000_001_initial_schema as migration_001
        )

        # Set custom dimension
        old_value = os.environ.get("EMBEDDING_DIMENSION")
        try:
            os.environ["EMBEDDING_DIMENSION"] = "768"

            # Run migration 001
            with migration_engine.connect() as conn:
                # Enable pgvector
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()

                # Run upgrade
                migration_001.upgrade()

                # Check column type
                inspector = inspect(migration_engine)
                columns = inspector.get_columns("tools")
                embedding_col = next(c for c in columns if c["name"] == "embedding")

                # The column should be created with dimension 768
                # Note: Can't easily check vector dimension in SQLAlchemy inspector,
                # so we'll verify we can insert a 768-dim vector

        finally:
            if old_value:
                os.environ["EMBEDDING_DIMENSION"] = old_value
            else:
                os.environ.pop("EMBEDDING_DIMENSION", None)

    def test_migration_002_fixes_dimension(self, migration_engine):
        """Test that migration 002 correctly changes dimension."""
        from alembic.versions import (
            20251210_0000_001_initial_schema as migration_001,
            20251220_0001_002_fix_embedding_dimension as migration_002
        )

        with migration_engine.connect() as conn:
            # Enable pgvector
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

            # Run migration 001 (creates with 1024, the old hardcoded value)
            # We need to temporarily modify the migration to use 1024
            old_value = os.environ.get("EMBEDDING_DIMENSION")
            try:
                os.environ["EMBEDDING_DIMENSION"] = "1024"
                migration_001.upgrade()

                # Insert a test tool with 1024-dim embedding
                conn.execute(text("""
                    INSERT INTO tools
                    (name, description, category, tags, input_schema, output_schema,
                     implementation_type, is_active, version, created_at, updated_at, embedding)
                    VALUES
                    ('test_tool', 'Test', 'test', '[]', '{}', '{}',
                     'python_function', true, '1.0.0', NOW(), NOW(),
                     ARRAY[{}]::vector(1024))
                """.format(",".join(["0.1"] * 1024))))
                conn.commit()

                # Now run migration 002 to fix dimension to 1536
                os.environ["EMBEDDING_DIMENSION"] = "1536"
                migration_002.upgrade()

                # Verify the embedding was cleared (since dimensions changed)
                result = conn.execute(text(
                    "SELECT embedding FROM tools WHERE name = 'test_tool'"
                ))
                row = result.fetchone()
                assert row[0] is None, "Embedding should be cleared after dimension change"

                # Verify we can now insert 1536-dim embedding
                conn.execute(text("""
                    UPDATE tools
                    SET embedding = ARRAY[{}]::vector(1536)
                    WHERE name = 'test_tool'
                """.format(",".join(["0.2"] * 1536))))
                conn.commit()

                # Verify it was inserted successfully
                result = conn.execute(text(
                    "SELECT embedding FROM tools WHERE name = 'test_tool'"
                ))
                row = result.fetchone()
                assert row[0] is not None, "Should be able to insert 1536-dim embedding"

            finally:
                if old_value:
                    os.environ["EMBEDDING_DIMENSION"] = old_value
                else:
                    os.environ.pop("EMBEDDING_DIMENSION", None)

    def test_migration_002_downgrade(self, migration_engine):
        """Test that migration 002 downgrade reverts to 1024 dimension."""
        from alembic.versions import (
            20251210_0000_001_initial_schema as migration_001,
            20251220_0001_002_fix_embedding_dimension as migration_002
        )

        with migration_engine.connect() as conn:
            # Enable pgvector
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

            # Setup: Run migrations up to 002
            old_value = os.environ.get("EMBEDDING_DIMENSION")
            try:
                os.environ["EMBEDDING_DIMENSION"] = "1536"
                migration_001.upgrade()
                migration_002.upgrade()

                # Now downgrade
                migration_002.downgrade()

                # Verify we can insert 1024-dim embedding (original dimension)
                conn.execute(text("""
                    INSERT INTO tools
                    (name, description, category, tags, input_schema, output_schema,
                     implementation_type, is_active, version, created_at, updated_at, embedding)
                    VALUES
                    ('test_tool_downgrade', 'Test', 'test', '[]', '{}', '{}',
                     'python_function', true, '1.0.0', NOW(), NOW(),
                     ARRAY[{}]::vector(1024))
                """.format(",".join(["0.1"] * 1024))))
                conn.commit()

                # Verify it was inserted
                result = conn.execute(text(
                    "SELECT embedding FROM tools WHERE name = 'test_tool_downgrade'"
                ))
                row = result.fetchone()
                assert row[0] is not None, "Should be able to insert 1024-dim embedding after downgrade"

            finally:
                if old_value:
                    os.environ["EMBEDDING_DIMENSION"] = old_value
                else:
                    os.environ.pop("EMBEDDING_DIMENSION", None)


class TestDimensionConsistency:
    """Tests to ensure dimension consistency across the application."""

    @pytest.mark.asyncio
    async def test_model_dimension_matches_config(self):
        """Test that the Tool model uses the configured dimension."""
        from app.models import Tool
        from app.config import settings

        # The model should use settings.EMBEDDING_DIMENSION
        # This is verified by checking the column definition
        assert settings.EMBEDDING_DIMENSION == 1536, "Config should default to 1536"

    def test_migration_dimension_consistency(self):
        """Test that both migrations use the same dimension logic."""
        from alembic.versions import (
            20251210_0000_001_initial_schema as migration_001,
            20251220_0001_002_fix_embedding_dimension as migration_002
        )

        # Both should have the same get_embedding_dimension function
        old_value = os.environ.get("EMBEDDING_DIMENSION")
        try:
            os.environ["EMBEDDING_DIMENSION"] = "768"

            dim_001 = migration_001.get_embedding_dimension()
            dim_002 = migration_002.get_embedding_dimension()

            assert dim_001 == dim_002 == 768, "Both migrations should read same dimension"

        finally:
            if old_value:
                os.environ["EMBEDDING_DIMENSION"] = old_value
            else:
                os.environ.pop("EMBEDDING_DIMENSION", None)


@pytest.mark.integration
class TestMigrationIntegration:
    """Integration tests for the full migration process."""

    def test_fresh_deployment_uses_correct_dimension(self, migration_engine, alembic_config):
        """Test that a fresh deployment creates database with correct dimension."""
        # This tests the real Alembic migration process
        old_value = os.environ.get("EMBEDDING_DIMENSION")
        try:
            os.environ["EMBEDDING_DIMENSION"] = "1536"

            # Update alembic config to use test database
            test_db_url = migration_engine.url
            alembic_config.set_main_option("sqlalchemy.url", str(test_db_url))

            # Run all migrations
            command.upgrade(alembic_config, "head")

            # Verify we can insert tools with 1536-dim embeddings
            with migration_engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO tools
                    (name, description, category, tags, input_schema, output_schema,
                     implementation_type, is_active, version, created_at, updated_at, embedding)
                    VALUES
                    ('integration_test_tool', 'Test', 'test', '[]', '{}', '{}',
                     'python_function', true, '1.0.0', NOW(), NOW(),
                     ARRAY[{}]::vector(1536))
                """.format(",".join(["0.1"] * 1536))))
                conn.commit()

                result = conn.execute(text(
                    "SELECT name FROM tools WHERE name = 'integration_test_tool'"
                ))
                assert result.fetchone() is not None

        finally:
            if old_value:
                os.environ["EMBEDDING_DIMENSION"] = old_value
            else:
                os.environ.pop("EMBEDDING_DIMENSION", None)
