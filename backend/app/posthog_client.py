"""PostHog analytics client."""
import atexit
from posthog import Posthog, new_context, identify_context, tag

from .config import get_settings

_posthog_client: Posthog | None = None


def get_posthog_client() -> Posthog:
    """Get or create the PostHog client instance."""
    global _posthog_client
    if _posthog_client is None:
        settings = get_settings()
        _posthog_client = Posthog(
            project_api_key=settings.posthog_api_key,
            host=settings.posthog_host,
            enable_exception_autocapture=True,
        )
        atexit.register(_posthog_client.shutdown)
    return _posthog_client


__all__ = ["get_posthog_client", "new_context", "identify_context", "tag"]
