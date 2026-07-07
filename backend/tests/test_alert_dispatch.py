"""Tests for the durable alert delivery pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.alert_dispatch import (
    enqueue_check_alerts,
    process_delivery,
    process_due_deliveries,
    BACKOFF_BASE_SECONDS,
    MAX_ATTEMPTS,
)
from app.models import AlertChannel, AlertChannelType, AlertDelivery, Check, CheckStatus, Team


def _check(channels=("chan-1",)):
    return Check(
        check_id="check-1", team_id="team-1", name="Nightly Backup",
        token="tok", period_seconds=3600, grace_seconds=300,
        status=CheckStatus.LATE, created_at="2026-01-01T00:00:00Z",
        alert_channels=list(channels),
    )


def _team():
    return Team(team_id="team-1", name="SRE", slug="sre",
                created_at="2026-01-01T00:00:00Z", created_by="user-1")


def _channel(channel_id="chan-1"):
    return AlertChannel(
        channel_id=channel_id, team_id="team-1", name="oncall",
        display_name="On-call", type=AlertChannelType.MATTERMOST,
        configuration={"webhook_url": "https://chat.example.com/hooks/x"},
        shared=False, created_at="2026-01-01T00:00:00Z", created_by="user-1",
    )


def _delivery(attempts=0, max_attempts=MAX_ATTEMPTS):
    return AlertDelivery(
        delivery_id="del-1", team_id="team-1", check_id="check-1",
        check_name="Nightly Backup", channel_id="chan-1",
        channel_type="mattermost", channel_name="On-call",
        alert_type="late", status="pending", attempts=attempts,
        max_attempts=max_attempts, next_attempt_at=0,
        created_at="2026-01-01T00:00:00Z",
    )


class TestEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_only_creates_pending_records(self):
        db = AsyncMock()
        db.get_alert_channel.return_value = _channel()

        deliveries = await enqueue_check_alerts(db, _check(), "recovery", attempt_now=False)

        assert len(deliveries) == 1
        assert deliveries[0].status == "pending"
        assert deliveries[0].alert_type == "recovery"
        assert deliveries[0].channel_name == "On-call"
        db.create_alert_delivery.assert_called_once()
        db.update_alert_delivery.assert_not_called()  # no attempt made

    @pytest.mark.asyncio
    async def test_enqueue_with_no_channels_is_noop(self):
        db = AsyncMock()
        deliveries = await enqueue_check_alerts(db, _check(channels=()), "late")
        assert deliveries == []
        db.create_alert_delivery.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_channel_dead_letters_immediately(self):
        db = AsyncMock()
        db.get_alert_channel.return_value = None

        deliveries = await enqueue_check_alerts(db, _check(), "late", attempt_now=False)

        assert deliveries[0].status == "failed"
        assert "not found" in deliveries[0].last_error

    @pytest.mark.asyncio
    async def test_attempt_now_delivers(self):
        db = AsyncMock()
        db.get_alert_channel.return_value = _channel()

        with patch("app.handlers._send_channel_alert", new=AsyncMock(return_value=True)):
            deliveries = await enqueue_check_alerts(db, _check(), "late", team=_team())

        assert deliveries[0].status == "delivered"
        assert deliveries[0].attempts == 1
        assert deliveries[0].delivered_at is not None


class TestRetrySemantics:
    @pytest.mark.asyncio
    async def test_failure_schedules_exponential_backoff(self):
        db = AsyncMock()
        db.get_alert_channel.return_value = _channel()
        delivery = _delivery(attempts=0)

        with patch("app.handlers._send_channel_alert", new=AsyncMock(return_value=False)), \
             patch("app.alert_dispatch.get_current_time_seconds", return_value=1000):
            ok = await process_delivery(db, delivery, check=_check(), team=_team())

        assert ok is False
        assert delivery.status == "pending"
        assert delivery.attempts == 1
        assert delivery.next_attempt_at == 1000 + BACKOFF_BASE_SECONDS  # 2 minutes

        # Second failure doubles the backoff
        with patch("app.handlers._send_channel_alert", new=AsyncMock(return_value=False)), \
             patch("app.alert_dispatch.get_current_time_seconds", return_value=2000):
            await process_delivery(db, delivery, check=_check(), team=_team())

        assert delivery.attempts == 2
        assert delivery.next_attempt_at == 2000 + BACKOFF_BASE_SECONDS * 2

    @pytest.mark.asyncio
    async def test_exhausted_attempts_dead_letter(self):
        db = AsyncMock()
        db.get_alert_channel.return_value = _channel()
        delivery = _delivery(attempts=MAX_ATTEMPTS - 1)

        with patch("app.handlers._send_channel_alert", new=AsyncMock(return_value=False)):
            ok = await process_delivery(db, delivery, check=_check(), team=_team())

        assert ok is False
        assert delivery.status == "failed"  # dead-letter state
        assert delivery.attempts == MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_exception_counts_as_failed_attempt(self):
        db = AsyncMock()
        db.get_alert_channel.return_value = _channel()
        delivery = _delivery()

        with patch("app.handlers._send_channel_alert", new=AsyncMock(side_effect=RuntimeError("boom"))):
            ok = await process_delivery(db, delivery, check=_check(), team=_team())

        assert ok is False
        assert delivery.status == "pending"
        assert "boom" in delivery.last_error

    @pytest.mark.asyncio
    async def test_deleted_check_dead_letters(self):
        db = AsyncMock()
        db.get_check.return_value = None
        delivery = _delivery()

        ok = await process_delivery(db, delivery)

        assert ok is False
        assert delivery.status == "failed"
        assert "no longer exists" in delivery.last_error


class TestQueueDrain:
    @pytest.mark.asyncio
    async def test_drain_processes_due_deliveries(self):
        db = AsyncMock()
        db.query_due_alert_deliveries.return_value = [_delivery(), _delivery()]
        db.get_check.return_value = _check()
        db.get_team.return_value = _team()
        db.get_alert_channel.return_value = _channel()

        with patch("app.handlers._send_channel_alert", new=AsyncMock(return_value=True)):
            stats = await process_due_deliveries(db)

        assert stats == {"processed": 2, "delivered": 2, "failed": 0}

    @pytest.mark.asyncio
    async def test_drain_with_empty_queue(self):
        db = AsyncMock()
        db.query_due_alert_deliveries.return_value = []
        stats = await process_due_deliveries(db)
        assert stats["processed"] == 0


class TestDeadMansSwitch:
    @pytest.mark.asyncio
    async def test_heartbeat_pinged_when_configured(self):
        from app.handlers import _ping_heartbeat

        settings = MagicMock()
        settings.heartbeat_url = "https://hc-ping.example.com/uuid"
        mock_client = AsyncMock()

        with patch("app.handlers.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            await _ping_heartbeat(settings)

        mock_client.get.assert_awaited_once_with("https://hc-ping.example.com/uuid")

    @pytest.mark.asyncio
    async def test_heartbeat_skipped_when_unset(self):
        from app.handlers import _ping_heartbeat

        settings = MagicMock()
        settings.heartbeat_url = ""
        with patch("app.handlers.httpx.AsyncClient") as mock_cls:
            await _ping_heartbeat(settings)
        mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_failure_never_raises(self):
        from app.handlers import _ping_heartbeat

        settings = MagicMock()
        settings.heartbeat_url = "https://hc-ping.example.com/uuid"
        with patch("app.handlers.httpx.AsyncClient", side_effect=RuntimeError("network down")):
            await _ping_heartbeat(settings)  # must not raise
