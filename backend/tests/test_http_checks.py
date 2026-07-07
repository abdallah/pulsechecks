"""Tests for HTTP endpoint checks — polling, failure threshold, string matching."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.models.entities import Check, CheckStatus
from app.models.enums import PingType
from app.scheduler import _poll_single_check, poll_http_checks


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


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


def get_ping_call_args(mock_ping):
    """Extract ping_type and data from mock call regardless of positional/keyword usage."""
    call = mock_ping.call_args
    ping_type = call.kwargs.get("ping_type") if call.kwargs.get("ping_type") else (call.args[2] if len(call.args) > 2 else None)
    data = call.kwargs.get("data") if "data" in call.kwargs else (call.args[3] if len(call.args) > 3 else None)
    return ping_type, data


class TestPollSingleCheck:
    @pytest.mark.asyncio
    async def test_success_ping_recorded_on_200(self):
        check = make_check()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_db = AsyncMock()

        with patch("app.scheduler.time.monotonic", side_effect=[10.0, 10.123]), \
             patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            with patch("app.routers.ping._record_ping_internal", mock_ping):
                await _poll_single_check(mock_client, mock_db, check)
                mock_ping.assert_called_once()
                ping_type, _ = get_ping_call_args(mock_ping)
                assert ping_type == PingType.SUCCESS
                assert 122 <= mock_ping.call_args.kwargs["response_time_ms"] <= 123
                assert mock_ping.call_args.kwargs["code"] is None

    @pytest.mark.asyncio
    async def test_fail_ping_on_wrong_status_code(self):
        check = make_check(expected_status_code=200)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_db = AsyncMock()

        with patch("app.scheduler.time.monotonic", side_effect=[10.0, 10.25]), \
             patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            mock_ping.assert_called_once()
            ping_type, data = get_ping_call_args(mock_ping)
            assert ping_type == PingType.FAIL
            assert "500" in str(data)
            assert "200" in str(data)
            assert mock_ping.call_args.kwargs["code"] == "500"
            assert mock_ping.call_args.kwargs["response_time_ms"] == 250

    @pytest.mark.asyncio
    async def test_fail_ping_on_missing_expected_string(self):
        check = make_check(expected_string="HEALTHY")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK but missing keyword"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            ping_type, data = get_ping_call_args(mock_ping)
            assert ping_type == PingType.FAIL
            assert "HEALTHY" in str(data)

    @pytest.mark.asyncio
    async def test_success_when_expected_string_present(self):
        check = make_check(expected_string="HEALTHY")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Status: HEALTHY"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            ping_type, _ = get_ping_call_args(mock_ping)
            assert ping_type == PingType.SUCCESS

    @pytest.mark.asyncio
    async def test_fail_ping_on_timeout(self):
        import httpx
        check = make_check()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            ping_type, data = get_ping_call_args(mock_ping)
            assert ping_type == PingType.FAIL
            assert "timeout" in str(data).lower()

    @pytest.mark.asyncio
    async def test_fail_ping_on_connection_error(self):
        import httpx
        check = make_check()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("connection refused")
        mock_db = AsyncMock()

        with patch("app.routers.ping._record_ping_internal", new_callable=AsyncMock) as mock_ping:
            await _poll_single_check(mock_client, mock_db, check)
            ping_type, _ = get_ping_call_args(mock_ping)
            assert ping_type == PingType.FAIL


class TestPollHttpChecks:
    @pytest.mark.asyncio
    async def test_skips_checks_not_yet_due(self):
        """Due-filtering now happens in the database query — an empty
        result means nothing is polled."""
        mock_db = AsyncMock()
        mock_db.query_due_http_checks.return_value = []

        with patch("app.scheduler.create_db_client", return_value=mock_db), \
             patch("app.scheduler._poll_single_check", new_callable=AsyncMock) as mock_poll:
            await poll_http_checks()
            mock_poll.assert_not_called()

    @pytest.mark.asyncio
    async def test_polls_checks_that_are_due(self):
        past_due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        check = make_check(next_due_at=past_due)

        mock_db = AsyncMock()
        mock_db.query_due_http_checks.return_value = [check]

        with patch("app.scheduler.create_db_client", return_value=mock_db), \
             patch("app.scheduler._poll_single_check", new_callable=AsyncMock) as mock_poll:
            await poll_http_checks()
            mock_poll.assert_called_once()

    @pytest.mark.asyncio
    async def test_polls_checks_with_no_due_date(self):
        """Checks with next_due_at=None should be polled (never been checked)."""
        check = make_check(next_due_at=None)

        mock_db = AsyncMock()
        mock_db.query_due_http_checks.return_value = [check]

        with patch("app.scheduler.create_db_client", return_value=mock_db), \
             patch("app.scheduler._poll_single_check", new_callable=AsyncMock) as mock_poll:
            await poll_http_checks()
            mock_poll.assert_called_once()


class TestInternalEndpoints:
    def test_late_detection_endpoint_exists(self, client):
        """Verify /internal/late-detection returns something other than 404."""
        resp = client.post("/internal/late-detection")
        assert resp.status_code != 404

    def test_http_poll_endpoint_exists(self, client):
        """Verify /internal/http-poll returns something other than 404."""
        with patch("app.scheduler.poll_http_checks", new_callable=AsyncMock):
            resp = client.post("/internal/http-poll")
            assert resp.status_code != 404
