"""
Tests for EmbeddingClient batch embedding functionality.

These tests verify that the batch embedding bug fix works correctly:
- All texts in a batch are processed
- Each text receives its own unique embedding
- Fallback to sequential processing works
- Different response formats are handled
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from app.registry.embedding_client import EmbeddingClient
from app.config import settings


class TestEmbedBatchProcessingFix:
    """Tests for the batch embedding processing bug fix."""

    @pytest.mark.asyncio
    async def test_embed_batch_processes_all_texts(self):
        """Verify all texts in batch are processed and each gets unique embedding."""
        client = EmbeddingClient()
        texts = ["hello", "world", "test"]

        # Mock the HTTP response
        mock_response = {
            "data": [
                {"embedding": [0.1] * settings.EMBEDDING_DIMENSION, "index": 0},
                {"embedding": [0.2] * settings.EMBEDDING_DIMENSION, "index": 1},
                {"embedding": [0.3] * settings.EMBEDDING_DIMENSION, "index": 2},
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)

            # Verify we got 3 distinct embeddings
            assert len(embeddings) == 3, "Should return 3 embeddings for 3 texts"

            # Verify each embedding is unique
            assert embeddings[0] != embeddings[1]
            assert embeddings[1] != embeddings[2]
            assert embeddings[0] != embeddings[2]

            # Verify the payload sent includes ALL texts
            call_args = mock_post.call_args
            sent_payload = call_args.kwargs['json']
            assert sent_payload['input'] == texts, "Should send all texts in input array"

    @pytest.mark.asyncio
    async def test_embed_batch_maintains_order(self):
        """Verify embedding order matches input order."""
        client = EmbeddingClient()
        texts = ["first", "second", "third"]

        # Mock response with explicit indices
        mock_response = {
            "data": [
                {"embedding": [0.3] * settings.EMBEDDING_DIMENSION, "index": 2},
                {"embedding": [0.1] * settings.EMBEDDING_DIMENSION, "index": 0},
                {"embedding": [0.2] * settings.EMBEDDING_DIMENSION, "index": 1},
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)

            # Verify order is correct (sorted by index)
            assert embeddings[0][0] == 0.1  # First text -> index 0
            assert embeddings[1][0] == 0.2  # Second text -> index 1
            assert embeddings[2][0] == 0.3  # Third text -> index 2

    @pytest.mark.asyncio
    async def test_embed_batch_single_text(self):
        """Verify batch works correctly with single text."""
        client = EmbeddingClient()
        texts = ["single text"]

        mock_response = {
            "data": [
                {"embedding": [0.5] * settings.EMBEDDING_DIMENSION, "index": 0}
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)

            assert len(embeddings) == 1
            assert len(embeddings[0]) == settings.EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self):
        """Verify empty batch returns empty list."""
        client = EmbeddingClient()

        embeddings = await client.embed_batch([])

        assert embeddings == []

    @pytest.mark.asyncio
    async def test_embed_batch_fallback_to_sequential(self):
        """Verify fallback to sequential processing when batch not supported."""
        client = EmbeddingClient()
        texts = ["hello", "world"]

        # First call (batch) fails with "batch not supported" error
        batch_error_response = Mock()
        batch_error_response.status_code = 400
        batch_error_response.json = lambda: {
            "error": "Expected string input, got array"
        }

        batch_error = httpx.HTTPStatusError(
            "Bad request",
            request=Mock(),
            response=batch_error_response
        )

        # Sequential calls succeed
        sequential_responses = [
            {"data": [{"embedding": [0.1] * settings.EMBEDDING_DIMENSION}]},
            {"data": [{"embedding": [0.2] * settings.EMBEDDING_DIMENSION}]},
        ]

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call (batch attempt) fails
                raise batch_error
            else:
                # Sequential calls succeed
                idx = call_count - 2
                mock_resp = AsyncMock(
                    status_code=200,
                    json=lambda i=idx: sequential_responses[i]
                )
                mock_resp.raise_for_status = Mock()
                return mock_resp

        with patch.object(httpx.AsyncClient, 'post', side_effect=mock_post):
            embeddings = await client.embed_batch(texts)

            # Should have 2 embeddings from sequential processing
            assert len(embeddings) == 2
            assert embeddings[0][0] == 0.1
            assert embeddings[1][0] == 0.2

            # Verify we made 3 calls total (1 batch + 2 sequential)
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_embed_batch_dimension_validation(self):
        """Verify dimension mismatch is detected."""
        client = EmbeddingClient()
        texts = ["test"]

        # Response with wrong dimension
        mock_response = {
            "data": [
                {"embedding": [0.1] * 512, "index": 0}  # Wrong dimension
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            with pytest.raises(ValueError, match="dimension"):
                await client.embed_batch(texts)

    @pytest.mark.asyncio
    async def test_embed_batch_count_mismatch(self):
        """Verify count mismatch is detected."""
        client = EmbeddingClient()
        texts = ["text1", "text2", "text3"]

        # Response with wrong count (only 2 embeddings)
        mock_response = {
            "data": [
                {"embedding": [0.1] * settings.EMBEDDING_DIMENSION, "index": 0},
                {"embedding": [0.2] * settings.EMBEDDING_DIMENSION, "index": 1},
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            with pytest.raises(ValueError, match="Expected 3 embeddings, got 2"):
                await client.embed_batch(texts)


class TestEmbedBatchResponseFormats:
    """Tests for different embedding API response formats."""

    @pytest.mark.asyncio
    async def test_openai_format_with_index(self):
        """Test OpenAI format: {"data": [{"embedding": [...], "index": 0}]}"""
        client = EmbeddingClient()
        texts = ["a", "b"]

        mock_response = {
            "data": [
                {"embedding": [0.1] * settings.EMBEDDING_DIMENSION, "index": 0},
                {"embedding": [0.2] * settings.EMBEDDING_DIMENSION, "index": 1},
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)
            assert len(embeddings) == 2

    @pytest.mark.asyncio
    async def test_simple_embeddings_array_format(self):
        """Test simple format: {"embeddings": [[...], [...]]}"""
        client = EmbeddingClient()
        texts = ["a", "b"]

        mock_response = {
            "embeddings": [
                [0.1] * settings.EMBEDDING_DIMENSION,
                [0.2] * settings.EMBEDDING_DIMENSION,
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)
            assert len(embeddings) == 2

    @pytest.mark.asyncio
    async def test_lm_studio_format_without_index(self):
        """Test LM Studio format: {"data": [{"embedding": [...]}]} (no index)"""
        client = EmbeddingClient()
        texts = ["a", "b"]

        mock_response = {
            "data": [
                {"embedding": [0.1] * settings.EMBEDDING_DIMENSION},
                {"embedding": [0.2] * settings.EMBEDDING_DIMENSION},
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)
            assert len(embeddings) == 2

    @pytest.mark.asyncio
    async def test_direct_array_format(self):
        """Test direct array format: [[...], [...]]"""
        client = EmbeddingClient()
        texts = ["a", "b"]

        mock_response = [
            [0.1] * settings.EMBEDDING_DIMENSION,
            [0.2] * settings.EMBEDDING_DIMENSION,
        ]

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)
            assert len(embeddings) == 2

    @pytest.mark.asyncio
    async def test_single_embedding_object_format(self):
        """Test single embedding in object: {"embedding": [...]}"""
        client = EmbeddingClient()
        texts = ["single"]

        mock_response = {
            "embedding": [0.1] * settings.EMBEDDING_DIMENSION
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embeddings = await client.embed_batch(texts)
            assert len(embeddings) == 1

    @pytest.mark.asyncio
    async def test_invalid_format_raises_error(self):
        """Test that invalid response format raises clear error."""
        client = EmbeddingClient()
        texts = ["test"]

        mock_response = {
            "unexpected_field": "value"
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            with pytest.raises(ValueError, match="Unexpected response format"):
                await client.embed_batch(texts)


class TestEmbedTextDelegation:
    """Tests for embed_text delegation to embed_batch."""

    @pytest.mark.asyncio
    async def test_embed_text_uses_embed_batch(self):
        """Verify embed_text delegates to embed_batch correctly."""
        client = EmbeddingClient()

        mock_response = {
            "data": [
                {"embedding": [0.5] * settings.EMBEDDING_DIMENSION, "index": 0}
            ]
        }

        with patch.object(httpx.AsyncClient, 'post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            mock_post.return_value.raise_for_status = Mock()

            embedding = await client.embed_text("test text")

            # Verify single embedding returned
            assert len(embedding) == settings.EMBEDDING_DIMENSION
            assert embedding[0] == 0.5

            # Verify batch was called with single-item list
            call_args = mock_post.call_args
            sent_payload = call_args.kwargs['json']
            assert sent_payload['input'] == ["test text"]


class TestBatchNotSupportedDetection:
    """Tests for detecting when batch processing is not supported."""

    @pytest.mark.asyncio
    async def test_detects_batch_not_supported_from_error_message(self):
        """Verify detection of 'batch not supported' from error messages."""
        client = EmbeddingClient()

        error_messages = [
            "Expected string input, got array",
            "Batch processing is not supported",
            "Input must be a string, not a list",
            "Expected str, got list",
        ]

        for error_msg in error_messages:
            error_response = Mock()
            error_response.status_code = 400
            error_response.json = lambda msg=error_msg: {"error": msg}

            error = httpx.HTTPStatusError(
                "Bad request",
                request=Mock(),
                response=error_response
            )

            is_batch_error = client._is_batch_not_supported_error(error)
            assert is_batch_error, f"Should detect batch error from: {error_msg}"

    @pytest.mark.asyncio
    async def test_does_not_detect_other_errors_as_batch_errors(self):
        """Verify other errors are not mistaken for batch errors."""
        client = EmbeddingClient()

        other_errors = [
            ("Invalid API key", 401),
            ("Rate limit exceeded", 429),
            ("Model not found", 404),
            ("Internal server error", 500),
        ]

        for error_msg, status_code in other_errors:
            error_response = Mock()
            error_response.status_code = status_code
            error_response.json = lambda msg=error_msg: {"error": msg}

            error = httpx.HTTPStatusError(
                "Error",
                request=Mock(),
                response=error_response
            )

            is_batch_error = client._is_batch_not_supported_error(error)
            assert not is_batch_error, f"Should not detect as batch error: {error_msg}"


class TestConcurrentBatchProcessing:
    """Tests for concurrent batch embedding performance."""

    @pytest.mark.asyncio
    async def test_batch_faster_than_sequential_conceptually(self):
        """
        Conceptual test: Batch should be more efficient than sequential.

        Note: We can't easily measure real timing in mocked tests,
        but we verify batch makes fewer HTTP calls.
        """
        client = EmbeddingClient()
        texts = ["text1", "text2", "text3", "text4", "text5"]

        mock_response = {
            "data": [
                {"embedding": [0.1] * settings.EMBEDDING_DIMENSION, "index": i}
                for i in range(5)
            ]
        }

        call_count = 0

        async def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock(status_code=200, json=lambda: mock_response)
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch.object(httpx.AsyncClient, 'post', side_effect=count_calls):
            await client.embed_batch(texts)

            # Batch should make only 1 HTTP call, not 5
            assert call_count == 1, "Batch should make single HTTP call"
