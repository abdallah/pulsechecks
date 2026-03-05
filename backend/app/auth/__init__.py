"""Authentication modules for multi-cloud support."""
from typing import Dict, Tuple

from .interface import AuthInterface
from .factory import create_auth_client, get_auth_client
from .cognito import CognitoAuth
from .firebase import FirebaseAuth


# Backwards-compatible wrapper functions
async def verify_jwt_token(token: str) -> Dict:
    """
    Verify JWT token and return claims.

    Backwards-compatible wrapper for existing code.

    Args:
        token: JWT token string

    Returns:
        Decoded token claims

    Raises:
        InvalidTokenError: If token is invalid
    """
    auth_client = create_auth_client()
    return await auth_client.verify_token(token)


def extract_user_info(claims: Dict) -> Tuple[str, str, str, bool]:
    """
    Extract user information from JWT claims.

    Backwards-compatible wrapper for existing code.

    Returns:
        Tuple of (user_id, email, name, email_verified)

    Raises:
        ValueError: If required claims are missing
    """
    auth_client = create_auth_client()
    return auth_client.extract_user_info(claims)


def check_domain_allowed(email: str, allowed_domains: str = None) -> bool:
    """
    Check if email domain is in the allowlist.

    Backwards-compatible wrapper for existing code.

    Args:
        email: User email address
        allowed_domains: Comma-separated list of allowed domains. If not provided, uses settings.

    Returns:
        True if domain is allowed, False otherwise
    """
    auth_client = create_auth_client()
    return auth_client.check_domain_allowed(email, allowed_domains)


def get_email_domain(email: str) -> str:
    """
    Extract domain from email address.

    Backwards-compatible wrapper for existing code.
    """
    auth_client = create_auth_client()
    return auth_client.get_email_domain(email)


__all__ = [
    "AuthInterface",
    "create_auth_client",
    "get_auth_client",
    "CognitoAuth",
    "FirebaseAuth",
    # Backwards-compatible functions
    "verify_jwt_token",
    "extract_user_info",
    "check_domain_allowed",
    "get_email_domain",
]
