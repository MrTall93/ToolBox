"""
Vector store implementation using PostgreSQL + pgvector.

This module provides semantic search capabilities for tools using vector embeddings.
"""
from typing import List, Optional, Tuple
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.models.tool import Tool
from app.config import settings
from app.utils.validation import validate_embedding_vector, validate_search_query, validate_similarity_threshold


class VectorStore:
    """
    Vector store for semantic search over tool embeddings.

    Uses PostgreSQL with pgvector extension for efficient similarity search.
    Supports both pure vector search and hybrid search (vector + full-text).
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize vector store with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def initialize(self) -> None:
        """
        Initialize the vector store.

        Ensures pgvector extension is enabled and indexes are created.
        This is typically handled by Alembic migrations, but can be called
        explicitly if needed.
        """
        # Verify pgvector extension exists
        result = await self.session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        if not result.scalar():
            raise RuntimeError("pgvector extension is not installed")

    async def index_tool(
        self,
        tool_id: int,
        embedding: List[float],
    ) -> None:
        """
        Index a tool with its embedding vector.

        Args:
            tool_id: ID of the tool to index
            embedding: Vector embedding (list of floats, dimension = EMBEDDING_DIMENSION)

        Raises:
            ValueError: If embedding dimension doesn't match configuration
        """
        # Validate embedding format and values
        embedding = validate_embedding_vector(embedding)

        # Update tool with embedding
        stmt = (
            select(Tool)
            .where(Tool.id == tool_id)
        )
        result = await self.session.execute(stmt)
        tool = result.scalar_one_or_none()

        if not tool:
            raise ValueError(f"Tool with id {tool_id} not found")

        tool.embedding = embedding
        await self.session.commit()

    async def semantic_search(
        self,
        query_embedding: List[float],
        limit: int = None,
        threshold: float = None,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Tuple[Tool, float]]:
        """
        Perform semantic search using vector similarity.

        Uses cosine distance for similarity measurement. Lower distance = higher similarity.

        Args:
            query_embedding: Query vector embedding
            limit: Maximum number of results to return
            threshold: Minimum similarity threshold (0.0 to 1.0, where 1.0 is identical)
            category: Optional category filter
            active_only: Only return active tools

        Returns:
            List of (Tool, similarity_score) tuples, ordered by similarity (descending)
        """
        if limit is None:
            limit = settings.DEFAULT_SEARCH_LIMIT
        if threshold is None:
            threshold = settings.DEFAULT_SIMILARITY_THRESHOLD

        # Build query with pgvector cosine distance
        # Note: cosine distance ranges from 0 (identical) to 2 (opposite)
        # We convert to similarity score: 1 - (distance / 2) for 0-1 range
        stmt = select(
            Tool,
            (1 - (Tool.embedding.cosine_distance(query_embedding) / 2)).label("similarity")
        ).where(
            Tool.embedding.isnot(None)  # Only tools with embeddings
        )

        # Apply filters
        if active_only:
            stmt = stmt.where(Tool.is_active == True)
        if category:
            stmt = stmt.where(Tool.category == category)

        # Filter by similarity threshold
        # Similarity = 1 - (distance / 2), so distance = 2 * (1 - similarity)
        max_distance = 2 * (1 - threshold)
        stmt = stmt.where(
            Tool.embedding.cosine_distance(query_embedding) <= max_distance
        )

        # Order by similarity (ascending distance = descending similarity)
        stmt = stmt.order_by(Tool.embedding.cosine_distance(query_embedding))
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return [(row.Tool, row.similarity) for row in result]

    async def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = None,
        threshold: float = None,
        category: Optional[str] = None,
        active_only: bool = True,
        vector_weight: float = 0.7,
    ) -> List[Tuple[Tool, float]]:
        """
        Perform hybrid search combining vector similarity and full-text search.

        Combines vector similarity (70%) with PostgreSQL full-text search (30%)
        for improved relevance.

        Args:
            query_embedding: Query vector embedding
            query_text: Query text for full-text search
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            category: Optional category filter
            active_only: Only return active tools
            vector_weight: Weight for vector similarity (0.0-1.0), default 0.7

        Returns:
            List of (Tool, combined_score) tuples, ordered by score (descending)
        """
        if limit is None:
            limit = settings.DEFAULT_SEARCH_LIMIT
        if threshold is None:
            threshold = settings.DEFAULT_SIMILARITY_THRESHOLD

        text_weight = 1.0 - vector_weight

        # Create full-text search query
        # Combine name and description for text search
        ts_query = func.plainto_tsquery("english", query_text)

        # Build hybrid query
        stmt = select(
            Tool,
            (
                # Vector similarity (0-1 range)
                vector_weight * (1 - (Tool.embedding.cosine_distance(query_embedding) / 2)) +
                # Text similarity (0-1 range, using ts_rank_cd normalized)
                text_weight * func.ts_rank_cd(
                    func.to_tsvector("english", Tool.name + " " + Tool.description),
                    ts_query,
                    32  # normalization flag: divide by document length
                )
            ).label("score")
        ).where(
            Tool.embedding.isnot(None)
        )

        # Apply filters
        if active_only:
            stmt = stmt.where(Tool.is_active == True)
        if category:
            stmt = stmt.where(Tool.category == category)

        # Filter by threshold (applied to combined score)
        stmt = stmt.where(
            (
                vector_weight * (1 - (Tool.embedding.cosine_distance(query_embedding) / 2)) +
                text_weight * func.ts_rank_cd(
                    func.to_tsvector("english", Tool.name + " " + Tool.description),
                    ts_query,
                    32
                )
            ) >= threshold
        )

        # Order by combined score (descending)
        stmt = stmt.order_by(text("score DESC"))
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return [(row.Tool, row.score) for row in result]

    async def find_similar_tools(
        self,
        tool_id: int,
        limit: int = 5,
        threshold: float = None,
        exclude_self: bool = True,
    ) -> List[Tuple[Tool, float]]:
        """
        Find tools similar to a given tool based on embeddings.

        Args:
            tool_id: ID of the tool to find similar tools for
            limit: Maximum number of similar tools to return
            threshold: Minimum similarity threshold
            exclude_self: Whether to exclude the query tool from results

        Returns:
            List of (Tool, similarity_score) tuples

        Raises:
            ValueError: If tool not found or has no embedding
        """
        if threshold is None:
            threshold = settings.DEFAULT_SIMILARITY_THRESHOLD

        # Validate parameters
        threshold = validate_similarity_threshold(threshold)
        if limit <= 0 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        # Get the source tool
        stmt = select(Tool).where(Tool.id == tool_id)
        result = await self.session.execute(stmt)
        source_tool = result.scalar_one_or_none()

        if not source_tool:
            raise ValueError(f"Tool with id {tool_id} not found")
        if not source_tool.embedding:
            raise ValueError(f"Tool {tool_id} has no embedding")

        # Perform semantic search using the tool's embedding
        results = await self.semantic_search(
            query_embedding=source_tool.embedding,
            limit=limit + (1 if exclude_self else 0),  # +1 to account for self
            threshold=threshold,
            active_only=True,
        )

        # Filter out self if requested
        if exclude_self:
            results = [(tool, score) for tool, score in results if tool.id != tool_id]

        return results[:limit]

    async def get_tools_without_embeddings(
        self,
        limit: int = 100,
        active_only: bool = True,
    ) -> List[Tool]:
        """
        Get tools that don't have embeddings yet.

        Useful for batch re-indexing or finding tools that need embedding.

        Args:
            limit: Maximum number of tools to return
            active_only: Only return active tools

        Returns:
            List of Tool objects without embeddings
        """
        stmt = select(Tool).where(Tool.embedding.is_(None))

        if active_only:
            stmt = stmt.where(Tool.is_active == True)

        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_indexed_tools(self, active_only: bool = True) -> int:
        """
        Count tools that have been indexed (have embeddings).

        Args:
            active_only: Only count active tools

        Returns:
            Number of indexed tools
        """
        stmt = select(func.count(Tool.id)).where(Tool.embedding.isnot(None))

        if active_only:
            stmt = stmt.where(Tool.is_active == True)

        result = await self.session.execute(stmt)
        return result.scalar() or 0
