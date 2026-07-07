"""Tests for the email alert channel and Telegram delivery path."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from app.models import AlertChannel, AlertChannelType, Check, CheckStatus, Team
from app.routers.channels import _validate_channel_configuration
from app.handlers import _send_channel_alert
from app.integrations.email import _send_sync, EmailNotConfiguredError


def _make_check():
    return Check(
        check_id="check-1", team_id="team-1", name="Nightly Backup",
        token="tok", period_seconds=3600, grace_seconds=300,
        status=CheckStatus.LATE, created_at="2026-01-01T00:00:00Z",
    )


def _make_team():
    return Team(
        team_id="team-1", name="SRE", slug="sre",
        created_at="2026-01-01T00:00:00Z", created_by="user-1",
    )


def _make_channel(channel_type, configuration):
    return AlertChannel(
        channel_id="chan-1", team_id="team-1", name="oncall",
        display_name="On-call", type=channel_type,
        configuration=configuration, shared=False,
        created_at="2026-01-01T00:00:00Z", created_by="user-1",
    )


class TestEmailChannelValidation:
    def test_valid_recipients_accepted(self):
        _validate_channel_configuration(
            AlertChannelType.EMAIL,
            {"recipients": ["oncall@example.com", "sre@example.com"]},
        )

    def test_missing_recipients_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _validate_channel_configuration(AlertChannelType.EMAIL, {})
        assert exc.value.status_code == 400

    def test_non_list_recipients_rejected(self):
        with pytest.raises(HTTPException):
            _validate_channel_configuration(
                AlertChannelType.EMAIL, {"recipients": "oncall@example.com"}
            )

    def test_invalid_address_rejected(self):
        with pytest.raises(HTTPException):
            _validate_channel_configuration(
                AlertChannelType.EMAIL, {"recipients": ["not-an-email"]}
            )

    def test_too_many_recipients_rejected(self):
        recipients = [f"user{i}@example.com" for i in range(21)]
        with pytest.raises(HTTPException):
            _validate_channel_configuration(
                AlertChannelType.EMAIL, {"recipients": recipients}
            )


class TestSmtpSend:
    def test_unconfigured_smtp_raises(self):
        settings = MagicMock()
        settings.smtp_host = ""
        with patch("app.integrations.email.get_settings", return_value=settings):
            with pytest.raises(EmailNotConfiguredError):
                _send_sync(["a@example.com"], "subject", "body")

    def test_send_uses_tls_and_login(self):
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_username = "user"
        settings.smtp_password = "pass"
        settings.smtp_from = "PulseChecks <alerts@example.com>"
        settings.smtp_use_tls = True

        with patch("app.integrations.email.get_settings", return_value=settings), \
             patch("app.integrations.email.smtplib.SMTP") as mock_smtp:
            server = mock_smtp.return_value.__enter__.return_value
            _send_sync(["a@example.com"], "subject", "body")

        mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=15)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("user", "pass")
        server.send_message.assert_called_once()
        sent = server.send_message.call_args[0][0]
        assert sent["To"] == "a@example.com"
        assert sent["From"] == "PulseChecks <alerts@example.com>"


class TestSendChannelAlert:
    @pytest.mark.asyncio
    async def test_email_channel_sends_late_alert(self):
        channel = _make_channel(
            AlertChannelType.EMAIL, {"recipients": ["oncall@example.com"]}
        )
        with patch(
            "app.integrations.email.send_late_alert_email",
            new=AsyncMock(return_value=True),
        ) as mock_send:
            ok = await _send_channel_alert(
                channel, _make_check(), _make_team(), None, MagicMock()
            )
        assert ok is True
        mock_send.assert_awaited_once()
        assert mock_send.await_args[0][0] == ["oncall@example.com"]

    @pytest.mark.asyncio
    async def test_email_channel_without_recipients_fails(self):
        channel = _make_channel(AlertChannelType.EMAIL, {})
        ok = await _send_channel_alert(
            channel, _make_check(), _make_team(), None, MagicMock()
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_telegram_channel_sends_message(self):
        channel = _make_channel(
            AlertChannelType.TELEGRAM,
            {"bot_token": "123:abc", "chat_id": "-100"},
        )
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.handlers.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            ok = await _send_channel_alert(
                channel, _make_check(), _make_team(), None, MagicMock()
            )

        assert ok is True
        url = mock_client.post.await_args[0][0]
        assert url == "https://api.telegram.org/bot123:abc/sendMessage"
        payload = mock_client.post.await_args.kwargs["json"]
        assert payload["chat_id"] == "-100"
        assert "Nightly Backup" in payload["text"]

    @pytest.mark.asyncio
    async def test_telegram_channel_missing_config_fails(self):
        channel = _make_channel(AlertChannelType.TELEGRAM, {"bot_token": "123:abc"})
        ok = await _send_channel_alert(
            channel, _make_check(), _make_team(), None, MagicMock()
        )
        assert ok is False
