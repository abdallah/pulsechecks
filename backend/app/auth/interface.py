"""Abstract authentication interface for multi-cloud support."""
from abc import ABC, abstractmethod
from typing import Dict, Tuple


class AuthInterface(ABC):
    """
    Abstract authentication interface for JWT verification.

    This interface defines authentication operations required by Pulsechecks,
    allowing the application to work with different auth providers
    (AWS Cognito, Firebase Auth, etc.) without changing business logic.
    """

    @abstractmethod
    async def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token and return claims.

        Args:
            token: JWT token string

        Returns:
            Decoded token claims

        Raises:
            InvalidTokenError: If token is invalid
        """
        pass

    @abstractmethod
    def extract_user_info(self, claims: Dict) -> Tuple[str, str, str, bool]:
        """
        Extract user information from JWT claims.

        Returns:
            Tuple of (user_id, email, name, email_verified)

        Raises:
            ValueError: If required claims are missing
        """
        pass

    def check_domain_allowed(self, email: str, allowed_domains: str = None) -> bool:
        """
        Check if email domain is in the allowlist.

        This is a common implementation that can be shared across providers.

        Args:
            email: User email address
            allowed_domains: Optional comma-separated list of allowed domains.
                           If None (default), uses settings.
                           If "" (empty string), allows all domains.

        Returns:
            True if domain is allowed, False otherwise
        """
        from ..config import get_settings

        # Determine which domains to check
        if allowed_domains is None:
            # Not provided - fall back to settings
            settings = get_settings()
            domains = settings.allowed_email_domains
        else:
            # Explicitly provided (may be empty string for "allow all")
            domains = allowed_domains

        if not domains:
            # No restriction if not configured or explicitly empty
            return True

        domain = email.split("@")[-1].lower()
        allowed = [d.strip().lower() for d in domains.split(",")]

        return domain in allowed

    def get_email_domain(self, email: str) -> str:
        """Extract domain from email address."""
        return email.split("@")[-1].lower()
