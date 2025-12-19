"""
Integration tests for the call_tool_summarized feature.

These tests verify the full flow from MCP tool call through summarization.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.services.summarization import (
    SummarizationService,
    estimate_tokens,
    serialize_output,
    get_summarization_service,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def summarization_service():
    """Create a summarization service for testing."""
    return SummarizationService(
        litellm_url="http://test-litellm:4000",
        litellm_api_key="test-key",
        model="test-model",
        timeout=10.0,
    )


@pytest.fixture
def small_output():
    """Output that should NOT trigger summarization (small)."""
    return {
        "status": "ok",
        "data": {"id": 123, "name": "test"},
    }


@pytest.fixture
def large_output():
    """Output that SHOULD trigger summarization (large)."""
    # Create output that's definitely over 2000 tokens (~8000 chars)
    return {
        "results": [
            {
                "id": i,
                "title": f"Document Title {i}",
                "content": f"This is a very long document content section number {i}. " * 50,
                "metadata": {
                    "author": f"Author {i}",
                    "created": "2024-01-01",
                    "tags": ["tag1", "tag2", "tag3"],
                }
            }
            for i in range(20)
        ]
    }


@pytest.fixture
def mock_litellm_response():
    """Mock successful LiteLLM response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Summary: Found 20 documents related to the query. Key documents include..."
                }
            }
        ]
    }


# ============================================================================
# Unit Tests - Helper Functions
# ============================================================================

class TestEstimateTokens:
    """Tests for the estimate_tokens function."""

    def test_empty_string_returns_zero(self):
        """Empty string should return 0 tokens."""
        assert estimate_tokens("") == 0

    def test_none_returns_zero(self):
        """None should return 0 tokens."""
        assert estimate_tokens(None) == 0

    def test_short_string(self):
        """Short string should return approximate token count."""
        # "hello world" = 11 chars / 4 ≈ 2-3 tokens
        result = estimate_tokens("hello world")
        assert 2 <= result <= 3

    def test_long_string(self):
        """Long string should scale proportionally."""
        # 4000 chars / 4 = 1000 tokens
        text = "a" * 4000
        assert estimate_tokens(text) == 1000

    def test_unicode_string(self):
        """Unicode strings should still work."""
        text = "こんにちは世界" * 100
        result = estimate_tokens(text)
        assert result > 0


