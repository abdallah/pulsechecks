"""Integration tests for SSRF validation in channel endpoints."""
import pytest
from app.routers.channels import _validate_channel_configuration
from app.models import AlertChannelType
from fastapi import HTTPException


class TestChannelSSRFValidation:
    """Test that channel creation validates webhook URLs for SSRF attacks."""

    def test_mattermost_channel_valid_webhook(self):
        """Mattermost channel with valid webhook URL should pass."""
        config = {
            "webhook_url": "https://mattermost.example.com/hooks/abcd1234"
        }
        # Should not raise
        _validate_channel_configuration(AlertChannelType.MATTERMOST, config)

    def test_mattermost_channel_localhost_webhook(self):
        """Mattermost channel with localhost webhook should be blocked."""
        config = {
            "webhook_url": "http://localhost:3000/hooks/webhook"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.MATTERMOST, config)
        assert exc_info.value.status_code == 400
        assert "blocked" in exc_info.value.detail.lower() or "localhost" in exc_info.value.detail.lower()

    def test_mattermost_channel_metadata_endpoint(self):
        """Mattermost channel with metadata endpoint should be blocked."""
        config = {
            "webhook_url": "http://169.254.169.254/latest/meta-data/"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.MATTERMOST, config)
        assert exc_info.value.status_code == 400

    def test_mattermost_channel_private_network(self):
        """Mattermost channel with private network IP should be blocked."""
        config = {
            "webhook_url": "http://192.168.1.100/webhook"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.MATTERMOST, config)
        assert exc_info.value.status_code == 400

    def test_webhook_channel_valid_webhook(self):
        """Webhook channel with valid webhook URL should pass."""
        config = {
            "webhook_url": "https://api.example.com/webhooks/alerts",
            "headers": {"Authorization": "Bearer token123"}
        }
        # Should not raise
        _validate_channel_configuration(AlertChannelType.WEBHOOK, config)

    def test_webhook_channel_gcp_metadata(self):
        """Webhook channel with GCP metadata endpoint should be blocked."""
        config = {
            "webhook_url": "http://metadata.google.internal/computeMetadata/v1/"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_webhook_channel_127_0_0_1(self):
        """Webhook channel with 127.0.0.1 should be blocked."""
        config = {
            "webhook_url": "http://127.0.0.1:8080/callback"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_webhook_channel_private_range_10(self):
        """Webhook channel with 10.x.x.x should be blocked."""
        config = {
            "webhook_url": "http://10.0.0.50/alert"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_webhook_channel_private_range_172(self):
        """Webhook channel with 172.16-31.x.x should be blocked."""
        config = {
            "webhook_url": "http://172.20.0.1/webhook"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_webhook_channel_missing_webhook_url(self):
        """Webhook channel without webhook_url should fail validation."""
        config = {
            "headers": {"Authorization": "Bearer token123"}
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400
        assert "webhook_url" in exc_info.value.detail.lower()

    def test_webhook_channel_invalid_scheme(self):
        """Webhook channel with invalid scheme should fail."""
        config = {
            "webhook_url": "ftp://example.com/webhook"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_mattermost_channel_missing_webhook_url(self):
        """Mattermost channel without webhook_url should fail validation."""
        config = {}
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.MATTERMOST, config)
        assert exc_info.value.status_code == 400
        assert "webhook_url" in exc_info.value.detail.lower()

    def test_sns_channel_no_webhook_validation(self):
        """SNS channel should not validate webhook_url."""
        config = {}
        # Should not raise - SNS doesn't need webhook_url
        _validate_channel_configuration(AlertChannelType.SNS, config)

    def test_telegram_channel_no_webhook_validation(self):
        """Telegram channel should not validate webhook_url."""
        config = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "-1001234567890"
        }
        # Should not raise
        _validate_channel_configuration(AlertChannelType.TELEGRAM, config)

    def test_webhook_channel_local_domain(self):
        """Webhook channel with .local domain should be blocked."""
        config = {
            "webhook_url": "http://webhook.local/alert"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_webhook_channel_localhost_domain(self):
        """Webhook channel with .localhost domain should be blocked."""
        config = {
            "webhook_url": "http://service.localhost/webhook"
        }
        with pytest.raises(HTTPException) as exc_info:
            _validate_channel_configuration(AlertChannelType.WEBHOOK, config)
        assert exc_info.value.status_code == 400

    def test_mattermost_channel_with_query_params(self):
        """Valid Mattermost webhook with query params should pass."""
        config = {
            "webhook_url": "https://mattermost.example.com/hooks/webhook123?token=abc"
        }
        # Should not raise
        _validate_channel_configuration(AlertChannelType.MATTERMOST, config)

    def test_webhook_channel_with_custom_headers(self):
        """Valid webhook channel with custom headers should pass."""
        config = {
            "webhook_url": "https://webhook.example.com/alert",
            "headers": {
                "Authorization": "Bearer token123",
                "X-Custom-Header": "value"
            }
        }
        # Should not raise
        _validate_channel_configuration(AlertChannelType.WEBHOOK, config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
