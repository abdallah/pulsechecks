"""Tests for utility functions."""
import pytest
from datetime import datetime, timezone
from app.utils import (
    get_iso_timestamp,
    get_current_time_seconds,
    calculate_next_due,
    calculate_alert_after,
    generate_token,
    generate_id,
)


def test_get_iso_timestamp():
    """Test ISO timestamp generation."""
    timestamp = get_iso_timestamp()
    assert isinstance(timestamp, str)
    assert "T" in timestamp
    # Should be parseable
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert dt.tzinfo is not None


def test_get_current_time_seconds():
    """Test Unix timestamp generation."""
    timestamp = get_current_time_seconds()
    assert isinstance(timestamp, int)
    assert timestamp > 0
    # Should be reasonable (after 2020)
    assert timestamp > 1577836800


def test_calculate_next_due():
    """Test next due time calculation."""
    last_ping = 1000000
    period = 3600
    next_due = calculate_next_due(last_ping, period)
    assert next_due == 1003600


def test_calculate_alert_after():
    """Test alert time calculation."""
    last_ping = 1000000
    period = 3600
    grace = 600
    alert_after = calculate_alert_after(last_ping, period, grace)
    assert alert_after == 1004200  # 1000000 + 3600 + 600


def test_generate_token():
    """Test token generation."""
    token1 = generate_token()
    token2 = generate_token()

    assert isinstance(token1, str)
    assert isinstance(token2, str)
    assert len(token1) > 0
    assert len(token2) > 0
    # Should be unique
    assert token1 != token2
    # Should be URL-safe
    assert "/" not in token1
    assert "+" not in token1


def test_generate_id():
    """Test ID generation."""
    id1 = generate_id()
    id2 = generate_id()

    assert isinstance(id1, str)
    assert isinstance(id2, str)
    assert len(id1) > 0
    assert len(id2) > 0
    # Should be unique
    assert id1 != id2
    # Should be URL-safe
    assert "/" not in id1
    assert "+" not in id1
