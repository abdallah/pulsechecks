"""Tests for input validation and middleware."""
import pytest
from pydantic import ValidationError

from app.models.requests import (
    CreateTeamRequest,
    CreateCheckRequest,
    UpdateCheckRequest,
    PingRequest,
    CreateAlertTopicRequest,
    SubscribeAlertTopicRequest
)
from app.middleware import RateLimiter


class TestCreateTeamRequest:
    """Test CreateTeamRequest validation."""

    def test_valid_team_name(self):
        """Test valid team name."""
        request = CreateTeamRequest(name="My Team")
        assert request.name == "My Team"

    def test_team_name_with_special_chars(self):
        """Test team name with allowed special characters."""
        request = CreateTeamRequest(name="Team-1_Test")
        assert request.name == "Team-1_Test"

    def test_empty_team_name(self):
        """Test empty team name validation."""
        with pytest.raises(ValidationError) as exc_info:
            CreateTeamRequest(name="")
        assert "at least 1 character" in str(exc_info.value)

    def test_whitespace_team_name(self):
        """Test whitespace-only team name validation."""
        with pytest.raises(ValidationError) as exc_info:
            CreateTeamRequest(name="   ")
        assert "name cannot be empty" in str(exc_info.value)

    def test_invalid_characters_team_name(self):
        """Test team name with invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            CreateTeamRequest(name="Team@#$%")
        assert "can only contain letters, numbers" in str(exc_info.value)

    def test_team_name_too_long(self):
        """Test team name exceeding max length."""
        with pytest.raises(ValidationError) as exc_info:
            CreateTeamRequest(name="x" * 101)
        assert "at most 100 characters" in str(exc_info.value)


class TestCreateCheckRequest:
    """Test CreateCheckRequest validation."""

    def test_valid_check_request(self):
        """Test valid check creation request."""
        request = CreateCheckRequest(
            name="Daily Backup",
            periodSeconds=86400,
            graceSeconds=3600,
            alertTopics=["arn:aws:sns:us-east-1:123456789012:test-topic"]
        )
        assert request.name == "Daily Backup"
        assert request.period_seconds == 86400
        assert request.grace_seconds == 3600

    def test_period_too_short(self):
        """Test period_seconds below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCheckRequest(
                name="Test Check",
                periodSeconds=30,  # Below 60 minimum
                graceSeconds=300
            )
        assert "greater than or equal to 60" in str(exc_info.value)

    def test_period_too_long(self):
        """Test period_seconds above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCheckRequest(
                name="Test Check",
                periodSeconds=31536001,  # Above 1 year maximum
                graceSeconds=300
            )
        assert "less than or equal to 31536000" in str(exc_info.value)

    def test_grace_exceeds_period(self):
        """Test grace_seconds exceeding period_seconds."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCheckRequest(
                name="Test Check",
                periodSeconds=3600,
                graceSeconds=7200  # Exceeds period
            )
        assert "grace_seconds cannot exceed period_seconds" in str(exc_info.value)

    def test_invalid_sns_arn(self):
        """Test exceeding maximum alert channels."""
        channels = [f"channel-{i}" for i in range(11)]
        with pytest.raises(ValidationError) as exc_info:
            CreateCheckRequest(
                name="Test Check",
                period_seconds=3600,
                grace_seconds=300,
                alert_channels=channels
            )
        assert "Maximum 10 alert channels allowed" in str(exc_info.value)


