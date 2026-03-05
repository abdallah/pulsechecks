"""Middleware for FastAPI application."""
import time
import uuid
from collections import defaultdict, deque
from typing import Dict, Deque
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from .logging_config import get_logger, set_request_context, clear_request_context, log_business_event
from .metrics import get_metrics_client

logger = get_logger(__name__)


async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to all requests for tracking."""
    # Generate or extract correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    
    # Store in request state
    request.state.correlation_id = correlation_id
    
    # Set in logging context
    set_request_context(correlation_id)
    
    try:
        response = await call_next(request)
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        clear_request_context()

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for the given key."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        request_times = self.requests[key]
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        
        # Check if under limit
        if len(request_times) >= self.max_requests:
            return False
        
        # Add current request
        request_times.append(now)
        return True

# Global rate limiters
general_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100 req/min
ping_limiter = RateLimiter(max_requests=1000, window_seconds=60)    # 1000 req/min for pings

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Choose appropriate limiter
    if request.url.path.startswith("/ping/"):
        limiter = ping_limiter
        limit_type = "ping"
    else:
        limiter = general_limiter
        limit_type = "general"
    
    # Check rate limit
    if not limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip} on {limit_type} endpoint")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "detail": f"Too many requests from {client_ip}",
                "retry_after": limiter.window_seconds
            },
            headers={"Retry-After": str(limiter.window_seconds)}
        )
    
    response = await call_next(request)
    return response

async def request_logging_middleware(request: Request, call_next):
    """Add request context and logging."""
    start_time = time.time()
    metrics = get_metrics_client()
    
    # Set request context for structured logging
    set_request_context()
    
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)
        
        # Record metrics
        metrics.api_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms
        )
        
        # Log request completion
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                'extra_fields': {
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'duration_ms': duration_ms,
                    'user_agent': request.headers.get('user-agent'),
                }
            }
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)
        
        # Record error metrics
        metrics.api_request(
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=duration_ms
        )
        
        logger.error(
            f"{request.method} {request.url.path} - ERROR: {str(e)}",
            extra={
                'extra_fields': {
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': duration_ms,
                    'error': str(e),
                }
            },
            exc_info=True
        )
        raise
    finally:
        clear_request_context()


async def error_handler_middleware(request: Request, call_next):
    """Global error handling middleware."""
    try:
        response = await call_next(request)
        return response
    except HTTPException:
        # Let FastAPI handle HTTP exceptions
        raise
    except ValueError as e:
        logger.warning(f"Validation error on {request.url.path}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Validation error",
                "detail": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error on {request.url.path}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": "An unexpected error occurred"
            }
        )
