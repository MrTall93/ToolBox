"""
Enhanced embedding service with retry logic, caching, and monitoring.

This service provides a robust wrapper around the EmbeddingClient with
production-ready features like exponential backoff, LRU caching, and
comprehensive error handling.
"""
import asyncio
import hashlib
import logging
import time
from functools import wraps
from typing import List, Optional, Dict, Any, Tuple
import httpx
from cachetools import TTLCache, LRUCache
import backoff

from app.config import settings
from app.registry.embedding_client import EmbeddingClient, get_embedding_client

# Setup logging
logger = logging.getLogger(__name__)

# Cache configuration
_EMBEDDING_CACHE: Optional[LRUCache] = None
_CACHE_STATS = {
    "hits": 0,
    "misses": 0,
    "errors": 0,
    "total_requests": 0,
}


def get_embedding_cache() -> LRUCache:
    """Get or create the embedding cache."""
    global _EMBEDDING_CACHE
    if _EMBEDDING_CACHE is None and settings.ENABLE_EMBEDDING_CACHE:
        _EMBEDDING_CACHE = LRUCache(
            maxsize=settings.EMBEDDING_CACHE_SIZE,
        )
        logger.info(f"Embedding cache initialized with max size: {settings.EMBEDDING_CACHE_SIZE}")
    return _EMBEDDING_CACHE or LRUCache(maxsize=1)  # Fallback dummy cache


def get_cache_key(text: str) -> str:
    """Generate cache key for text."""
    return hashlib.md5(text.encode()).hexdigest()


def _log_cache_stats(func):
    """Decorator to log cache statistics."""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        _CACHE_STATS["total_requests"] += 1
        try:
            result = await func(self, *args, **kwargs)
            return result
        except Exception as e:
            _CACHE_STATS["errors"] += 1
            logger.error(f"Embedding service error: {e}")
            raise
    return wrapper


def _retry_on_http_error(exception):
    """Check if exception should trigger retry."""
    if isinstance(exception, httpx.HTTPError):
        # Retry on network errors, timeouts, and 5xx errors
        if hasattr(exception, 'response') and exception.response is not None:
            # Don't retry on 4xx client errors (except 429 Too Many Requests)
            return (400 <= exception.response.status_code < 500 and
                    exception.response.status_code != 429)
        return True  # Retry on network errors
    return False


def _retry_on_value_error(exception):
    """Check if ValueError should trigger retry."""
    if isinstance(exception, ValueError):
        # Retry on temporary data format issues
        return "Invalid embedding response" in str(exception)
    return False


