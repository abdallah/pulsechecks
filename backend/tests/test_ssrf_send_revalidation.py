"""Regression tests: SSRF revalidation at send time (handlers + test-notification)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

from app.handlers import _send_channel_alert
from app.routers.channels import _send_test_notification
from app.models import AlertChannelType


def _make_channel(channel_type, webhook_url):
    return SimpleNamespace(
        channel_id="ch-1",
        team_id="team-1",
        name="test",
        display_name="Test",
        type=channel_type,
        configuration={"webhook_url": webhook_url},
        shared=False,
    )


def _make_check():
    return SimpleNamespace(
        check_id="chk-1",
        name="my-check",
        team_id="team-1",
        status=SimpleNamespace(value="late"),
    )


def _make_team():
    return SimpleNamespace(team_id="team-1", name="My Team")


class TestHandlerWebhookSSRF:
    """_send_channel_alert revalidates SSRF before every outbound webhook request."""

    @pytest.mark.asyncio
    async def test_webhook_to_metadata_blocked(self):
        """Generic webhook targeting metadata endpoint is blocked at send time."""
        channel = _make_channel(AlertChannelType.WEBHOOK, "http://169.254.169.254/latest/meta-data/")
        check = _make_check()
        team = _make_team()

        result = await _send_channel_alert(channel, check, team, None, MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_webhook_to_localhost_blocked(self):
        """Generic webhook targeting localhost is blocked at send time."""
        channel = _make_channel(AlertChannelType.WEBHOOK, "http://127.0.0.1/steal")
        check = _make_check()
        team = _make_team()

        result = await _send_channel_alert(channel, check, team, None, MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_mattermost_to_internal_blocked(self):
        """Mattermost client revalidates SSRF before sending."""
        channel = _make_channel(AlertChannelType.MATTERMOST, "http://169.254.169.254/hook")
        check = _make_check()
        check.period_seconds = 3600
        check.grace_seconds = 300
        check.last_ping_at = "2025-01-01T00:00:00Z"
        team = _make_team()

        result = await _send_channel_alert(channel, check, team, None, MagicMock())
        assert result is False


class TestTestNotificationSSRF:
    """_send_test_notification revalidates SSRF before outbound request."""

    @pytest.mark.asyncio
    async def test_mattermost_test_to_metadata_blocked(self):
        channel = _make_channel(AlertChannelType.MATTERMOST, "http://169.254.169.254/hook")
        from fastapi import HTTPException
        with pytest.raises((HTTPException, ValueError)):
            await _send_test_notification(channel, "team-1")

    @pytest.mark.asyncio
    async def test_webhook_test_to_localhost_blocked(self):
        channel = _make_channel(AlertChannelType.WEBHOOK, "http://127.0.0.1/exfil")
        from fastapi import HTTPException
        with pytest.raises((HTTPException, ValueError)):
            await _send_test_notification(channel, "team-1")

    @pytest.mark.asyncio
    async def test_webhook_test_to_private_ip_blocked(self):
        channel = _make_channel(AlertChannelType.WEBHOOK, "http://10.0.0.1/internal")
        from fastapi import HTTPException
        with pytest.raises((HTTPException, ValueError)):
            await _send_test_notification(channel, "team-1")
