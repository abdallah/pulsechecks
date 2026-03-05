"""Structured logging configuration for Pulsechecks."""
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
from contextvars import ContextVar

# Context variables for request correlation
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "pulsechecks-api",
        }
        
        # Add request context if available
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id
            
        user_id = user_id_var.get()
        if user_id:
            log_entry["user_id"] = user_id
        
        # Add extra fields from log record
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
            
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)


def setup_logging():
    """Configure structured logging."""
    # Create formatter
    formatter = StructuredFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler with structured formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("app").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with structured formatting."""
    return logging.getLogger(name)


def log_business_event(event_type: str, **kwargs):
    """Log a business event with structured data."""
    logger = get_logger("app.business")
    extra_fields = {
        "event_type": event_type,
        **kwargs
    }
    logger.info(f"Business event: {event_type}", extra={'extra_fields': extra_fields})


def set_request_context(request_id: str = None, user_id: str = None):
    """Set request context for logging."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context():
    """Clear request context."""
    request_id_var.set(None)
    user_id_var.set(None)
