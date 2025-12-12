"""Initial schema with pgvector extension

Revision ID: 001
Revises:
Create Date: 2025-12-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema with pgvector extension."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Note: ExecutionStatus uses Python enum, no need to create PostgreSQL enum

    # Create tools table
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),  # SQLAlchemy JSON maps to JSONB in Postgres
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("implementation_type", sa.String(length=50), nullable=False),
        sa.Column("implementation_code", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),  # Updated for Nomic-embed-text-v1.5
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create indexes for tools table
    op.create_index("ix_tools_name", "tools", ["name"], unique=True)
    op.create_index("ix_tools_category", "tools", ["category"], unique=False)
    op.create_index("ix_tools_is_active", "tools", ["is_active"], unique=False)
    op.create_index("ix_tools_active_category", "tools", ["is_active", "category"], unique=False)

    # Create GIN index for tags (JSON array search)
    op.execute("""
        CREATE INDEX ix_tools_tags ON tools USING gin ((tags::jsonb))
    """)

    # Create ivfflat index for vector similarity search
    op.execute(
        """
        CREATE INDEX ix_tools_embedding ON tools
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # Create tool_executions table
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),  # Uses Python enum in model
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tool_id"],
            ["tools.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for tool_executions table
    op.create_index("ix_executions_tool_id", "tool_executions", ["tool_id"], unique=False)
    op.create_index("ix_executions_tool_name", "tool_executions", ["tool_name"], unique=False)
    op.create_index("ix_executions_status", "tool_executions", ["status"], unique=False)
    op.create_index("ix_executions_started_at", "tool_executions", ["started_at"], unique=False)
    op.create_index(
        "ix_executions_tool_status", "tool_executions", ["tool_id", "status"], unique=False
    )
    op.create_index(
        "ix_executions_tool_time", "tool_executions", ["tool_name", "started_at"], unique=False
    )


def downgrade() -> None:
    """Drop all tables and extensions."""
    # Drop tables
    op.drop_table("tool_executions")
    op.drop_table("tools")

    # Drop enum type
    op.execute("DROP TYPE execution_status")

    # Drop pgvector extension
    op.execute("DROP EXTENSION IF EXISTS vector")
