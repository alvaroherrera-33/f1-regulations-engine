"""Admin authentication dependency.

Routes that mutate state (upload, sync/ingest, admin stats) require
an X-Admin-Key header matching the ADMIN_API_KEY environment variable.

Usage:
    from app.auth import require_admin_key

    @router.post("/upload")
    async def upload_pdf(..., _: None = Depends(require_admin_key)):
        ...
"""
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

_header_scheme = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin_key(api_key: str | None = Security(_header_scheme)) -> None:
    """
    FastAPI dependency that enforces admin authentication.

    Raises 403 if ADMIN_API_KEY is not configured or the provided key is wrong.
    Uses constant-time comparison to prevent timing attacks.
    """
    configured_key = settings.admin_api_key
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is disabled (ADMIN_API_KEY not configured).",
        )
    if not api_key or not secrets.compare_digest(api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Key header.",
        )
