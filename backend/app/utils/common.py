"""Utility functions for the application."""
import secrets
from datetime import datetime, timezone
from typing import Any


def get_iso_timestamp(timestamp_seconds: int = None) -> str:
    """Get timestamp in ISO 8601 format. If timestamp_seconds provided, convert it, otherwise use current time."""
    if timestamp_seconds:
        dt = datetime.fromtimestamp(timestamp_seconds, timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


def parse_iso_timestamp(iso_string: str) -> int:
    """Parse ISO 8601 timestamp string to Unix timestamp in seconds."""
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    return int(dt.timestamp())


def parse_iso_timestamp(iso_string: str) -> int:
    """Parse ISO 8601 timestamp string to Unix timestamp in seconds."""
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    return int(dt.timestamp())


def get_current_time_seconds() -> int:
    """Get current Unix timestamp in seconds."""
    return int(datetime.now(timezone.utc).timestamp())


def calculate_next_due(last_ping_seconds: int, period_seconds: int) -> int:
    """Calculate next due time in seconds."""
    return last_ping_seconds + period_seconds


def calculate_alert_after(last_ping_seconds: int, period_seconds: int, grace_seconds: int) -> int:
    """Calculate alert time (next_due + grace) in seconds."""
    # For very short periods, ensure minimum buffer to prevent false positives
    # Late detector runs every 2 minutes, so short periods need extra grace
    if period_seconds < 300:  # Less than 5 minutes
        effective_grace = max(grace_seconds, 180)  # Minimum 3 minutes grace for short periods
    else:
        effective_grace = grace_seconds
    
    return last_ping_seconds + period_seconds + effective_grace


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def generate_id() -> str:
    """Generate a secure random ID."""
    return secrets.token_urlsafe(16)
