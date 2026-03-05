"""Authentication and JWT verification using PyJWT and httpx."""
import jwt
from jwt.exceptions import InvalidTokenError
import httpx
from typing import Dict, Tuple
from cachetools import TTLCache
from functools import lru_cache

from .config import get_settings


# Cache JWKS for 24 hours (86400 seconds)
_jwks_cache: TTLCache = TTLCache(maxsize=10, ttl=86400)


async def get_jwks(region: str, user_pool_id: str) -> Dict:
    """Fetch and cache Cognito JWKS."""
    cache_key = f"{region}:{user_pool_id}"

    # Check cache first
    if cache_key in _jwks_cache:
        return _jwks_cache[cache_key]

    # Fetch from Cognito
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"

    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        jwks = response.json()

    # Cache result
    _jwks_cache[cache_key] = jwks
    return jwks


async def verify_jwt_token(token: str) -> Dict:
    """
    Verify JWT token from Cognito and return claims.

    Args:
        token: JWT token string

    Returns:
        Decoded token claims

    Raises:
        InvalidTokenError: If token is invalid
    """
    settings = get_settings()

    # Get unverified header to extract kid
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    if not kid:
        raise InvalidTokenError("Token missing kid in header")

    # Fetch JWKS
    jwks = await get_jwks(settings.aws_region, settings.cognito_user_pool_id)

    # Find matching key
    key = None
    for jwk_key in jwks.get("keys", []):
        if jwk_key.get("kid") == kid:
            key = jwk_key
            break

    if not key:
        raise InvalidTokenError("Public key not found in JWKS")

    # Verify and decode token
    # PyJWT expects the JWK as a dict and will handle the conversion
    from jwt.algorithms import RSAAlgorithm

    public_key = RSAAlgorithm.from_jwk(key)

    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        # ID tokens use aud claim, so we can verify it directly
        audience=settings.cognito_client_id,
        issuer=f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}",
    )

    return claims


def extract_user_info(claims: Dict) -> Tuple[str, str, str, bool]:
    """
    Extract user information from JWT claims.

    Returns:
        Tuple of (user_id, email, name, email_verified)

    Raises:
        ValueError: If required claims are missing
    """
    user_id = claims.get("sub")
    email = claims.get("email", "")
    name = claims.get("name", email.split("@")[0] if email else "Unknown")
    email_verified = claims.get("email_verified", False)

    if not user_id:
        raise ValueError("Token missing sub claim")

    if not email:
        raise ValueError("Token missing email claim")

    return user_id, email, name, email_verified


def check_domain_allowed(email: str, allowed_domains: str = "") -> bool:
    """
    Check if email domain is in the allowlist.

    Args:
        email: User email address
        allowed_domains: Comma-separated list of allowed domains

    Returns:
        True if domain is allowed, False otherwise
    """
    settings = get_settings()
    domains = allowed_domains or settings.allowed_email_domains

    if not domains:
        # No restriction if not configured
        return True

    domain = email.split("@")[-1].lower()
    allowed = [d.strip().lower() for d in domains.split(",")]

    return domain in allowed


def get_email_domain(email: str) -> str:
    """Extract domain from email address."""
    return email.split("@")[-1].lower()
