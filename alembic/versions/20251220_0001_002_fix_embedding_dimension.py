"""Fix embedding dimension mismatch

This migration fixes the mismatch between the hardcoded embedding dimension
in the initial migration (1024) and the configurable EMBEDDING_DIMENSION
setting (default 1536).

Revision ID: 002
Revises: 001
Create Date: 2025-12-20 00:00:00.000000
"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def get_embedding_dimension() -> int:
    """
    Get embedding dimension from environment variable.

    Returns:
        int: Embedding dimension (default: 1536)
    """
    try:
        dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        if dimension <= 0:
            raise ValueError("EMBEDDING_DIMENSION must be positive")
        return dimension
    except ValueError as e:
        print(f"Warning: Invalid EMBEDDING_DIMENSION, using default 1536. Error: {e}")
        return 1536


def upgrade() -> None:
    """
    Upgrade embedding column to use correct dimension.

    Steps:
    1. Drop the existing vector index (required before altering column type)
    2. Alter the embedding column to use the configured dimension
    3. Clear existing embeddings (incompatible dimensions)
    4. Recreate the vector index with correct dimension
    """
    dimension = get_embedding_dimension()

    print(f"Upgrading embedding column to dimension {dimension}...")

    # Step 1: Drop existing index
    # Note: Must drop index before altering column type in PostgreSQL
    op.execute("DROP INDEX IF EXISTS ix_tools_embedding")

    # Step 2: Alter column type to new dimension
    # Using raw SQL since SQLAlchemy doesn't support altering vector dimensions directly
    op.execute(f"""
        ALTER TABLE tools
        ALTER COLUMN embedding TYPE vector({dimension})
        USING embedding::vector({dimension})
    """)

    # Step 3: Clear existing embeddings
    # Since dimensions changed, old embeddings are incompatible
    # They will be regenerated on next tool registration or manual reindex
    print(f"Clearing {dimension} existing embeddings (will be regenerated)...")
    op.execute("UPDATE tools SET embedding = NULL WHERE embedding IS NOT NULL")

    # Step 4: Recreate index with correct dimension
    # Using IVFFlat index for fast approximate nearest neighbor search
    print(f"Creating vector index for dimension {dimension}...")
    op.execute(f"""
        CREATE INDEX ix_tools_embedding ON tools
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    print(f"✓ Migration complete. Embedding dimension is now {dimension}")
    print("  Note: Existing tools need their embeddings regenerated.")
    print("  Use the /admin/tools/{tool_id}/reindex endpoint or trigger bulk re-indexing.")


def downgrade() -> None:
    """
    Downgrade to original 1024 dimension.

    WARNING: This will clear all embeddings since dimensions are incompatible.
    """
    print("Downgrading embedding column to original dimension 1024...")

    # Drop index
    op.execute("DROP INDEX IF EXISTS ix_tools_embedding")

    # Revert to 1024 dimension
    op.execute("""
        ALTER TABLE tools
        ALTER COLUMN embedding TYPE vector(1024)
        USING NULL  -- Clear all embeddings since dimensions changed
    """)

    # Clear embeddings
    op.execute("UPDATE tools SET embedding = NULL WHERE embedding IS NOT NULL")

    # Recreate original index
    op.execute("""
        CREATE INDEX ix_tools_embedding ON tools
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    print("✓ Downgrade complete. Embedding dimension is now 1024")
    print("  Note: All embeddings have been cleared and need regeneration.")
