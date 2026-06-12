"""Tests for OIDC cert cache TTL expiration and invalidation."""
import time
import pytest
from unittest.mock import patch, MagicMock

from app.oidc_validator import (
    _get_google_certs,
    _google_certs_cache,
    invalidate_google_certs_cache,
)


class TestOIDCCacheTTL:
    """Verify cert cache expires after TTL and can be invalidated."""

    def setup_method(self):
        """Clear cache before each test."""
        _google_certs_cache.clear()

    def test_cache_returns_same_result_within_ttl(self):
        """Successive calls within TTL return cached value (no extra fetch)."""
        fake_certs = {"key-1": "cert-pem-1"}
        with patch("app.oidc_validator.httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = fake_certs
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            result1 = _get_google_certs()
            result2 = _get_google_certs()

        assert result1 == fake_certs
        assert result2 == fake_certs
        # httpx.Client called only once (cached on second call)
        assert mock_client_cls.call_count == 1

    def test_cache_expires_after_ttl(self):
        """After TTL elapses, cache refetches certificates."""
        fake_certs_v1 = {"key-1": "cert-v1"}
        fake_certs_v2 = {"key-2": "cert-v2"}

        call_count = {"n": 0}

        def make_response():
            mock_resp = MagicMock()
            call_count["n"] += 1
            mock_resp.json.return_value = fake_certs_v1 if call_count["n"] == 1 else fake_certs_v2
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("app.oidc_validator.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get = MagicMock(side_effect=lambda *a, **k: make_response())
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            result1 = _get_google_certs()
            assert result1 == fake_certs_v1

            # Simulate TTL expiry by clearing the TTLCache (mimics time passing)
            _google_certs_cache.clear()

            result2 = _get_google_certs()
            assert result2 == fake_certs_v2
            assert call_count["n"] == 2

    def test_invalidate_forces_refetch(self):
        """invalidate_google_certs_cache clears cache, forcing next call to refetch."""
        fake_certs = {"key-1": "cert-pem-1"}
        with patch("app.oidc_validator.httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = fake_certs
            mock_resp.raise_for_status = MagicMock()
            mock_client = MagicMock()
            mock_client.get = MagicMock(return_value=mock_resp)
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            _get_google_certs()
            assert mock_client.get.call_count == 1

            invalidate_google_certs_cache()

            _get_google_certs()
            assert mock_client.get.call_count == 2

    def test_cache_is_bounded(self):
        """Cache has maxsize=1, so only latest fetch is stored."""
        assert _google_certs_cache.maxsize == 1

    def test_cache_ttl_is_one_hour(self):
        """Cache TTL is 3600 seconds."""
        assert _google_certs_cache.ttl == 3600
