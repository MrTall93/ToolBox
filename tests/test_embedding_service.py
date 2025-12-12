"""Comprehensive tests for enhanced embedding service."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import List, Dict, Any

from app.registry.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    get_cache_key,
    get_embedding_cache,
    _CACHE_STATS,
)
from app.registry.embedding_client import EmbeddingClient
from app.config import settings


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock embedding client."""
        client = AsyncMock(spec=EmbeddingClient)
        client.endpoint_url = "https://mock-embedding.com/v1/embed"
        client.api_key = "test-key"
        client.timeout = 30.0
        client.dimension = 1536
        return client

    @pytest.fixture
    def embedding_service(self, mock_client):
        """Create embedding service with mock client."""
        return EmbeddingService(
            client=mock_client,
            max_batch_size=2,
            max_retries=2,
            base_delay=0.1,  # Fast retries for tests
        )

    @pytest.fixture
    def sample_embeddings(self):
        """Sample embedding vectors for testing."""
        return [
            [0.1, 0.2, 0.3] + [0.0] * 1533,
            [0.4, 0.5, 0.6] + [0.0] * 1533,
        ]

    def test_get_cache_key(self):
        """Test cache key generation."""
        text1 = "Hello world"
        text2 = "Hello world"
        text3 = "Different text"

        key1 = get_cache_key(text1)
        key2 = get_cache_key(text2)
        key3 = get_cache_key(text3)

        assert key1 == key2  # Same text should have same key
        assert key1 != key3  # Different text should have different key
        assert len(key1) == 32  # MD5 hash length

    @pytest.mark.asyncio
    async def test_embed_text_basic(self, embedding_service, mock_client, sample_embeddings):
        """Test basic text embedding."""
        text = "Test text for embedding"
        mock_client.embed_text.return_value = sample_embeddings[0]

        result = await embedding_service.embed_text(text)

        assert result == sample_embeddings[0]
        mock_client.embed_text.assert_called_once_with(text)

    @pytest.mark.asyncio
    async def test_embed_text_empty(self, embedding_service):
        """Test embedding empty text raises error."""
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            await embedding_service.embed_text("")

        with pytest.raises(ValueError, match="Cannot embed empty text"):
            await embedding_service.embed_text("   ")

    @pytest.mark.asyncio
    async def test_embed_text_caching(self, embedding_service, mock_client, sample_embeddings):
        """Test embedding caching."""
        text = "Test text for caching"
        mock_client.embed_text.return_value = sample_embeddings[0]

        # First call should hit the client
        result1 = await embedding_service.embed_text(text)
        assert result1 == sample_embeddings[0]
        assert mock_client.embed_text.call_count == 1

        # Second call should use cache
        result2 = await embedding_service.embed_text(text)
        assert result2 == sample_embeddings[0]
        assert mock_client.embed_text.call_count == 1  # No additional calls

        # Verify cache stats
        stats = embedding_service.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1

    @pytest.mark.asyncio
    async def test_embed_text_no_cache(self, embedding_service, mock_client, sample_embeddings):
        """Test embedding with caching disabled."""
        text = "Test text without cache"
        mock_client.embed_text.return_value = sample_embeddings[0]

        # First call
        result1 = await embedding_service.embed_text(text, use_cache=False)
        assert result1 == sample_embeddings[0]
        assert mock_client.embed_text.call_count == 1

        # Second call should still hit client
        result2 = await embedding_service.embed_text(text, use_cache=False)
        assert result2 == sample_embeddings[0]
        assert mock_client.embed_text.call_count == 2

    @pytest.mark.asyncio
    async def test_embed_batch_basic(self, embedding_service, mock_client, sample_embeddings):
        """Test basic batch embedding."""
        texts = ["Text 1", "Text 2"]
        mock_client.embed_batch.return_value = sample_embeddings

        result = await embedding_service.embed_batch(texts)

        assert result == sample_embeddings
        mock_client.embed_batch.assert_called_once_with(texts)

    @pytest.mark.asyncio
    async def test_embed_batch_with_caching(
        self, embedding_service, mock_client, sample_embeddings
    ):
        """Test batch embedding with partial cache hits."""
        texts = ["Text 1", "Text 2", "Text 3"]
        mock_client.embed_batch.return_value = [sample_embeddings[0], sample_embeddings[1]]

        # First call - all should hit client
        result1 = await embedding_service.embed_batch(texts, batch_size=2)
        assert len(result1) == 3
        assert mock_client.embed_batch.call_count == 2  # Split into 2 batches

        # Second call - should use cache for previous results
        result2 = await embedding_service.embed_batch(texts)
        assert result2 == result1
        # No additional client calls for cached items
        assert mock_client.embed_batch.call_count == 2

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self, embedding_service):
        """Test embedding empty list."""
        result = await embedding_service.embed_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_batch_large(self, embedding_service, mock_client):
        """Test embedding large batch gets split."""
        texts = ["Text 1", "Text 2", "Text 3", "Text 4"]
        mock_client.embed_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

        result = await embedding_service.embed_batch(texts, batch_size=2)

        # Should be called twice for 2 batches of size 2
        assert mock_client.embed_batch.call_count == 2
        assert len(result) == 4

    @pytest.mark.asyncio
    async def test_embed_tool(self, embedding_service, mock_client, sample_embeddings):
        """Test tool embedding generation."""
        tool_data = {
            "name": "Calculator",
            "description": "Performs mathematical calculations",
            "category": "Utility",
            "tags": ["math", "calculator"],
            "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}}
        }
        mock_client.embed_text.return_value = sample_embeddings[0]

        result = await embedding_service.embed_tool(tool_data)

        assert result == sample_embeddings[0]
        # Verify the tool metadata was combined into text
        call_args = mock_client.embed_text.call_args[0][0]
        assert "Calculator" in call_args
        assert "mathematical calculations" in call_args
        assert "Utility" in call_args
        assert "math" in call_args

    @pytest.mark.asyncio
    async def test_retry_logic(self, embedding_service, mock_client, sample_embeddings):
        """Test exponential backoff retry logic."""
        text = "Test retry logic"

        # Configure mock to fail twice then succeed
        mock_client.embed_text.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            sample_embeddings[0]
        ]

        result = await embedding_service.embed_text(text)

        assert result == sample_embeddings[0]
        assert mock_client.embed_text.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_failure(self, embedding_service, mock_client):
        """Test retry failure after max attempts."""
        text = "Test retry failure"

        # Configure mock to always fail
        mock_client.embed_text.side_effect = Exception("Persistent error")

        with pytest.raises(Exception, match="Persistent error"):
            await embedding_service.embed_text(text)

        assert mock_client.embed_text.call_count == 3  # Max retries

    @pytest.mark.asyncio
    async def test_circuit_breaker(self, embedding_service, mock_client):
        """Test circuit breaker functionality."""
        # Configure mock to always fail
        mock_client.embed_text.side_effect = Exception("Service down")

        # Make enough failures to trigger circuit breaker
        with pytest.raises(Exception):
            await embedding_service.embed_text("test1")
        with pytest.raises(Exception):
            await embedding_service.embed_text("test2")
        with pytest.raises(Exception):
            await embedding_service.embed_text("test3")
        with pytest.raises(Exception):
            await embedding_service.embed_text("test4")
        with pytest.raises(Exception):
            await embedding_service.embed_text("test5")

        # Circuit should now be open
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await embedding_service.embed_text("test6")

        # Verify circuit breaker state
        assert embedding_service._circuit_open is True
        assert embedding_service._failure_count >= 5

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self, embedding_service, mock_client, sample_embeddings):
        """Test circuit breaker reset on success."""
        # Trigger circuit breaker
        mock_client.embed_text.side_effect = Exception("Service down")

        for i in range(6):
            with pytest.raises(Exception):
                await embedding_service.embed_text(f"test{i}")

        assert embedding_service._circuit_open is True

        # Reset circuit breaker
        embedding_service.reset_circuit_breaker()
        assert embedding_service._circuit_open is False
        assert embedding_service._failure_count == 0

    @pytest.mark.asyncio
    async def test_health_check(self, embedding_service, mock_client):
        """Test comprehensive health check."""
        mock_client.health_check.return_value = True

        health = await embedding_service.health_check()

        assert health["status"] == "healthy"
        assert health["client_available"] is True
        assert health["circuit_breaker_open"] is False
        assert health["cache_enabled"] is True
        assert "cache_stats" in health

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, embedding_service, mock_client):
        """Test health check when service is unhealthy."""
        mock_client.health_check.return_value = False

        health = await embedding_service.health_check()

        assert health["status"] == "degraded"
        assert health["client_available"] is False
        assert "error" in health

    @pytest.mark.asyncio
    async def test_health_check_circuit_open(self, embedding_service, mock_client):
        """Test health check when circuit breaker is open."""
        # Open circuit breaker
        embedding_service._circuit_open = True
        mock_client.health_check.return_value = True

        health = await embedding_service.health_check()

        assert health["status"] == "unhealthy"
        assert health["circuit_breaker_open"] is True
        assert "circuit breaker open" in health["error"]

    def test_cache_stats(self, embedding_service):
        """Test cache statistics collection."""
        stats = embedding_service.get_cache_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "errors" in stats
        assert "total_requests" in stats
        assert "hit_rate" in stats
        assert "cache_size" in stats
        assert "cache_utilization" in stats

    def test_reset_cache_stats(self, embedding_service):
        """Test resetting cache statistics."""
        # Manually increment some stats
        global _CACHE_STATS
        _CACHE_STATS["hits"] = 10
        _CACHE_STATS["misses"] = 5
        _CACHE_STATS["errors"] = 1
        _CACHE_STATS["total_requests"] = 16

        stats_before = embedding_service.get_cache_stats()
        assert stats_before["hits"] == 10

        embedding_service.reset_cache_stats()

        stats_after = embedding_service.get_cache_stats()
        assert stats_after["hits"] == 0
        assert stats_after["misses"] == 0
        assert stats_after["errors"] == 0
        assert stats_after["total_requests"] == 0

    def test_clear_cache(self, embedding_service):
        """Test cache clearing."""
        # Add something to cache (simulate)
        if embedding_service.cache:
            embedding_service.cache["test_key"] = [0.1, 0.2]
            assert len(embedding_service.cache) > 0

            embedding_service.clear_cache()
            assert len(embedding_service.cache) == 0

    @pytest.mark.asyncio
    async def test_create_tool_text(self, embedding_service):
        """Test tool text representation creation."""
        tool_data = {
            "name": "Test Tool",
            "description": "A test tool for testing",
            "category": "Testing",
            "tags": ["test", "tool"],
            "input_schema": {"type": "object"}
        }

        text = embedding_service._create_tool_text(tool_data)

        assert "Test Tool" in text
        assert "A test tool for testing" in text
        assert "Testing" in text
        assert "test" in text
        assert "tool" in text
        assert "object" in text

    def test_get_embedding_service_singleton(self):
        """Test singleton pattern for embedding service."""
        service1 = get_embedding_service()
        service2 = get_embedding_service()

        assert service1 is service2  # Same instance

    @patch('app.registry.embedding_service.settings.ENABLE_EMBEDDING_CACHE', False)
    def test_cache_disabled(self):
        """Test behavior when cache is disabled."""
        service = EmbeddingService()

        # Cache should be disabled
        assert settings.ENABLE_EMBEDDING_CACHE is False

        # Should still work without errors
        stats = service.get_cache_stats()
        assert stats["cache_size"] == 0
        assert stats["cache_utilization"] == 0.0

    @pytest.mark.asyncio
    async def test_embedding_service_with_real_client(self):
        """Test embedding service with a real client mock."""
        # Create a more realistic mock
        mock_client = Mock()
        mock_client.endpoint_url = "https://api.openai.com/v1/embeddings"
        mock_client.api_key = "sk-test"
        mock_client.timeout = 30.0
        mock_client.dimension = 1536

        # Mock successful embedding response
        test_embedding = [0.1] * 1536
        mock_client.embed_text = AsyncMock(return_value=test_embedding)
        mock_client.embed_batch = AsyncMock(return_value=[test_embedding])
        mock_client.health_check = AsyncMock(return_value=True)

        service = EmbeddingService(client=mock_client)

        # Test embedding
        result = await service.embed_text("test text")
        assert result == test_embedding
        assert len(result) == 1536

        # Test batch
        results = await service.embed_batch(["text1", "text2"])
        assert len(results) == 2
        assert all(len(r) == 1536 for r in results)

        # Test tool embedding
        tool_data = {"name": "Test", "description": "Test tool"}
        tool_embedding = await service.embed_tool(tool_data)
        assert tool_embedding == test_embedding

        # Test health check
        health = await service.health_check()
        assert health["status"] == "healthy"
        assert health["client_available"] is True


class TestEmbeddingServiceIntegration:
    """Integration tests for embedding service."""

    @pytest.mark.asyncio
    async def test_end_to_end_embedding_flow(self):
        """Test complete embedding flow with mocked external service."""
        # Mock the external service call
        with patch('httpx.AsyncClient.post') as mock_post:
            # Setup mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "embeddings": [[0.1, 0.2, 0.3] + [0.0] * 1533]
            }
            mock_post.return_value = mock_response

            # Create real client and service
            client = EmbeddingClient(
                endpoint_url="https://mock-api.com/v1/embeddings",
                api_key="test-key"
            )
            service = EmbeddingService(client=client)

            # Test embedding flow
            result = await service.embed_text("test integration")

            # Verify result
            assert len(result) == 1536
            assert result[0] == 0.1
            assert result[1] == 0.2
            assert result[2] == 0.3

            # Verify external service was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "texts" in call_args[1]["json"]


if __name__ == "__main__":
    pytest.main([__file__])