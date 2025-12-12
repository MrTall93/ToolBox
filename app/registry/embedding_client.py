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

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Prepare request payload for LM Studio format
        if len(texts) == 1:
            # Single text
            payload = {
                "input": texts[0],
                "model": "text-embedding-nomic-embed-text-v1.5"  # LM Studio model
            }
        else:
            # Multiple texts - LM Studio might not support this, so batch them
            # For now, send the first one and repeat calls if needed
            payload = {
                "input": texts[0],
                "model": "text-embedding-nomic-embed-text-v1.5"
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise Exception(
                    f"Failed to get embeddings from {self.endpoint_url}: {str(e)}"
                ) from e

            # Parse response for LM Studio format
            try:
                data = response.json()

                # LM Studio typically returns: {"data": [{"embedding": [...]}]}
                if "data" in data and isinstance(data["data"], list):
                    embeddings = [item["embedding"] for item in data["data"]]
                # Support alternative LM Studio format: {"embedding": [...]}
                elif "embedding" in data:
                    embeddings = [data["embedding"]]
                # Support common formats
                elif "embeddings" in data:
                    embeddings = data["embeddings"]
                elif isinstance(data, list):
                    embeddings = data
                else:
                    raise ValueError(f"Unexpected response format: {data}")

                # Validate embeddings
                if len(embeddings) != len(texts):
                    raise ValueError(
                        f"Expected {len(texts)} embeddings, got {len(embeddings)}"
                    )

                for i, embedding in enumerate(embeddings):
                    if len(embedding) != self.dimension:
                        raise ValueError(
                            f"Embedding {i} has dimension {len(embedding)}, "
                            f"expected {self.dimension}"
                        )

                return embeddings

            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"Invalid embedding response: {str(e)}") from e

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
