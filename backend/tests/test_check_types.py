"""Tests covering distinct behaviour of cron, heartbeat, and http check types."""
import pytest
from pydantic import ValidationError

from app.models.requests import CreateCheckRequest
from app.models.entities import Check, CheckStatus
from app.models.enums import CheckType
from app.utils import calculate_next_due_from_cron, validate_cron_expression


# ---------------------------------------------------------------------------
# Enum distinctness
# ---------------------------------------------------------------------------

def test_check_types_are_distinct():
    assert CheckType.CRON != CheckType.HEARTBEAT
    assert CheckType.HEARTBEAT != CheckType.HTTP
    assert CheckType.CRON != CheckType.HTTP


def test_check_type_values():
    assert CheckType.CRON.value == "cron"
    assert CheckType.HEARTBEAT.value == "heartbeat"
    assert CheckType.HTTP.value == "http"


# ---------------------------------------------------------------------------
# CreateCheckRequest validation
# ---------------------------------------------------------------------------

class TestCreateCheckRequestCron:
    def test_valid_cron(self):
        r = CreateCheckRequest(name="nightly", schedule="0 2 * * *", graceSeconds=300, type="cron")
        assert r.type == "cron"
        assert r.schedule == "0 2 * * *"
        assert r.period_seconds is None

    def test_missing_schedule_raises(self):
        with pytest.raises(ValidationError, match="schedule is required"):
            CreateCheckRequest(name="x", graceSeconds=0, type="cron")

    def test_invalid_schedule_raises(self):
        with pytest.raises(ValidationError, match="valid cron expression"):
            CreateCheckRequest(name="x", schedule="not-valid", graceSeconds=0, type="cron")

    def test_period_seconds_ignored_for_cron(self):
        # period_seconds can be omitted for cron — no error
        r = CreateCheckRequest(name="x", schedule="*/5 * * * *", graceSeconds=60, type="cron")
        assert r.period_seconds is None


class TestCreateCheckRequestHeartbeat:
    def test_valid_heartbeat(self):
        r = CreateCheckRequest(name="daemon", periodSeconds=60, graceSeconds=10, type="heartbeat")
        assert r.type == "heartbeat"
        assert r.period_seconds == 60
        assert r.schedule is None

    def test_missing_period_raises(self):
        with pytest.raises(ValidationError, match="periodSeconds is required"):
            CreateCheckRequest(name="x", graceSeconds=0, type="heartbeat")

    def test_grace_exceeds_period_raises(self):
        with pytest.raises(ValidationError, match="grace_seconds cannot exceed period_seconds"):
            CreateCheckRequest(name="x", periodSeconds=60, graceSeconds=120, type="heartbeat")


class TestCreateCheckRequestHttp:
    def test_valid_http(self):
        r = CreateCheckRequest(
            name="api", periodSeconds=300, graceSeconds=60, type="http",
            url="https://example.com/health"
        )
        assert r.type == "http"
        assert r.url == "https://example.com/health"

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError, match="url is required"):
            CreateCheckRequest(name="x", periodSeconds=60, graceSeconds=0, type="http")

    def test_missing_period_raises(self):
        with pytest.raises(ValidationError, match="periodSeconds is required"):
            CreateCheckRequest(name="x", graceSeconds=0, type="http", url="https://example.com")

    def test_invalid_url_scheme_raises(self):
        with pytest.raises(ValidationError, match="http"):
            CreateCheckRequest(
                name="x", periodSeconds=60, graceSeconds=0, type="http",
                url="ftp://example.com"
            )


# ---------------------------------------------------------------------------
# Check entity — schedule field
# ---------------------------------------------------------------------------

def test_check_entity_stores_schedule():
    check = Check(
        check_id="c1", team_id="t1", name="nightly", token="tok",
        schedule="0 2 * * *", grace_seconds=300,
        created_at="2026-01-01T00:00:00Z", type=CheckType.CRON,
    )
    assert check.schedule == "0 2 * * *"
    assert check.period_seconds is None


def test_check_entity_heartbeat_no_schedule():
    check = Check(
        check_id="c2", team_id="t1", name="daemon", token="tok",
        period_seconds=60, grace_seconds=10,
        created_at="2026-01-01T00:00:00Z", type=CheckType.HEARTBEAT,
    )
    assert check.schedule is None
    assert check.period_seconds == 60


# ---------------------------------------------------------------------------
# Cron utilities
# ---------------------------------------------------------------------------

def test_validate_cron_expression_valid():
    assert validate_cron_expression("0 2 * * *") is True
    assert validate_cron_expression("*/15 * * * *") is True
    assert validate_cron_expression("0 9 * * 1-5") is True


def test_validate_cron_expression_invalid():
    assert validate_cron_expression("not-a-cron") is False
    assert validate_cron_expression("99 99 99 99 99") is False


def test_calculate_next_due_from_cron_is_in_future():
    import time
    now = int(time.time())
    next_due = calculate_next_due_from_cron("* * * * *")  # every minute
    assert next_due > now
    assert next_due <= now + 120  # within 2 minutes


def test_calculate_next_due_from_cron_after_given_time():
    # After a known timestamp, next due for "0 2 * * *" should be next 2am
    from datetime import datetime, timezone
    base = int(datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    next_due = calculate_next_due_from_cron("0 2 * * *", after_seconds=base)
    expected = int(datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc).timestamp())
    assert next_due == expected


# ---------------------------------------------------------------------------
# Ping endpoint — heartbeat rejects /start and /fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heartbeat_rejects_start_signal():
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from app.models.enums import PingType
    from app.routers.ping import _record_ping_internal

    mock_db = AsyncMock()
    mock_db.get_check_by_token.return_value = Check(
        check_id="c1", team_id="t1", name="daemon", token="tok",
        period_seconds=60, grace_seconds=10,
        status=CheckStatus.UP, created_at="2026-01-01T00:00:00Z",
        type=CheckType.HEARTBEAT,
    )

    with pytest.raises(HTTPException) as exc_info:
        await _record_ping_internal("tok", mock_db, PingType.START)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_heartbeat_rejects_fail_signal():
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from app.models.enums import PingType
    from app.routers.ping import _record_ping_internal

    mock_db = AsyncMock()
    mock_db.get_check_by_token.return_value = Check(
        check_id="c1", team_id="t1", name="daemon", token="tok",
        period_seconds=60, grace_seconds=10,
        status=CheckStatus.UP, created_at="2026-01-01T00:00:00Z",
        type=CheckType.HEARTBEAT,
    )

    with pytest.raises(HTTPException) as exc_info:
        await _record_ping_internal("tok", mock_db, PingType.FAIL)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_cron_accepts_start_signal():
    from unittest.mock import AsyncMock, patch
    from app.models.enums import PingType
    from app.routers.ping import _record_ping_internal

    mock_db = AsyncMock()
    mock_db.get_check_by_token.return_value = Check(
        check_id="c1", team_id="t1", name="nightly", token="tok",
        schedule="0 2 * * *", grace_seconds=300,
        status=CheckStatus.UP, created_at="2026-01-01T00:00:00Z",
        type=CheckType.CRON,
    )
    mock_db.create_ping = AsyncMock()

    with patch("app.routers.ping.get_metrics_client"):
        result = await _record_ping_internal("tok", mock_db, PingType.START)
    assert result.ok is True
