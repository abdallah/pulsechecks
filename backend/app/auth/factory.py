"""Authentication client factory for multi-cloud support."""
from ..config import get_settings
from .interface import AuthInterface


def create_auth_client() -> AuthInterface:
    """
    Create and return the appropriate authentication client based on cloud provider setting.

    Returns:
        Authentication client instance implementing AuthInterface

    Raises:
        ValueError: If cloud_provider is not supported
    """
    settings = get_settings()
    cloud_provider = settings.cloud_provider.lower()

    if cloud_provider == "aws":
        from .cognito import CognitoAuth
        return CognitoAuth()
    elif cloud_provider == "gcp":
        from .firebase import FirebaseAuth
        return FirebaseAuth()
    else:
        raise ValueError(
            f"Unsupported cloud provider: {cloud_provider}. "
            f"Supported providers: 'aws', 'gcp'"
        )


# For backwards compatibility
get_auth_client = create_auth_client
