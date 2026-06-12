"""Regression tests: HTTP check SSRF protection at creation, update, and poll time."""
import socket
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.models.entities import Check, CheckStatus
from app.models.enums import PingType
from app.scheduler import _poll_single_check


def make_check(**kwargs):
    defaults = dict(
        check_id="test-check-1",
        team_id="team-1",
        name="Test HTTP Check",
        token="test-token-123",
        period_seconds=300,
        grace_seconds=60,
        status=CheckStatus.UP.value,
        created_at="2026-01-01T00:00:00Z",
        type="http",
        url="https://example.com",
        expected_status_code=200,
        expected_string=None,
        failure_threshold=1,
        consecutive_failure_count=0,
        next_due_at=None,
    )
    defaults.update(kwargs)
    return Check(**defaults)


class TestHTTPCheckSSRFCreation:
    """SSRF validation blocks unsafe URLs at check creation time."""

    def test_create_check_blocks_metadata_url(self):
        from app.models.requests import CreateCheckRequest
        with pytest.raises(ValueError, match="[Uu]nsafe|blocked"):
            CreateCheckRequest(
                name="Bad Check",
                periodSeconds=300,
                graceSeconds=60,
                type="http",
                url="http://169.254.169.254/latest/meta-data/",
            )

    def test_create_check_blocks_localhost(self):
        from app.models.requests import CreateCheckRequest
        with pytest.raises(ValueError, match="[Uu]nsafe|blocked"):
            CreateCheckRequest(
                name="Bad Check",
                periodSeconds=300,
                graceSeconds=60,
                type="http",
                url="http://localhost:8080/health",
            )

    def test_create_check_blocks_private_ip(self):
        from app.models.requests import CreateCheckRequest
        with pytest.raises(ValueError, match="[Uu]nsafe|blocked"):
            CreateCheckRequest(
                name="Bad Check",
                periodSeconds=300,
                graceSeconds=60,
                type="http",
                url="http://10.0.0.1/internal",
            )

    def test_create_check_allows_valid_external_url(self):
        from app.models.requests import CreateCheckRequest
        with patch("app.security.ssrf.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]):
            req = CreateCheckRequest(
                name="Good Check",
                periodSeconds=300,
                graceSeconds=60,
                type="http",
                url="https://example.com/health",
            )
            assert req.url == "https://example.com/health"


class TestHTTPCheckSSRFUpdate:
    """SSRF validation blocks unsafe URLs at check update time."""

    def test_update_check_blocks_metadata_url(self):
        from app.models.requests import UpdateCheckRequest
        with pytest.raises(ValueError, match="[Uu]nsafe|blocked"):
            UpdateCheckRequest(url="http://169.254.169.254/latest/meta-data/")

    def test_update_check_blocks_private_ip(self):
        from app.models.requests import UpdateCheckRequest
        with pytest.raises(ValueError, match="[Uu]nsafe|blocked"):
            UpdateCheckRequest(url="http://192.168.1.1/internal")

    def test_update_check_allows_valid_url(self):
        from app.models.requests import UpdateCheckRequest
        with patch("app.security.ssrf.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]):
            req = UpdateCheckRequest(url="https://example.com/health")
            assert req.url == "https://example.com/health"


class TestHTTPCheckSSRFPollTime:
    """SSRF revalidation at poll execution time — fail closed without making the request."""

    @pytest.mark.asyncio
    async def test_poll_blocks_metadata_url(self):
        """Polling a check with metadata URL records a failure without making a request."""
        check = make_check(url="http://169.254.169.254/latest/meta-data/")
        mock_client = AsyncMock()
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)

            # HTTP client should never be called
            mock_client.get.assert_not_called()
            # A failure ping should be recorded
            mock_ping.assert_called_once()
            assert mock_ping.call_args.kwargs["ping_type"] == PingType.FAIL
            assert mock_ping.call_args.kwargs["code"] == "ssrf_blocked"

    @pytest.mark.asyncio
    async def test_poll_blocks_localhost(self):
        check = make_check(url="http://localhost/steal")
        mock_client = AsyncMock()
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            mock_client.get.assert_not_called()
            mock_ping.assert_called_once()
            assert mock_ping.call_args.kwargs["code"] == "ssrf_blocked"

    @pytest.mark.asyncio
    async def test_poll_blocks_private_ip(self):
        check = make_check(url="http://10.0.0.1/internal")
        mock_client = AsyncMock()
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            mock_client.get.assert_not_called()
            assert mock_ping.call_args.kwargs["code"] == "ssrf_blocked"

    @pytest.mark.asyncio
    async def test_poll_allows_valid_url(self):
        """Valid external URLs are polled normally."""
        check = make_check(url="https://example.com/health")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_db = AsyncMock()

        with patch("app.security.ssrf.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]):
            with patch("app.scheduler.time.monotonic", side_effect=[1.0, 1.1]):
                with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
                    await _poll_single_check(mock_client, mock_db, check)
                    mock_client.get.assert_called_once()
                    assert mock_ping.call_args.kwargs["ping_type"] == PingType.SUCCESS


class TestNoRedirectFollowing:
    """HTTP poller must not follow redirects."""

    @pytest.mark.asyncio
    async def test_redirect_not_followed(self):
        """A 302 redirect is treated as a status mismatch, not followed."""
        check = make_check(url="https://example.com/health", expected_status_code=200)
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.text = ""
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_db = AsyncMock()

        with patch("app.security.ssrf.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]):
            with patch("app.scheduler.time.monotonic", side_effect=[1.0, 1.1]):
                with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
                    await _poll_single_check(mock_client, mock_db, check)
                    assert mock_ping.call_args.kwargs["ping_type"] == PingType.FAIL
                    assert mock_ping.call_args.kwargs["code"] == "302"
