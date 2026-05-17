"""JWT authentication and API key management for the orchid multi-tenant API."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

logger = structlog.get_logger(__name__)

_JWT_SECRET = os.getenv("API_SECRET_KEY", "dev-secret-change-in-prod")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))


# ---------------------------------------------------------------------------
# Token creation & verification
# ---------------------------------------------------------------------------


def create_access_token(tenant_id: str) -> str:
    """Issue a signed JWT for the given tenant."""
    now = datetime.now(UTC)
    payload = {
        "sub": tenant_id,
        "iat": now,
        "exp": now + timedelta(hours=_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_access_token(token: str) -> str:
    """Decode a JWT and return the tenant_id (sub claim).

    Raises HTTPException 401 on any verification failure.
    """
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        tenant_id: str | None = payload.get("sub")
        if not tenant_id:
            raise ValueError("missing sub claim")
        return tenant_id
    except JWTError as exc:
        logger.warning("jwt_verification_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


def hash_api_key(raw_key: str) -> str:
    """Return HMAC-SHA256 hex digest of the raw API key.

    Uses the JWT secret as the HMAC key so the hash is only reproducible
    server-side — equivalent security to bcrypt for this threat model,
    with O(1) verification instead of O(bcrypt_cost).
    """
    return hmac.new(
        _JWT_SECRET.encode(),
        raw_key.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Generate a cryptographically random API key.

    Returns (raw_key, hashed_key). Store only the hash; give raw_key to the tenant.
    """
    raw = f"orchid_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_tenant(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    authorization: str = Header(...),
) -> str:
    """Extract and validate the calling tenant.

    Requires:
      Authorization: Bearer <JWT>
      X-Tenant-ID: <tenant_id>

    The JWT sub claim must equal X-Tenant-ID.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ")
    token_tenant = verify_access_token(token)
    if token_tenant != x_tenant_id:
        logger.warning(
            "tenant_mismatch",
            header_tenant=x_tenant_id,
            token_tenant=token_tenant,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Tenant-ID does not match token subject",
        )
    return x_tenant_id
