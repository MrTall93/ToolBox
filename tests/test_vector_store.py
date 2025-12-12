"""Vector store tests."""
import pytest
from unittest.mock import AsyncMock, patch
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.registry.vector_store import VectorStore
from app.models.tool import Tool


class TestVectorStore:
    """Test VectorStore class methods."""

    @pytest.mark.asyncio
    async def test_vector_store_initialization(self, test_db_session):
        """Test VectorStore can be initialized."""
        vector_store = VectorStore(test_db_session)
        assert vector_store.session == test_db_session

    @pytest.mark.asyncio
    async def test_initialize_with_pgvector_extension(self, test_db_session):
        """Test initialize() method with pgvector extension available."""
        vector_store = VectorStore(test_db_session)

        # Mock pgvector extension check
        with patch.object(test_db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalar.return_value = 'vector'
            mock_execute.return_value = mock_result

            # Should not raise any exception
            await vector_store.initialize()

            # Should have checked for pgvector extension
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_pgvector_extension(self, test_db_session):
        """Test initialize() method fails without pgvector extension."""
        vector_store = VectorStore(test_db_session)

        # Mock no pgvector extension
        with patch.object(test_db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalar.return_value = None
            mock_execute.return_value = mock_result

            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="pgvector extension is not installed"):
                await vector_store.initialize()

    @pytest.mark.asyncio
    async def test_index_tool_success(self, test_db_session: AsyncSession, sample_tool):
        """Test successful tool indexing."""
        vector_store = VectorStore(test_db_session)
        embedding = [0.1] * 1536

        await vector_store.index_tool(sample_tool.id, embedding)

        # Verify embedding was saved
        await test_db_session.refresh(sample_tool)
        assert sample_tool.embedding == embedding

    @pytest.mark.asyncio
    async def test_index_tool_not_found(self, test_db_session: AsyncSession):
        """Test indexing non-existent tool."""
        vector_store = VectorStore(test_db_session)
        embedding = [0.1] * 1536

        with pytest.raises(ValueError, match="Tool with id 999 not found"):
            await vector_store.index_tool(999, embedding)

    @pytest.mark.asyncio
    async def test_index_tool_wrong_dimension(self, test_db_session: AsyncSession, sample_tool):
        """Test indexing tool with wrong embedding dimension."""
        vector_store = VectorStore(test_db_session)
        wrong_embedding = [0.1] * 100  # Wrong dimension

        with pytest.raises(ValueError, match="Embedding dimension 100 doesn't match"):
            await vector_store.index_tool(sample_tool.id, wrong_embedding)

    @pytest.mark.asyncio
    async def test_semantic_search_basic(self, test_db_session: AsyncSession, sample_tool_with_embedding):
        """Test basic semantic search."""
        vector_store = VectorStore(test_db_session)
        query_embedding = [0.1] * 1536

        results = await vector_store.semantic_search(
            query_embedding=query_embedding,
            limit=5,
            threshold=0.5
        )

        assert isinstance(results, list)
        assert len(results) >= 0
        # Each result should be (Tool, similarity_score) tuple
        for tool, score in results:
            assert isinstance(tool, Tool)
            assert isinstance(score, float)
            assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_semantic_search_with_category_filter(self, test_db_session: AsyncSession):
        """Test semantic search with category filter."""
        vector_store = VectorStore(test_db_session)

        # Create tools in different categories
        math_tool = Tool(
            name="math_tool",
            description="Math operations tool",
            category="math",
            tags=["math"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        math_tool.embedding = [0.1] * 1536

        text_tool = Tool(
            name="text_tool",
            description="Text processing tool",
            category="text",
            tags=["text"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        text_tool.embedding = [0.2] * 1536

        test_db_session.add_all([math_tool, text_tool])
        await test_db_session.commit()

        query_embedding = [0.1] * 1536

        # Search for math tools only
        results = await vector_store.semantic_search(
            query_embedding=query_embedding,
            category="math",
            limit=10
        )

        assert len(results) == 1
        assert results[0][0].category == "math"

    @pytest.mark.asyncio
    async def test_semantic_search_active_only(self, test_db_session: AsyncSession):
        """Test semantic search with active_only filter."""
        vector_store = VectorStore(test_db_session)

        # Create active and inactive tools
        active_tool = Tool(
            name="active_tool",
            description="Active tool",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function",
            is_active=True
        )
        active_tool.embedding = [0.1] * 1536

        inactive_tool = Tool(
            name="inactive_tool",
            description="Inactive tool",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function",
            is_active=False
        )
        inactive_tool.embedding = [0.2] * 1536

        test_db_session.add_all([active_tool, inactive_tool])
        await test_db_session.commit()

        query_embedding = [0.1] * 1536

        # Search with active_only=True
        results = await vector_store.semantic_search(
            query_embedding=query_embedding,
            active_only=True,
            limit=10
        )

        # Should only return active tools
        assert len(results) == 1
        assert results[0][0].is_active is True

    @pytest.mark.asyncio
    async def test_semantic_search_threshold(self, test_db_session: AsyncSession):
        """Test semantic search with similarity threshold."""
        vector_store = VectorStore(test_db_session)

        # Create a tool
        tool = Tool(
            name="test_tool",
            description="Test tool",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        # Use very different embedding to test threshold
        tool.embedding = [0.9] * 1536

        test_db_session.add(tool)
        await test_db_session.commit()

        # Search with similar embedding
        query_embedding = [0.1] * 1536

        # High threshold - should return no results
        results = await vector_store.semantic_search(
            query_embedding=query_embedding,
            threshold=0.9,  # Very high threshold
            limit=10
        )

        assert len(results) == 0

        # Low threshold - should return results
        results = await vector_store.semantic_search(
            query_embedding=query_embedding,
            threshold=0.1,  # Very low threshold
            limit=10
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_hybrid_search_basic(self, test_db_session: AsyncSession):
        """Test basic hybrid search."""
        vector_store = VectorStore(test_db_session)

        # Create a tool
        tool = Tool(
            name="calculator",
            description="A tool for mathematical calculations",
            category="math",
            tags=["math", "calculator"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        tool.embedding = [0.1] * 1536

        test_db_session.add(tool)
        await test_db_session.commit()

        query_embedding = [0.1] * 1536
        query_text = "calculator math"

        results = await vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=5
        )

        assert isinstance(results, list)
        # Each result should be (Tool, combined_score) tuple
        for tool, score in results:
            assert isinstance(tool, Tool)
            assert isinstance(score, float)
            assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_hybrid_search_weights(self, test_db_session: AsyncSession):
        """Test hybrid search with different weights."""
        vector_store = VectorStore(test_db_session)

        tool = Tool(
            name="text_processor",
            description="Process text documents",
            category="text",
            tags=["text", "process"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        tool.embedding = [0.1] * 1536

        test_db_session.add(tool)
        await test_db_session.commit()

        query_embedding = [0.1] * 1536
        query_text = "text"

        # Test with vector weight 0.9 (dominant vector search)
        results_vector = await vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            vector_weight=0.9
        )

        # Test with vector weight 0.1 (dominant text search)
        results_text = await vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            vector_weight=0.1
        )

        assert isinstance(results_vector, list)
        assert isinstance(results_text, list)

    @pytest.mark.asyncio
    async def test_find_similar_tools(self, test_db_session: AsyncSession, sample_tool_with_embedding):
        """Test finding similar tools."""
        vector_store = VectorStore(test_db_session)

        # Create similar tool
        similar_tool = Tool(
            name="similar_calculator",
            description="Another calculator tool",
            category="math",
            tags=["math", "calculator"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        similar_tool.embedding = [0.11] * 1536  # Very similar embedding

        test_db_session.add(similar_tool)
        await test_db_session.commit()

        results = await vector_store.find_similar_tools(
            tool_id=sample_tool_with_embedding.id,
            limit=5,
            exclude_self=True
        )

        assert isinstance(results, list)
        # Results should not include the source tool
        for tool, score in results:
            assert tool.id != sample_tool_with_embedding.id
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_find_similar_tools_include_self(self, test_db_session: AsyncSession, sample_tool_with_embedding):
        """Test finding similar tools including self."""
        vector_store = VectorStore(test_db_session)

        results = await vector_store.find_similar_tools(
            tool_id=sample_tool_with_embedding.id,
            limit=5,
            exclude_self=False
        )

        # Should include the source tool
        tool_ids = [tool.id for tool, _ in results]
        assert sample_tool_with_embedding.id in tool_ids

    @pytest.mark.asyncio
    async def test_find_similar_tools_not_found(self, test_db_session: AsyncSession):
        """Test finding similar tools for non-existent tool."""
        vector_store = VectorStore(test_db_session)

        with pytest.raises(ValueError, match="Tool with id 999 not found"):
            await vector_store.find_similar_tools(999)

    @pytest.mark.asyncio
    async def test_find_similar_tools_no_embedding(self, test_db_session: AsyncSession, sample_tool):
        """Test finding similar tools for tool without embedding."""
        vector_store = VectorStore(test_db_session)

        with pytest.raises(ValueError, match="has no embedding"):
            await vector_store.find_similar_tools(sample_tool.id)

    @pytest.mark.asyncio
    async def test_get_tools_without_embeddings(self, test_db_session: AsyncSession):
        """Test getting tools without embeddings."""
        vector_store = VectorStore(test_db_session)

        # Create tools with and without embeddings
        tool_with_embedding = Tool(
            name="tool_with_embedding",
            description="Has embedding",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        tool_with_embedding.embedding = [0.1] * 1536

        tool_without_embedding = Tool(
            name="tool_without_embedding",
            description="No embedding",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        # No embedding set

        test_db_session.add_all([tool_with_embedding, tool_without_embedding])
        await test_db_session.commit()

        results = await vector_store.get_tools_without_embeddings()

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].id == tool_without_embedding.id

    @pytest.mark.asyncio
    async def test_get_tools_without_embeddings_include_inactive(self, test_db_session: AsyncSession):
        """Test getting tools without embeddings including inactive tools."""
        vector_store = VectorStore(test_db_session)

        # Create inactive tool without embedding
        inactive_tool = Tool(
            name="inactive_tool",
            description="Inactive tool",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function",
            is_active=False
        )
        # No embedding set

        test_db_session.add(inactive_tool)
        await test_db_session.commit()

        # With active_only=True (default)
        results_active = await vector_store.get_tools_without_embeddings(active_only=True)
        assert len(results_active) == 0

        # With active_only=False
        results_all = await vector_store.get_tools_without_embeddings(active_only=False)
        assert len(results_all) == 1

    @pytest.mark.asyncio
    async def test_count_indexed_tools(self, test_db_session: AsyncSession):
        """Test counting indexed tools."""
        vector_store = VectorStore(test_db_session)

        # Create tools with and without embeddings
        tool1 = Tool(
            name="tool1",
            description="Tool 1",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        tool1.embedding = [0.1] * 1536

        tool2 = Tool(
            name="tool2",
            description="Tool 2",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        tool2.embedding = [0.2] * 1536

        tool3 = Tool(
            name="tool3",
            description="Tool 3",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        # No embedding

        test_db_session.add_all([tool1, tool2, tool3])
        await test_db_session.commit()

        count = await vector_store.count_indexed_tools()
        assert count == 2

        # Test including inactive tools
        count_all = await vector_store.count_indexed_tools(active_only=False)
        assert count_all == 2

    @pytest.mark.asyncio
    async def test_semantic_search_no_embeddings(self, test_db_session: AsyncSession):
        """Test semantic search when no tools have embeddings."""
        vector_store = VectorStore(test_db_session)

        # Create tool without embedding
        tool = Tool(
            name="no_embedding_tool",
            description="Tool without embedding",
            category="test",
            tags=["test"],
            input_schema={"type": "object"},
            implementation_type="python_function"
        )
        test_db_session.add(tool)
        await test_db_session.commit()

        query_embedding = [0.1] * 1536
        results = await vector_store.semantic_search(query_embedding=query_embedding)

        # Should return empty list
        assert results == []


class TestVectorStorePerformance:
    """Test vector store performance and benchmarks."""

    @pytest.mark.asyncio
    async def test_semantic_search_performance(self, test_db_session: AsyncSession):
        """Test semantic search performance with multiple tools."""
        vector_store = VectorStore(test_db_session)

        # Create multiple tools
        tools = []
        for i in range(10):
            tool = Tool(
                name=f"tool_{i}",
                description=f"Test tool number {i}",
                category="test",
                tags=["test", f"tag_{i}"],
                input_schema={"type": "object"},
                implementation_type="python_function"
            )
            # Create unique embedding for each tool
            embedding = [float(i) / 10] * 1536
            tool.embedding = embedding
            tools.append(tool)

        test_db_session.add_all(tools)
        await test_db_session.commit()

        import time
        start_time = time.time()

        query_embedding = [0.1] * 1536
        results = await vector_store.semantic_search(
            query_embedding=query_embedding,
            limit=5
        )

        elapsed_time = time.time() - start_time

        # Should complete quickly
        assert elapsed_time < 1.0  # Less than 1 second
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_hybrid_search_performance(self, test_db_session: AsyncSession):
        """Test hybrid search performance."""
        vector_store = VectorStore(test_db_session)

        # Create tools with both embeddings and text content
        tools = []
        categories = ["math", "text", "data", "api"]

        for i in range(20):
            category = categories[i % len(categories)]
            tool = Tool(
                name=f"{category}_tool_{i}",
                description=f"A {category} processing tool for various operations",
                category=category,
                tags=[category, f"tag_{i}"],
                input_schema={"type": "object"},
                implementation_type="python_function"
            )
            tool.embedding = [float(i) / 20] * 1536
            tools.append(tool)

        test_db_session.add_all(tools)
        await test_db_session.commit()

        import time
        start_time = time.time()

        query_embedding = [0.5] * 1536
        query_text = "math operations"
        results = await vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=10
        )

        elapsed_time = time.time() - start_time

        # Should complete quickly
        assert elapsed_time < 1.5  # Less than 1.5 seconds
        assert isinstance(results, list)

        # Results should be ordered by relevance
        if results:
            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True)


@pytest.fixture
async def sample_tool_with_embedding(test_db_session: AsyncSession, sample_embedding):
    """Create a sample tool with embedding for testing."""
    tool = Tool(
        name="test_tool_with_embedding",
        description="A test tool with embedding",
        category="test",
        tags=["test", "embedding"],
        input_schema={
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        },
        implementation_type="python_function"
    )
    tool.embedding = sample_embedding

    test_db_session.add(tool)
    await test_db_session.commit()
    await test_db_session.refresh(tool)
    return tool