class EmbeddingService:
    """
    Enhanced embedding service with production-ready features.

    Features:
    - Exponential backoff retry logic
    - LRU caching for repeated requests
    - Request batching and optimization
    - Comprehensive logging and monitoring
    - Circuit breaker pattern
    """

    def __init__(
        self,
        client: Optional[EmbeddingClient] = None,
        max_batch_size: int = 100,
        cache_ttl: int = 3600,  # 1 hour
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """
        Initialize enhanced embedding service.

        Args:
            client: EmbeddingClient instance (creates default if None)
            max_batch_size: Maximum texts to process in a single batch
            cache_ttl: Cache time-to-live in seconds (not used with LRU)
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff in seconds
        """
        self.client = client or get_embedding_client()
        self.max_batch_size = max_batch_size
        self.cache = get_embedding_cache()
        self.max_retries = max_retries
        self.base_delay = base_delay

        # Circuit breaker state
        self._circuit_open = False
        self._circuit_open_time = 0
        self._circuit_timeout = 60  # Circuit timeout in seconds
        self._failure_count = 0
        self._failure_threshold = 5
        self._success_count = 0
        self._success_threshold = 3

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_open:
            return True

        # Check if circuit should be half-open
        if time.time() - self._circuit_open_time > self._circuit_timeout:
            self._circuit_open = False
            self._success_count = 0
            logger.info("Circuit breaker entering half-open state")
            return True

        return False

    def _record_success(self):
        """Record successful operation."""
        self._success_count += 1
        self._failure_count = 0

        # Close circuit if we're in half-open state and have enough successes
        if not self._circuit_open and self._success_count >= self._success_threshold:
            self._circuit_open = False
            logger.info("Circuit breaker closed")

    def _record_failure(self):
        """Record failed operation."""
        self._failure_count += 1
        self._success_count = 0

        # Open circuit if too many failures
        if self._failure_count >= self._failure_threshold and not self._circuit_open:
            self._circuit_open = True
            self._circuit_open_time = time.time()
            logger.warning("Circuit breaker opened due to repeated failures")

    @backoff.on_exception(
        backoff.expo,
        (httpx.HTTPError, ValueError),
        base=1,
        max_tries=3,
        jitter=backoff.random_jitter,
        giveup=lambda e: not (_retry_on_http_error(e) or _retry_on_value_error(e)),
    )
    @_log_cache_stats
    async def embed_text(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for a single text with caching and retry logic.

        Args:
            text: Text to embed
            use_cache: Whether to use cache for this request

        Returns:
            List of floats representing the embedding vector

        Raises:
            Exception: If embedding fails after retries
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check circuit breaker
        if not self._check_circuit_breaker():
            raise Exception("Circuit breaker is open - embedding service unavailable")

        # Check cache first
        if use_cache and settings.ENABLE_EMBEDDING_CACHE:
            cache_key = get_cache_key(text)
            try:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    _CACHE_STATS["hits"] += 1
                    logger.debug(f"Cache hit for text: {text[:50]}...")
                    self._record_success()
                    return cached_result
            except Exception as e:
                logger.warning(f"Cache error: {e}")

        _CACHE_STATS["misses"] += 1
        logger.debug(f"Cache miss for text: {text[:50]}...")

        try:
            # Use client to generate embedding
            start_time = time.time()
            embedding = await self.client.embed_text(text)
            duration = time.time() - start_time

            # Cache the result
            if use_cache and settings.ENABLE_EMBEDDING_CACHE:
                try:
                    self.cache[cache_key] = embedding
                except Exception as e:
                    logger.warning(f"Failed to cache embedding: {e}")

            self._record_success()
            logger.debug(f"Generated embedding in {duration:.2f}s")
            return embedding

        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to embed text after retries: {e}")
            raise

    @_log_cache_stats
    async def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with optimization.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache for this request
            batch_size: Override default batch size

        Returns:
            List of embedding vectors

        Raises:
            Exception: If embedding fails after retries
        """
        if not texts:
            return []

        batch_size = batch_size or self.max_batch_size
        all_embeddings = []

        # Process in batches for better performance
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1} with {len(batch)} texts")

            # Check which texts are cached
            uncached_texts = []
            uncached_indices = []
            cached_embeddings = [None] * len(batch)

            if use_cache and settings.ENABLE_EMBEDDING_CACHE:
                for j, text in enumerate(batch):
                    if not text or not text.strip():
                        cached_embeddings[j] = []
                        continue

                    cache_key = get_cache_key(text)
                    try:
                        cached_result = self.cache.get(cache_key)
                        if cached_result is not None:
                            cached_embeddings[j] = cached_result
                            _CACHE_STATS["hits"] += 1
                        else:
                            uncached_texts.append(text)
                            uncached_indices.append(j)
                            _CACHE_STATS["misses"] += 1
                    except Exception as e:
                        logger.warning(f"Cache error: {e}")
                        uncached_texts.append(text)
                        uncached_indices.append(j)
            else:
                uncached_texts = batch
                uncached_indices = list(range(len(batch)))
                _CACHE_STATS["misses"] += len(batch)

            # Generate embeddings for uncached texts
            if uncached_texts:
                try:
                    # Check circuit breaker
                    if not self._check_circuit_breaker():
                        raise Exception("Circuit breaker is open - embedding service unavailable")

                    start_time = time.time()
                    new_embeddings = await self.client.embed_batch(uncached_texts)
                    duration = time.time() - start_time

                    # Place new embeddings in the correct positions
                    for j, embedding in enumerate(new_embeddings):
                        cached_embeddings[uncached_indices[j]] = embedding

                        # Cache the new embedding
                        if use_cache and settings.ENABLE_EMBEDDING_CACHE:
                            try:
                                text = uncached_texts[j]
                                cache_key = get_cache_key(text)
                                self.cache[cache_key] = embedding
                            except Exception as e:
                                logger.warning(f"Failed to cache embedding: {e}")

                    logger.debug(f"Generated {len(new_embeddings)} embeddings in {duration:.2f}s")
                    self._record_success()

                except Exception as e:
                    self._record_failure()
                    logger.error(f"Failed to embed batch: {e}")
                    raise

            all_embeddings.extend(cached_embeddings)

        return all_embeddings

    async def embed_tool(self, tool_data: Dict[str, Any], use_cache: bool = True) -> List[float]:
        """
        Generate embedding for tool metadata.

        Args:
            tool_data: Tool metadata dictionary
            use_cache: Whether to use cache for this request

        Returns:
            Embedding vector for the tool
        """
        return await self.embed_text(
            self._create_tool_text(tool_data),
            use_cache=use_cache
        )

    def _create_tool_text(self, tool_data: Dict[str, Any]) -> str:
        """Create text representation of tool for embedding."""
        parts = []

        # Add name (weighted more)
        if "name" in tool_data:
            parts.append(f"Tool: {tool_data['name']}")
            parts.append(tool_data['name'])

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

        # Add schema if available
        if "input_schema" in tool_data:
            parts.append(f"Input: {str(tool_data['input_schema'])}")

        return " | ".join(parts)

    async def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check with circuit breaker and cache stats.

        Returns:
            Health check result with detailed status
        """
        health = {
            "status": "healthy",
            "client_available": False,
            "circuit_breaker_open": self._circuit_open,
            "cache_enabled": settings.ENABLE_EMBEDDING_CACHE,
            "cache_size": len(self.cache) if settings.ENABLE_EMBEDDING_CACHE else 0,
            "cache_stats": _CACHE_STATS.copy() if settings.ENABLE_EMBEDDING_CACHE else None,
            "error": None,
        }

        try:
            # Test client health
            client_healthy = await self.client.health_check()
            health["client_available"] = client_healthy

            if not client_healthy:
                health["status"] = "degraded"
                health["error"] = "Embedding client unhealthy"

            # Check circuit breaker
            if self._circuit_open:
                health["status"] = "unhealthy"
                health["error"] = "Circuit breaker open"

        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)

        return health

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        stats = _CACHE_STATS.copy()
        if stats["total_requests"] > 0:
            stats["hit_rate"] = stats["hits"] / stats["total_requests"]
            stats["miss_rate"] = stats["misses"] / stats["total_requests"]
            stats["error_rate"] = stats["errors"] / stats["total_requests"]
        else:
            stats["hit_rate"] = 0.0
            stats["miss_rate"] = 0.0
            stats["error_rate"] = 0.0

        if settings.ENABLE_EMBEDDING_CACHE:
            stats["cache_size"] = len(self.cache)
            stats["cache_max_size"] = self.cache.maxsize
            stats["cache_utilization"] = len(self.cache) / self.cache.maxsize
        else:
            stats["cache_size"] = 0
            stats["cache_max_size"] = 0
            stats["cache_utilization"] = 0.0

        return stats

    def reset_cache_stats(self):
        """Reset cache statistics."""
        global _CACHE_STATS
        _CACHE_STATS = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_requests": 0,
        }

    def clear_cache(self):
        """Clear the embedding cache."""
        if settings.ENABLE_EMBEDDING_CACHE:
            self.cache.clear()
            logger.info("Embedding cache cleared")

    def reset_circuit_breaker(self):
        """Reset circuit breaker to closed state."""
        self._circuit_open = False
        self._failure_count = 0
        self._success_count = 0
        logger.info("Circuit breaker reset")


# Singleton instance for convenience
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get or create the singleton embedding service instance.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


# Configuration extension for settings
# Add these to app/config.py if not already present
DEFAULT_EMBEDDING_CONFIG = {
    "ENABLE_EMBEDDING_CACHE": True,
    "EMBEDDING_CACHE_SIZE": 1000,
    "EMBEDDING_MAX_RETRIES": 3,
    "EMBEDDING_BASE_DELAY": 1.0,
    "EMBEDDING_MAX_BATCH_SIZE": 100,
}