class TestUpdateCheckRequest:
    """Test UpdateCheckRequest validation."""

    def test_valid_partial_update(self):
        """Test valid partial update request."""
        request = UpdateCheckRequest(name="Updated Check")
        assert request.name == "Updated Check"
        assert request.period_seconds is None

    def test_grace_exceeds_period_in_update(self):
        """Test grace_seconds exceeding period_seconds in update."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateCheckRequest(
                periodSeconds=3600,  # Both fields needed for validation
                graceSeconds=7200
            )
        assert "grace_seconds cannot exceed period_seconds" in str(exc_info.value)


class TestPingRequest:
    """Test PingRequest validation."""

    def test_valid_ping_data(self):
        """Test valid ping data."""
        request = PingRequest(data="Backup completed successfully")
        assert request.data == "Backup completed successfully"

    def test_sanitize_ping_data(self):
        """Test ping data sanitization."""
        request = PingRequest(data="Test\x00data\x01with\x02control\x03chars")
        # Control characters should be removed
        assert "\x00" not in request.data
        assert "\x01" not in request.data

    def test_ping_data_too_long(self):
        """Test ping data exceeding max length."""
        with pytest.raises(ValidationError) as exc_info:
            PingRequest(data="x" * 10001)
        assert "at most 10000 characters" in str(exc_info.value)


class TestCreateAlertTopicRequest:
    """Test CreateAlertTopicRequest validation."""

    def test_valid_topic_name(self):
        """Test valid topic name."""
        request = CreateAlertTopicRequest(name="test-topic")
        assert request.name == "test-topic"

    def test_invalid_topic_name_characters(self):
        """Test topic name with invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            CreateAlertTopicRequest(name="test@topic")
        assert "can only contain letters, numbers, hyphens, and underscores" in str(exc_info.value)


class TestSubscribeAlertTopicRequest:
    """Test SubscribeAlertTopicRequest validation."""

    def test_valid_email_subscription(self):
        """Test valid email subscription."""
        request = SubscribeAlertTopicRequest(
            protocol="email",
            endpoint="test@example.com"
        )
        assert request.protocol == "email"
        assert request.endpoint == "test@example.com"

    def test_valid_https_subscription(self):
        """Test valid HTTPS subscription."""
        request = SubscribeAlertTopicRequest(
            protocol="https",
            endpoint="https://example.com/webhook"
        )
        assert request.protocol == "https"

    def test_valid_sms_subscription(self):
        """Test valid SMS subscription."""
        request = SubscribeAlertTopicRequest(
            protocol="sms",
            endpoint="+1234567890"
        )
        assert request.protocol == "sms"

    def test_invalid_protocol(self):
        """Test invalid protocol."""
        with pytest.raises(ValidationError) as exc_info:
            SubscribeAlertTopicRequest(
                protocol="invalid",
                endpoint="test@example.com"
            )
        assert "protocol must be one of" in str(exc_info.value)

    def test_invalid_email_format(self):
        """Test invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            SubscribeAlertTopicRequest(
                protocol="email",
                endpoint="invalid-email"
            )
        assert "Invalid email address format" in str(exc_info.value)

    def test_invalid_https_format(self):
        """Test invalid HTTPS URL format."""
        with pytest.raises(ValidationError) as exc_info:
            SubscribeAlertTopicRequest(
                protocol="https",
                endpoint="http://example.com"  # HTTP not HTTPS
            )
        assert "Invalid HTTPS URL format" in str(exc_info.value)

    def test_invalid_sms_format(self):
        """Test invalid SMS phone number format."""
        with pytest.raises(ValidationError) as exc_info:
            SubscribeAlertTopicRequest(
                protocol="sms",
                endpoint="1234567890"  # Missing + prefix
            )
        assert "Invalid phone number format" in str(exc_info.value)


class TestRateLimiter:
    """Test RateLimiter functionality."""

    def test_rate_limiter_allows_requests_under_limit(self):
        """Test rate limiter allows requests under the limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # Should allow first 5 requests
        for i in range(5):
            assert limiter.is_allowed("test-key") is True

    def test_rate_limiter_blocks_requests_over_limit(self):
        """Test rate limiter blocks requests over the limit."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Allow first 2 requests
        assert limiter.is_allowed("test-key") is True
        assert limiter.is_allowed("test-key") is True
        
        # Block 3rd request
        assert limiter.is_allowed("test-key") is False

    def test_rate_limiter_different_keys(self):
        """Test rate limiter handles different keys independently."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        # Each key should be allowed independently
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key2") is True
        
        # But second request for same key should be blocked
        assert limiter.is_allowed("key1") is False
