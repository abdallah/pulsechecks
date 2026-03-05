"""AWS Cognito authentication implementation."""
import jwt
from jwt.exceptions import InvalidTokenError
import httpx
from typing import Dict, Tuple
from cachetools import TTLCache

from ..config import get_settings
from .interface import AuthInterface


# Cache JWKS for 24 hours (86400 seconds)
_jwks_cache: TTLCache = TTLCache(maxsize=10, ttl=86400)


class CognitoAuth(AuthInterface):
    """AWS Cognito authentication implementation."""

    def __init__(self):
        """Initialize Cognito auth with settings."""
        self.settings = get_settings()
        self.region = self.settings.aws_region
        self.user_pool_id = self.settings.cognito_user_pool_id
        self.client_id = self.settings.cognito_client_id

    async def _get_jwks(self) -> Dict:
        """Fetch and cache Cognito JWKS."""
        cache_key = f"{self.region}:{self.user_pool_id}"

        # Check cache first
        if cache_key in _jwks_cache:
            return _jwks_cache[cache_key]

        # Fetch from Cognito
        jwks_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json"

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()

        # Cache result
        _jwks_cache[cache_key] = jwks
        return jwks

    async def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token from Cognito and return claims.

        Args:
            token: JWT token string

        Returns:
            Decoded token claims

        Raises:
            InvalidTokenError: If token is invalid
        """
        # Get unverified header to extract kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise InvalidTokenError("Token missing kid in header")

        # Fetch JWKS
        jwks = await self._get_jwks()

        # Find matching key
        key = None
        for jwk_key in jwks.get("keys", []):
            if jwk_key.get("kid") == kid:
                key = jwk_key
                break

        if not key:
            raise InvalidTokenError("Public key not found in JWKS")

        # Verify and decode token
        from jwt.algorithms import RSAAlgorithm

        public_key = RSAAlgorithm.from_jwk(key)

        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            # ID tokens use aud claim, so we can verify it directly
            audience=self.client_id,
            issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}",
        )

        return claims

    def extract_user_info(self, claims: Dict) -> Tuple[str, str, str, bool]:
        """
        Extract user information from Cognito JWT claims.

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
