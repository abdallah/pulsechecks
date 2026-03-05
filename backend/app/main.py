"""FastAPI application with Mangum for AWS Lambda."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from mangum import Mangum
from botocore.exceptions import ClientError

from .routers import users_router, teams_router, checks_router, ping_router, channels_router
from .config import get_settings
from .middleware import rate_limit_middleware, error_handler_middleware, request_logging_middleware, correlation_id_middleware
from .errors import (
    PulsechecksError,
    pulsechecks_error_handler,
    validation_error_handler,
    dynamodb_error_handler,
    generic_error_handler,
)
from .logging_config import setup_logging

# Setup structured logging
setup_logging()

# Note: uvloop removed - requires Linux-specific build
# Performance is still excellent with other optimizations

# Get settings
settings = get_settings()

# Create FastAPI app with orjson for faster JSON serialization
app = FastAPI(
    title="Pulsechecks API",
    description="Serverless job monitoring service",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware (order matters - correlation_id first)
app.middleware("http")(correlation_id_middleware)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(error_handler_middleware)

# Add global error handlers
app.add_exception_handler(PulsechecksError, pulsechecks_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(ClientError, dynamodb_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Include routers
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(checks_router)
app.include_router(ping_router)
app.include_router(channels_router)

# Lambda handler using Mangum
# This handles API Gateway HTTP API and REST API events
handler = Mangum(app, lifespan="off")

# Export for Lambda
__all__ = ["handler", "app"]