class TestSerializeOutput:
    """Tests for the serialize_output function."""

    def test_string_passthrough(self):
        """String input should pass through unchanged."""
        assert serialize_output("hello") == "hello"

    def test_dict_to_json(self):
        """Dict should be converted to JSON string."""
        result = serialize_output({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_list_to_json(self):
        """List should be converted to JSON string."""
        result = serialize_output([1, 2, 3])
        assert result == "[\n  1,\n  2,\n  3\n]"

    def test_nested_structure(self):
        """Nested structures should serialize correctly."""
        data = {"outer": {"inner": [1, 2, 3]}}
        result = serialize_output(data)
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == [1, 2, 3]

    def test_non_serializable_fallback(self):
        """Non-serializable objects should fall back to str()."""
        class CustomObj:
            def __str__(self):
                return "custom_object"

        result = serialize_output(CustomObj())
        assert "custom_object" in result


# ============================================================================
# Unit Tests - SummarizationService
# ============================================================================

class TestSummarizationService:
    """Tests for the SummarizationService class."""

    def test_initialization_with_defaults(self):
        """Service should initialize with default settings."""
        # Patch settings to avoid needing real config
        with patch('app.services.summarization.settings') as mock_settings:
            mock_settings.LITELLM_MCP_SERVER_URL = "http://default:4000"
            mock_settings.LITELLM_MCP_API_KEY = None
            mock_settings.SUMMARIZATION_MODEL = "claude-3-5-haiku-latest"
            mock_settings.SUMMARIZATION_TIMEOUT = 30.0
            mock_settings.SUMMARIZATION_MAX_INPUT_CHARS = 50000
            mock_settings.SUMMARIZATION_ENABLED = True

            service = SummarizationService()
            assert service.litellm_url == "http://default:4000"
            assert service.model == "claude-3-5-haiku-latest"
            assert service.timeout == 30.0
            assert service.max_input_chars == 50000
            assert service.enabled is True

    def test_initialization_with_custom_values(self):
        """Service should accept custom initialization values."""
        service = SummarizationService(
            litellm_url="http://custom:5000",
            litellm_api_key="custom-key",
            model="custom-model",
            timeout=60.0,
        )
        assert service.litellm_url == "http://custom:5000"
        assert service.litellm_api_key == "custom-key"
        assert service.model == "custom-model"
        assert service.timeout == 60.0

    @pytest.mark.asyncio
    async def test_summarize_if_needed_small_output(
        self, summarization_service, small_output
    ):
        """Small output should not be summarized."""
        content, was_summarized = await summarization_service.summarize_if_needed(
            content=small_output,
            max_tokens=2000,
        )

        assert was_summarized is False
        # Content should be serialized but not summarized
        assert "status" in content
        assert "ok" in content

    @pytest.mark.asyncio
    async def test_summarize_if_needed_large_output(
        self, summarization_service, large_output, mock_litellm_response
    ):
        """Large output should be summarized."""
        # Mock the HTTP client to return our mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_litellm_response

        with patch('app.services.summarization.create_http_client') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            content, was_summarized = await summarization_service.summarize_if_needed(
                content=large_output,
                max_tokens=500,  # Low threshold to trigger summarization
            )

            assert was_summarized is True
            assert "Summary:" in content

    @pytest.mark.asyncio
    async def test_summarize_with_context(
        self, summarization_service, mock_litellm_response
    ):
        """Context should be included in summarization request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_litellm_response

        captured_payload = None

        async def capture_post(url, json, headers):
            nonlocal captured_payload
            captured_payload = json
            return mock_response

        with patch('app.services.summarization.create_http_client') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(side_effect=capture_post)
            mock_client.return_value = mock_context

            await summarization_service.summarize(
                content="Large content here" * 100,
                user_query="Focus on errors",
                tool_name="test_tool",
            )

            # Verify context was included in the prompt
            assert captured_payload is not None
            user_message = captured_payload["messages"][1]["content"]
            assert "Focus on errors" in user_message
            assert "test_tool" in user_message

    @pytest.mark.asyncio
    async def test_summarize_handles_http_error(self, summarization_service):
        """HTTP errors should raise RuntimeError."""
        import httpx

        with patch('app.services.summarization.create_http_client') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )
            mock_client.return_value = mock_context

            with pytest.raises(RuntimeError, match="HTTP error"):
                await summarization_service.summarize(
                    content="Test content",
                )

    @pytest.mark.asyncio
    async def test_summarize_if_needed_fallback_on_error(
        self, summarization_service, large_output
    ):
        """Should fall back to truncation if summarization fails."""
        with patch('app.services.summarization.create_http_client') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Summarization failed")
            )
            mock_client.return_value = mock_context

            content, was_summarized = await summarization_service.summarize_if_needed(
                content=large_output,
                max_tokens=100,  # Very low to trigger summarization
            )

            # Should fall back to truncation
            assert was_summarized is True
            assert "[Output truncated" in content or len(content) < len(json.dumps(large_output))


# ============================================================================
# Integration Tests - MCP Tool
# ============================================================================

class TestCallToolSummarizedIntegration:
    """Integration tests for call_tool_summarized MCP tool."""

    @pytest.mark.asyncio
    async def test_full_flow_small_output(self):
        """Test full flow with small output (no summarization)."""
        from app.mcp_fastmcp_server import call_tool_summarized

        # Mock the database session and tool registry
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.is_active = True

        mock_result = {
            "success": True,
            "output": {"status": "ok"},
            "execution_time_ms": 100,
        }

        with patch('app.mcp_fastmcp_server.AsyncSessionLocal') as mock_session, \
             patch('app.mcp_fastmcp_server.ToolRegistry') as mock_registry, \
             patch('app.mcp_fastmcp_server.ToolExecutor') as mock_executor, \
             patch('app.services.summarization.settings') as mock_settings:

            # Setup settings
            mock_settings.SUMMARIZATION_ENABLED = True

            # Setup mocks
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            registry_instance = AsyncMock()
            registry_instance.get_tool_by_name = AsyncMock(return_value=mock_tool)
            mock_registry.return_value = registry_instance

            executor_instance = AsyncMock()
            executor_instance.execute_tool = AsyncMock(return_value=mock_result)
            mock_executor.return_value = executor_instance

            # Call the tool
            result = await call_tool_summarized(
                tool_name="test_tool",
                arguments={"arg": "value"},
                max_tokens=2000,
            )

            assert result["success"] is True
            assert result["was_summarized"] is False
            assert result["tool_name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_full_flow_tool_not_found(self):
        """Test flow when tool is not found."""
        from app.mcp_fastmcp_server import call_tool_summarized

        with patch('app.mcp_fastmcp_server.AsyncSessionLocal') as mock_session, \
             patch('app.mcp_fastmcp_server.ToolRegistry') as mock_registry:

            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            registry_instance = AsyncMock()
            registry_instance.get_tool_by_name = AsyncMock(return_value=None)
            registry_instance.find_tool = AsyncMock(return_value=[])
            mock_registry.return_value = registry_instance

            result = await call_tool_summarized(
                tool_name="nonexistent",
                arguments={},
            )

            assert result["success"] is False
            assert "not found" in result["error"]
            assert result["was_summarized"] is False

    @pytest.mark.asyncio
    async def test_full_flow_with_summarization(self):
        """Test full flow with summarization enabled and triggered."""
        from app.mcp_fastmcp_server import call_tool_summarized

        # Mock the database session and tool registry
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.is_active = True

        # Create large output
        large_output = {"data": "x" * 10000}  # Large enough to trigger summarization
        mock_result = {
            "success": True,
            "output": large_output,
            "execution_time_ms": 100,
        }

        # Mock litellm response
        mock_litellm_response = {
            "choices": [
                {"message": {"content": "Summarized content"}}
            ]
        }

        with patch('app.mcp_fastmcp_server.AsyncSessionLocal') as mock_session, \
             patch('app.mcp_fastmcp_server.ToolRegistry') as mock_registry, \
             patch('app.mcp_fastmcp_server.ToolExecutor') as mock_executor, \
             patch('app.services.summarization.create_http_client') as mock_client, \
             patch('app.services.summarization.settings') as mock_settings:

            # Setup settings
            mock_settings.SUMMARIZATION_ENABLED = True
            mock_settings.LITELLM_MCP_SERVER_URL = "http://test:4000"
            mock_settings.LITELLM_MCP_API_KEY = None
            mock_settings.SUMMARIZATION_MODEL = "test-model"
            mock_settings.SUMMARIZATION_TIMEOUT = 30.0
            mock_settings.SUMMARIZATION_MAX_INPUT_CHARS = 50000

            # Setup mocks
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            registry_instance = AsyncMock()
            registry_instance.get_tool_by_name = AsyncMock(return_value=mock_tool)
            mock_registry.return_value = registry_instance

            executor_instance = AsyncMock()
            executor_instance.execute_tool = AsyncMock(return_value=mock_result)
            mock_executor.return_value = executor_instance

            # Mock HTTP client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_litellm_response

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            # Call the tool
            result = await call_tool_summarized(
                tool_name="test_tool",
                arguments={"arg": "value"},
                max_tokens=500,  # Low threshold to trigger summarization
            )

            assert result["success"] is True
            assert result["was_summarized"] is True
            assert result["tool_name"] == "test_tool"
            assert "original_tokens_estimate" in result
            assert "summarized_tokens_estimate" in result
            assert result["output"] == "Summarized content"


# ============================================================================
# Tests - Global Instance
# ============================================================================

class TestGetSummarizationService:
    """Tests for the get_summarization_service function."""

    def test_returns_singleton(self):
        """Should return the same instance on multiple calls."""
        # Reset the global instance first
        import app.services.summarization as summarization_module
        summarization_module._summarization_service = None

        with patch('app.services.summarization.settings') as mock_settings:
            mock_settings.LITELLM_MCP_SERVER_URL = "http://test:4000"
            mock_settings.LITELLM_MCP_API_KEY = None
            mock_settings.SUMMARIZATION_MODEL = "test-model"
            mock_settings.SUMMARIZATION_TIMEOUT = 30.0
            mock_settings.SUMMARIZATION_MAX_INPUT_CHARS = 50000
            mock_settings.SUMMARIZATION_ENABLED = True

            service1 = get_summarization_service()
            service2 = get_summarization_service()

            assert service1 is service2