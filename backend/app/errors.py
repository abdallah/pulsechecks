"""Centralized error handling for Pulsechecks API."""
import logging
import uuid
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_correlation_id(request: Request) -> str:
    """Get or generate correlation ID for request tracking."""
    # Check if correlation ID exists in request state (set by middleware)
    if hasattr(request.state, 'correlation_id'):
        return request.state.correlation_id
    # Generate new one if not present
    return str(uuid.uuid4())


class PulsechecksError(Exception):
    """Base exception for Pulsechecks errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(PulsechecksError):
    """Resource not found error."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class UnauthorizedError(PulsechecksError):
    """Unauthorized access error."""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(PulsechecksError):
    """Forbidden access error."""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class ValidationError(PulsechecksError):
    """Validation error."""
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


async def pulsechecks_error_handler(request: Request, exc: PulsechecksError) -> JSONResponse:
    """Handle custom Pulsechecks errors."""
    correlation_id = get_correlation_id(request)
    logger.error(f"PulsechecksError: {exc.message}", extra={
        "correlation_id": correlation_id,
        "path": request.url.path,
        "method": request.method,
        "status_code": exc.status_code,
    })
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "correlation_id": correlation_id}
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    correlation_id = get_correlation_id(request)
    logger.warning(f"Validation error: {exc.errors()}", extra={
        "correlation_id": correlation_id,
        "path": request.url.path,
        "method": request.method,
    })
    
    # Convert errors to JSON-serializable format
    serializable_errors = []
    for error in exc.errors():
        serializable_error = dict(error)
        # Convert any non-serializable values to strings
        if 'ctx' in serializable_error and serializable_error['ctx']:
            for key, value in serializable_error['ctx'].items():
                if not isinstance(value, (str, int, float, bool, type(None))):
                    serializable_error['ctx'][key] = str(value)
        serializable_errors.append(serializable_error)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation error", "details": serializable_errors, "correlation_id": correlation_id}
    )


async def dynamodb_error_handler(request: Request, exc: ClientError) -> JSONResponse:
    """Handle DynamoDB/Boto3 client errors."""
    correlation_id = get_correlation_id(request)
    error_code = exc.response.get("Error", {}).get("Code", "Unknown")
    error_message = exc.response.get("Error", {}).get("Message", "Database error")
    
    logger.error(f"DynamoDB error: {error_code} - {error_message}", extra={
        "correlation_id": correlation_id,
        "path": request.url.path,
        "method": request.method,
        "error_code": error_code,
    })
    
    # Map specific DynamoDB errors to HTTP status codes
    if error_code == "ResourceNotFoundException":
        status_code = status.HTTP_404_NOT_FOUND
        message = "Resource not found"
    elif error_code == "ConditionalCheckFailedException":
        status_code = status.HTTP_409_CONFLICT
        message = "Conflict: condition check failed"
    elif error_code in ["ProvisionedThroughputExceededException", "RequestLimitExceeded"]:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        message = "Service temporarily unavailable"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        message = "Database error"
    
    return JSONResponse(
        status_code=status_code,
        content={"error": message, "correlation_id": correlation_id}
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unhandled exceptions."""
    correlation_id = get_correlation_id(request)
    logger.exception(f"Unhandled exception: {str(exc)}", extra={
        "correlation_id": correlation_id,
        "path": request.url.path,
        "method": request.method,
    })
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "correlation_id": correlation_id}
    )
