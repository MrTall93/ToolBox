"""
Client for interacting with external embedding service.

Provides methods to generate embeddings from text using a user-configured
embedding endpoint.
"""
from typing import List, Optional, Dict, Any
import httpx
from app.config import settings


class EmbeddingClient:
    """
    Client for generating text embeddings via external API.

    The embedding service endpoint is configurable via environment variables,
    allowing users to bring their own embedding provider.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize embedding client.

        Args:
            endpoint_url: Override default embedding endpoint URL
            api_key: Override default API key
            timeout: Request timeout in seconds
        """
        self.endpoint_url = endpoint_url or settings.EMBEDDING_ENDPOINT_URL
        self.api_key = api_key or settings.EMBEDDING_API_KEY
        self.timeout = timeout
        self.dimension = settings.EMBEDDING_DIMENSION
        self.model = settings.EMBEDDING_MODEL

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response is invalid
        """
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Supports OpenAI-compatible APIs that accept array inputs.
        Falls back to sequential processing if batch fails.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response is invalid
        """
        if not texts:
            return []

        headers = self._build_headers()

        # Try batch processing first (send all texts as array)
        payload = {
            "input": texts,  # Send ALL texts as array
            "model": self.model
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Parse and validate batch response
                return self._parse_batch_response(data, texts)

            except httpx.HTTPStatusError as e:
                # Check if it's a "batch not supported" error
                if self._is_batch_not_supported_error(e):
                    # Fall back to sequential processing
                    return await self._embed_sequential(texts, headers, client)
                else:
                    # Re-raise other HTTP errors
                    raise Exception(
                        f"Failed to get embeddings from {self.endpoint_url}: {str(e)}"
                    ) from e

            except httpx.HTTPError as e:
                # Network errors - don't retry
                raise Exception(
                    f"Failed to connect to embedding service at {self.endpoint_url}: {str(e)}"
                ) from e

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for embedding requests."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _embed_sequential(
        self,
        texts: List[str],
        headers: Dict[str, str],
        client: httpx.AsyncClient
    ) -> List[List[float]]:
        """
        Fallback: Process texts one at a time.

        Used when the embedding service doesn't support batch processing.

        Args:
            texts: List of texts to embed
            headers: HTTP headers
            client: Async HTTP client

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for text in texts:
            payload = {"input": text, "model": self.model}

            try:
                response = await client.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Extract single embedding
                embedding = self._extract_single_embedding(data)
                embeddings.append(embedding)

            except httpx.HTTPError as e:
                raise Exception(
                    f"Failed to get embedding for text (sequential mode): {str(e)}"
                ) from e

        return embeddings

    def _parse_batch_response(
        self,
        data: dict,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Parse batch response and validate dimensions.

        Handles multiple response formats:
        - OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
        - Simple format: {"embeddings": [[...], [...]]}
        - LM Studio format: {"data": [{"embedding": [...]}]}

        Args:
            data: Response JSON data
            texts: Original texts (for validation)

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If response format is invalid or dimensions don't match
        """
        # Handle OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
        if "data" in data and isinstance(data["data"], list):
            # Check if items have "index" field for proper ordering
            has_index = len(data["data"]) > 0 and "index" in data["data"][0]

            if has_index:
                # Sort by index to ensure correct ordering
                sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
                embeddings = [item["embedding"] for item in sorted_data]
            else:
                # No index field, assume order matches input
                embeddings = [item["embedding"] for item in data["data"]]

        # Handle alternative formats
        elif "embeddings" in data:
            embeddings = data["embeddings"]

        elif "embedding" in data:
            # Single embedding wrapped in object
            embeddings = [data["embedding"]]

        elif isinstance(data, list):
            # Direct array response
            embeddings = data

        else:
            raise ValueError(
                f"Unexpected response format. Expected 'data' or 'embeddings' field. "
                f"Got keys: {list(data.keys())}"
            )

        # Validate count matches
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(embeddings)}. "
                f"This may indicate the API doesn't support batch processing."
            )

        # Validate dimensions
        for i, embedding in enumerate(embeddings):
            if not isinstance(embedding, list):
                raise ValueError(f"Embedding {i} is not a list: {type(embedding)}")

            if len(embedding) != self.dimension:
                raise ValueError(
                    f"Embedding {i} has dimension {len(embedding)}, "
                    f"expected {self.dimension}"
                )

        return embeddings

    def _extract_single_embedding(self, data: dict) -> List[float]:
        """
        Extract single embedding from response.

        Args:
            data: Response JSON data

        Returns:
            Single embedding vector

        Raises:
            ValueError: If response format is invalid
        """
        # OpenAI format
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            embedding = data["data"][0]["embedding"]

        # Simple format
        elif "embedding" in data:
            embedding = data["embedding"]

        # Array format
        elif "embeddings" in data and isinstance(data["embeddings"], list):
            embedding = data["embeddings"][0]

        else:
            raise ValueError(
                f"Cannot extract embedding from response. "
                f"Expected 'data', 'embedding', or 'embeddings' field. "
                f"Got keys: {list(data.keys())}"
            )

        # Validate dimension
        if len(embedding) != self.dimension:
            raise ValueError(
                f"Embedding has dimension {len(embedding)}, expected {self.dimension}"
            )

        return embedding

    def _is_batch_not_supported_error(self, error: httpx.HTTPStatusError) -> bool:
        """
        Check if error indicates batch processing isn't supported.

        Args:
            error: HTTP error from embedding service

        Returns:
            True if error suggests batch processing isn't supported
        """
        if error.response is None:
            return False

        # Check status code (some APIs return 400 for unsupported features)
        if error.response.status_code not in (400, 422):
            return False

        # Check error message
        try:
            data = error.response.json()
            error_msg = str(data.get("error", "")).lower()

            # Common error messages indicating batch not supported
            batch_indicators = [
                "batch",
                "array",
                "list",
                "multiple inputs",
                "expected string",
                "expected str",
            ]

            return any(indicator in error_msg for indicator in batch_indicators)

        except Exception:
            # Can't parse response, assume it's not a batch error
            return False

    async def embed_tool(self, tool_data: Dict[str, Any]) -> List[float]:
        """
        Generate embedding for a tool based on its metadata.

        Combines tool name, description, and tags into a single text
        representation for embedding.

        Args:
            tool_data: Dictionary with tool metadata (name, description, tags, etc.)

        Returns:
            Embedding vector for the tool
        """
        # Create a rich text representation of the tool
        parts = []

        # Add name (weighted more)
        if "name" in tool_data:
            parts.append(f"Tool: {tool_data['name']}")
            parts.append(tool_data['name'])  # Repeat for emphasis

        # Add description
        if "description" in tool_data:
            parts.append(tool_data['description'])

        # Add category
        if "category" in tool_data:
            parts.append(f"Category: {tool_data['category']}")

        # Add tags
        if "tags" in tool_data and tool_data['tags']:
            tags_str = ", ".join(tool_data['tags'])
            parts.append(f"Tags: {tags_str}")

        # Combine into single text
        text = " | ".join(parts)

        return await self.embed_text(text)

    async def health_check(self) -> bool:
        """
        Check if the embedding service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try a simple embedding request
            await self.embed_text("health check")
            return True
        except Exception:
            return False


# Singleton instance for convenience
_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    """
    Get or create the singleton embedding client instance.

    Returns:
        EmbeddingClient instance
    """
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
