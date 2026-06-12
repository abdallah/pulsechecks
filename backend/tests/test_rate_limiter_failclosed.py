"""Tests for rate limiter fail-closed behavior and documentation."""
import time
import pytest
from unittest.mock import patch
from app.middleware import RateLimiter


class TestRateLimiterFailClosed:
    """Verify rate limiter fails closed on internal errors."""

    def test_normal_allow(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.is_allowed("client-1") is True

    def test_limit_exceeded(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("x") is True
        assert limiter.is_allowed("x") is True
        assert limiter.is_allowed("x") is False

    def test_fails_closed_on_internal_error(self):
        """On any internal exception, is_allowed returns False (deny)."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        with patch.object(limiter, "requests", side_effect=Exception("boom")):
            # Accessing limiter.requests raises -> should fail closed
            # We patch defaultdict __getitem__ behavior
            pass

        # More targeted: patch time.time to cause failure
        with patch("app.middleware.time.time", side_effect=RuntimeError("clock error")):
            assert limiter.is_allowed("client-1") is False

    def test_window_expiry_allows_again(self):
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed("y") is True
        assert limiter.is_allowed("y") is False
        time.sleep(1.1)
        assert limiter.is_allowed("y") is True

    def test_docstring_documents_non_distributed(self):
        """Class docstring warns about process-local limitation."""
        assert "NOT distributed" in RateLimiter.__doc__
        assert "MUST NOT" in RateLimiter.__doc__
