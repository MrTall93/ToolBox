"""
Tool Registry - Main orchestration class for tool management.

Combines vector store, embedding client, and database operations to provide
a complete tool registry with semantic search capabilities.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool
from app.models.execution import ToolExecution, ExecutionStatus
from app.registry.vector_store import VectorStore
from app.registry.embedding_client import EmbeddingClient, get_embedding_client
from app.config import settings
from app.utils.validation import (
    ValidationError,
    validate_tool_name,
    validate_category,
    validate_tags,
    validate_json_schema,
    validate_implementation_code,
    validate_tool_arguments,
)


class ToolRegistry:
    """
    Main tool registry class.

    Provides high-level API for:
    - Registering and managing tools
    - Semantic search over tools
    - Tool execution tracking
    - Automatic embedding generation
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: Optional[EmbeddingClient] = None,
    ):
        """
        Initialize tool registry.

        Args:
            session: Async SQLAlchemy session
            embedding_client: Optional custom embedding client
        """
        self.session = session
        self.vector_store = VectorStore(session)
        self.embedding_client = embedding_client or get_embedding_client()

    async def register_tool(
        self,
        name: str,
        description: str,
        category: str,
        input_schema: Dict[str, Any],
        tags: Optional[List[str]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        implementation_type: str = "python_function",
        implementation_code: Optional[str] = None,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
        auto_embed: bool = True,
    ) -> Tool:
        """
        Register a new tool in the registry.

        Automatically generates embeddings for the tool unless auto_embed=False.

        Args:
            name: Unique tool name
            description: Human-readable description
            category: Tool category
            input_schema: JSON schema for input validation
            tags: List of tags
            output_schema: JSON schema for output
            implementation_type: Type of implementation
            implementation_code: Implementation code or reference
            version: Tool version
            metadata: Additional metadata
            auto_embed: Automatically generate embedding

        Returns:
            Created Tool object

        Raises:
            ValueError: If tool with same name already exists
        """
        # Validate input parameters
        try:
            name = validate_tool_name(name)
            category = validate_category(category)
            tags = validate_tags(tags or [])
            input_schema = validate_json_schema(input_schema)

            if output_schema:
                output_schema = validate_json_schema(output_schema)

            if implementation_code:
                implementation_code = validate_implementation_code(
                    implementation_code, implementation_type
                )

        except ValidationError as e:
            raise ValueError(str(e))

        # Check if tool already exists
        stmt = select(Tool).where(Tool.name == name)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"Tool with name '{name}' already exists")

        # Create tool
        tool = Tool(
            name=name,
            description=description,
            category=category,
            tags=tags,
            input_schema=input_schema,
            output_schema=output_schema,
            implementation_type=implementation_type,
            implementation_code=implementation_code,
            version=version,
            metadata_=metadata,
            is_active=True,
        )

        self.session.add(tool)
        await self.session.flush()  # Get the tool ID

        # Generate embedding if requested
        if auto_embed:
            await self.update_tool_embedding(tool.id)

        await self.session.commit()
        await self.session.refresh(tool)

        return tool

    async def update_tool_embedding(self, tool_id: int) -> None:
        """
        Generate and update embedding for a tool.

        Args:
            tool_id: ID of the tool to update

        Raises:
            ValueError: If tool not found
        """
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.session.execute(stmt)
        tool = result.scalar_one_or_none()

        if not tool:
            raise ValueError(f"Tool with id {tool_id} not found")

        # Generate embedding
        tool_data = {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "tags": tool.tags,
        }
        embedding = await self.embedding_client.embed_tool(tool_data)

        # Update tool
        await self.vector_store.index_tool(tool_id, embedding)

    async def update_tool(
        self,
        tool_id: int,
        **updates,
    ) -> Tool:
        """
        Update tool properties.

        Automatically regenerates embedding if content changes.

        Args:
            tool_id: ID of the tool to update
            **updates: Fields to update

        Returns:
            Updated Tool object

        Raises:
            ValueError: If tool not found
        """
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.session.execute(stmt)
        tool = result.scalar_one_or_none()

        if not tool:
            raise ValueError(f"Tool with id {tool_id} not found")

        # Track if we need to regenerate embedding
        content_fields = {"name", "description", "category", "tags"}
        needs_reembed = any(field in updates for field in content_fields)

        # Update fields
        for key, value in updates.items():
            if key == "metadata":
                key = "metadata_"  # Handle reserved keyword
            if hasattr(tool, key):
                setattr(tool, key, value)

        # Regenerate embedding if content changed
        if needs_reembed:
            await self.update_tool_embedding(tool_id)

        await self.session.commit()
        await self.session.refresh(tool)

        return tool

    async def get_tool(self, tool_id: int) -> Optional[Tool]:
        """Get tool by ID."""
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        stmt = select(Tool).where(Tool.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_tools(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Tool]:
        """
        List all tools with optional filtering.

        Args:
            category: Filter by category
            active_only: Only return active tools
            limit: Maximum number of tools
            offset: Pagination offset

        Returns:
            List of Tool objects
        """
        stmt = select(Tool)

        if active_only:
            stmt = stmt.where(Tool.is_active == True)
        if category:
            stmt = stmt.where(Tool.category == category)

        stmt = stmt.order_by(Tool.name).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_tool(
        self,
        query: str,
        limit: int = None,
        threshold: float = None,
        category: Optional[str] = None,
        use_hybrid: bool = None,
    ) -> List[Tuple[Tool, float]]:
        """
        Find tools using semantic search.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            category: Optional category filter
            use_hybrid: Use hybrid search (vector + text), defaults to config setting

        Returns:
            List of (Tool, similarity_score) tuples
        """
        if use_hybrid is None:
            use_hybrid = settings.USE_HYBRID_SEARCH

        # Generate query embedding
        query_embedding = await self.embedding_client.embed_text(query)

        # Perform search
        if use_hybrid:
            results = await self.vector_store.hybrid_search(
                query_embedding=query_embedding,
                query_text=query,
                limit=limit,
                threshold=threshold,
                category=category,
            )
        else:
            results = await self.vector_store.semantic_search(
                query_embedding=query_embedding,
                limit=limit,
                threshold=threshold,
                category=category,
            )

        return results

    async def find_similar_tools(
        self,
        tool_id: int,
        limit: int = 5,
    ) -> List[Tuple[Tool, float]]:
        """
        Find tools similar to a given tool.

        Args:
            tool_id: ID of the reference tool
            limit: Maximum number of similar tools

        Returns:
            List of (Tool, similarity_score) tuples
        """
        return await self.vector_store.find_similar_tools(
            tool_id=tool_id,
            limit=limit,
        )

    async def deactivate_tool(self, tool_id: int) -> None:
        """
        Deactivate a tool (soft delete).

        Args:
            tool_id: ID of the tool to deactivate
        """
        await self.update_tool(tool_id, is_active=False)

    async def activate_tool(self, tool_id: int) -> None:
        """
        Activate a previously deactivated tool.

        Args:
            tool_id: ID of the tool to activate
        """
        await self.update_tool(tool_id, is_active=True)

    async def delete_tool(self, tool_id: int) -> None:
        """
        Permanently delete a tool.

        Args:
            tool_id: ID of the tool to delete

        Raises:
            ValueError: If tool not found
        """
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.session.execute(stmt)
        tool = result.scalar_one_or_none()

        if not tool:
            raise ValueError(f"Tool with id {tool_id} not found")

        await self.session.delete(tool)
        await self.session.commit()

    async def record_execution(
        self,
        tool_id: int,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]] = None,
        status: ExecutionStatus = ExecutionStatus.SUCCESS,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolExecution:
        """
        Record a tool execution.

        Args:
            tool_id: ID of the executed tool
            input_data: Input arguments
            output_data: Execution output
            status: Execution status
            error_message: Error message if failed
            execution_time_ms: Execution duration
            metadata: Additional metadata

        Returns:
            ToolExecution object
        """
        # Get tool name
        tool = await self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool with id {tool_id} not found")

        execution = ToolExecution(
            tool_id=tool_id,
            tool_name=tool.name,
            input_data=input_data,
            output_data=output_data,
            status=status,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
            completed_at=datetime.now(timezone.utc) if status != ExecutionStatus.RUNNING else None,
            metadata_=metadata,
        )

        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)

        return execution

    async def get_tool_stats(self, tool_id: int) -> Dict[str, Any]:
        """
        Get execution statistics for a tool.

        Args:
            tool_id: ID of the tool

        Returns:
            Dictionary with statistics
        """
        from sqlalchemy import func

        stmt = (
            select(
                func.count(ToolExecution.id).label("total_executions"),
                func.count(ToolExecution.id).filter(
                    ToolExecution.status == ExecutionStatus.SUCCESS
                ).label("successful_executions"),
                func.count(ToolExecution.id).filter(
                    ToolExecution.status == ExecutionStatus.FAILED
                ).label("failed_executions"),
                func.avg(ToolExecution.execution_time_ms).label("avg_execution_time_ms"),
            )
            .where(ToolExecution.tool_id == tool_id)
        )

        result = await self.session.execute(stmt)
        row = result.one()

        return {
            "total_executions": row.total_executions or 0,
            "successful_executions": row.successful_executions or 0,
            "failed_executions": row.failed_executions or 0,
            "avg_execution_time_ms": float(row.avg_execution_time_ms) if row.avg_execution_time_ms else None,
        }
