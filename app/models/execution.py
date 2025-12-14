"""
SQLAlchemy model for ToolExecution tracking.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, Integer, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum
from app.db.session import Base


class ExecutionStatus(str, enum.Enum):
    """Execution status enum."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolExecution(Base):
    """
    Track tool execution history and results.

    Attributes:
        id: Unique execution identifier
        tool_id: Foreign key to Tool
        tool_name: Denormalized tool name for query performance
        input_data: Input arguments passed to the tool
        output_data: Tool execution output/result
        status: Execution status (pending, running, success, failed, etc.)
        error_message: Error message if execution failed
        execution_time_ms: Execution duration in milliseconds
        started_at: When execution started
        completed_at: When execution completed
        metadata: Additional execution metadata
    """

    __tablename__ = "tool_executions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to Tool
    tool_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Denormalized tool name for faster queries
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Execution data
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status tracking
    status: Mapped[ExecutionStatus] = mapped_column(
        String(length=20),  # Store enum value as string
        default=ExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Performance metrics
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps (timezone-aware)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Additional metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationship to Tool (optional, for joins)

    # Indexes for performance
    __table_args__ = (
        # Composite index for querying executions by tool and status
        Index("ix_executions_tool_status", "tool_id", "status"),
        # Index for time-based queries
        Index("ix_executions_started_at", "started_at"),
        # Composite index for recent executions by tool
        Index("ix_executions_tool_time", "tool_name", "started_at"),
    )

    def __repr__(self) -> str:
        status_val = self.status.value if hasattr(self.status, 'value') else self.status
        return f"<ToolExecution(id={self.id}, tool_name='{self.tool_name}', status='{status_val}')>"

    def to_dict(self) -> dict:
        """Convert model to dictionary for API responses."""
        return {
            "id": self.id,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status.value,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata_,
        }
