"""HTTP utility functions for making external requests."""

import os
from functools import lru_cache
from typing import Union

import httpx

# Default custom certificate path for corporate/enterprise environments
DEFAULT_CUSTOM_CERT_PATH = "/etc/ssl/certs/ca-custom.pem"


@lru_cache(maxsize=1)
def get_ssl_verify() -> Union[str, bool]:
    """
    Get SSL verification setting for HTTP clients.

    Returns the path to a custom CA certificate if it exists at the default location,
    otherwise returns True for default SSL verification.

    Returns:
        Path to custom CA certificate if it exists, otherwise True for default verification.

    Note:
        Result is cached since the certificate path doesn't change at runtime.
    """
    if os.path.exists(DEFAULT_CUSTOM_CERT_PATH):
        return DEFAULT_CUSTOM_CERT_PATH
    return True


def create_http_client(
    timeout: float = 30.0,
    **kwargs
) -> httpx.AsyncClient:
    """
    Create an httpx AsyncClient with standard configuration.

    This is a factory function that creates a properly configured HTTP client
    with SSL verification and timeout settings.

    Args:
        timeout: Request timeout in seconds (default: 30.0)
        **kwargs: Additional arguments passed to AsyncClient

    Returns:
        Configured AsyncClient instance

    Usage:
        async with create_http_client() as client:
            response = await client.get("https://example.com")

        # With custom timeout
        async with create_http_client(timeout=60.0) as client:
            response = await client.post("https://api.example.com/data", json=data)
    """
    return httpx.AsyncClient(
        verify=get_ssl_verify(),
        timeout=httpx.Timeout(timeout),
        **kwargs
    )
