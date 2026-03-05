"""Firebase Authentication implementation."""
import jwt
from jwt.exceptions import InvalidTokenError
import httpx
from typing import Dict, Tuple
from cachetools import TTLCache

from ..config import get_settings
from .interface import AuthInterface


# Cache JWKS for 24 hours (86400 seconds)
_firebase_jwks_cache: TTLCache = TTLCache(maxsize=10, ttl=86400)


class FirebaseAuth(AuthInterface):
    """
    Firebase Authentication implementation.

    Uses Firebase ID tokens (JWT) for authentication.
    Verifies tokens using Google's public keys.
    """

    def __init__(self):
        """Initialize Firebase auth with settings."""
        self.settings = get_settings()
        self.project_id = self.settings.firebase_project_id or self.settings.gcp_project

    async def _get_jwks(self) -> Dict:
        """Fetch and cache Firebase/Google JWKS."""
        cache_key = "firebase_jwks"

        # Check cache first
        if cache_key in _firebase_jwks_cache:
            return _firebase_jwks_cache[cache_key]

        # Fetch from Google's public key endpoint
        # Firebase uses Google's identity platform public keys
        jwks_url = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()

        # Cache result
        _firebase_jwks_cache[cache_key] = jwks
        return jwks

    async def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token from Firebase and return claims.

        Args:
            token: Firebase ID token string

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

        # Firebase tokens use the project ID as audience
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=self.project_id,
            issuer=f"https://securetoken.google.com/{self.project_id}",
        )

        return claims

    def extract_user_info(self, claims: Dict) -> Tuple[str, str, str, bool]:
        """
        Extract user information from Firebase JWT claims.

        Firebase tokens have slightly different claim structure:
        - sub: user ID
        - email: email address
        - name: display name (may not be present)
        - email_verified: boolean

        Returns:
            Tuple of (user_id, email, name, email_verified)

        Raises:
            ValueError: If required claims are missing
        """
        user_id = claims.get("sub") or claims.get("user_id")
        email = claims.get("email", "")

        # Firebase may store name in 'name' or we can extract from email
        name = claims.get("name") or claims.get("display_name")
        if not name and email:
            name = email.split("@")[0]
        if not name:
            name = "Unknown"

        email_verified = claims.get("email_verified", False)

        if not user_id:
            raise ValueError("Token missing sub/user_id claim")

        if not email:
            raise ValueError("Token missing email claim")

        return user_id, email, name, email_verified
