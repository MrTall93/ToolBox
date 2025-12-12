"""
SQLAlchemy model for Tool with pgvector support.
"""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, JSON, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db.session import Base
from app.config import settings


class Tool(Base):
    """
    Tool model with vector embeddings for semantic search.

    Attributes:
        id: Unique tool identifier (primary key)
        name: Tool name (unique, indexed)
        description: Human-readable tool description
        category: Tool category for filtering
        tags: List of tags for additional classification
        input_schema: JSON schema for tool input validation
        output_schema: JSON schema for tool output
        implementation_type: Type of implementation (python_function, api_call, etc.)
        implementation_code: Actual implementation code or reference
        embedding: Vector embedding for semantic search (1536 dimensions)
        is_active: Whether the tool is currently active
        version: Tool version string
        created_at: Timestamp when tool was created
        updated_at: Timestamp when tool was last updated
        metadata: Additional metadata as JSON
    """

    __tablename__ = "tools"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tags: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Schema definitions
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Implementation
    implementation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="python_function"
    )
    implementation_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Vector embedding for semantic search
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=True
    )

    # Status and versioning
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Additional metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Indexes for performance
    __table_args__ = (
        # GIN index for tags array search - created in migration
        # Index("ix_tools_tags", sa.text("(tags::jsonb)"), postgresql_using="gin"),
        # Vector similarity index (ivfflat)
        Index(
            "ix_tools_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Composite index for active tools by category
        Index("ix_tools_active_category", "is_active", "category"),
    )

    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name='{self.name}', category='{self.category}')>"

    def to_dict(self) -> dict:
        """Convert model to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "implementation_type": self.implementation_type,
            "is_active": self.is_active,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata_,
        }
