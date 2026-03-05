"""Retry utilities for external service calls."""
import asyncio
import logging
from typing import TypeVar, Callable, Any, Optional
from functools import wraps
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

def should_retry_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry."""
    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")
        # Retry on throttling and service errors, not on client errors
        return error_code in [
            "ProvisionedThroughputExceededException",
            "RequestLimitExceeded", 
            "ServiceUnavailable",
            "InternalServerError",
            "Throttling",
        ]
    return False

async def retry_async(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> T:
    """Retry an async function with exponential backoff."""
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if not should_retry_error(e) or attempt == config.max_attempts - 1:
                raise
            
            # Calculate delay with exponential backoff
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                import random
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(
                f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {str(e)}"
            )
            await asyncio.sleep(delay)
    
    # This should never be reached, but just in case
    raise last_exception

def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry behavior to async functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_async(func, config, *args, **kwargs)
        return wrapper
    return decorator
