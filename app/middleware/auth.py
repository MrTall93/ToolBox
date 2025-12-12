"""Authentication middleware for API key verification."""

from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

# Security scheme for API key authentication
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[str]:
    """Verify API key if configured, otherwise allow requests.

    Args:
        credentials: HTTP Authorization credentials from request header

    Returns:
        API key if valid, None if no API key configured

    Raises:
        HTTPException: If API key is configured but invalid or missing
    """
    # If no API key is configured in settings, allow requests without authentication
    if not settings.API_KEY:
        return None

    # If API key is configured but no credentials provided
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the provided API key
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


def require_auth(credentials: Optional[str] = Depends(verify_api_key)) -> Optional[str]:
    """Dependency that requires authentication if API key is configured.

    This is a wrapper around verify_api_key that can be used in endpoints
    to enforce authentication when API_KEY is set.

    Args:
        credentials: API key from verify_api_key dependency

    Returns:
        API key if valid, None if no authentication required
    """
    return credentials