"""Tests for advanced alerting features (escalation and suppression)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models import Check, CheckStatus
from app.handlers import _is_suppressed, _should_suppress, _should_escalate
from app.utils import get_iso_timestamp, get_current_time_seconds


class TestEscalationLogic:
    """Test escalation logic functions."""

    def test_should_escalate_no_config(self):
        """Test escalation when no escalation is configured."""
        check = Check(
            check_id="test-check",
            team_id="test-team", 
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
        )
        
        current_time = get_current_time_seconds()
        assert not _should_escalate(check, current_time)

    def test_should_escalate_no_initial_alert(self):
        """Test escalation when no initial alert has been sent."""
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check", 
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            escalation_minutes=15,
            escalation_alert_channels=["test-channel-id"],
        )
        
        current_time = get_current_time_seconds()
        assert not _should_escalate(check, current_time)

    def test_should_escalate_already_triggered(self):
        """Test escalation when already triggered."""
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token", 
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            escalation_minutes=15,
            escalation_alert_channels=["test-channel-id"],
            last_alert_at=get_iso_timestamp(),
            escalation_triggered_at=get_iso_timestamp(),
        )
        
        current_time = get_current_time_seconds()
        assert not _should_escalate(check, current_time)

    def test_should_escalate_time_not_reached(self):
        """Test escalation when escalation time hasn't been reached."""
        # Alert sent 5 minutes ago, escalation set for 15 minutes
        alert_time = get_current_time_seconds() - (5 * 60)
        
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            escalation_minutes=15,
            escalation_alert_channels=["test-channel-id"],
            last_alert_at=get_iso_timestamp(alert_time),
        )
        
        current_time = get_current_time_seconds()
        assert not _should_escalate(check, current_time)

    def test_should_escalate_time_reached(self):
        """Test escalation when escalation time has been reached."""
        # Alert sent 20 minutes ago, escalation set for 15 minutes
        alert_time = get_current_time_seconds() - (20 * 60)
        
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            escalation_minutes=15,
            escalation_alert_channels=["test-channel-id"],
            last_alert_at=get_iso_timestamp(alert_time),
        )
        
        current_time = get_current_time_seconds()
        assert _should_escalate(check, current_time)


class TestSuppressionLogic:
    """Test suppression logic functions."""

    def test_is_suppressed_no_suppression(self):
        """Test suppression check when no suppression is active."""
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
        )
        
        current_time = get_current_time_seconds()
        assert not _is_suppressed(check, current_time)

    def test_is_suppressed_expired(self):
        """Test suppression check when suppression has expired."""
        # Suppressed until 1 hour ago
        suppressed_until_time = get_current_time_seconds() - 3600
        
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            suppressed_until=get_iso_timestamp(suppressed_until_time),
        )
        
        current_time = get_current_time_seconds()
        assert not _is_suppressed(check, current_time)

    def test_is_suppressed_active(self):
        """Test suppression check when suppression is active."""
        # Suppressed until 1 hour from now
        suppressed_until_time = get_current_time_seconds() + 3600
        
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            suppressed_until=get_iso_timestamp(suppressed_until_time),
        )
        
        current_time = get_current_time_seconds()
        assert _is_suppressed(check, current_time)

    def test_should_suppress_no_config(self):
        """Test suppression trigger when no suppression is configured."""
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            consecutive_alert_count=5,
        )
        
        assert not _should_suppress(check)

    def test_should_suppress_threshold_not_reached(self):
        """Test suppression trigger when threshold not reached."""
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            suppress_after_count=5,
            suppress_duration_minutes=120,
            consecutive_alert_count=3,
        )
        
        assert not _should_suppress(check)

    def test_should_suppress_threshold_reached(self):
        """Test suppression trigger when threshold is reached."""
        check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            suppress_after_count=3,
            suppress_duration_minutes=120,
            consecutive_alert_count=3,
        )
        
        assert _should_suppress(check)


class TestAdvancedAlertingIntegration:
    """Test integration of advanced alerting features."""

    @pytest.mark.asyncio
    async def test_enhanced_late_detector_suppression(self):
        """Test that late detector respects suppression."""
        from app.handlers import _late_detector_impl
        
        # Mock suppressed check
        suppressed_until_time = get_current_time_seconds() + 3600
        mock_check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            status=CheckStatus.LATE,
            suppressed_until=get_iso_timestamp(suppressed_until_time),
        )

        with patch('app.handlers.create_db_client') as mock_create_db:
            mock_db = AsyncMock()
            mock_create_db.return_value = mock_db
            mock_db.query_due_checks.return_value = [mock_check]
            
            with patch('app.handlers.get_settings') as mock_settings:
                mock_settings.return_value.aws_region = "us-east-1"
                with patch('app.handlers.get_metrics_client') as mock_metrics:
                    with patch('boto3.client') as mock_boto_client:
                        result = await _late_detector_impl({}, None)
                        
                        # Should process 1 check but suppress 1 alert
                        assert result["statusCode"] == 200
                        body = eval(result["body"])
                        assert body["checksProcessed"] == 1
                        assert body["alertsSuppressed"] == 1
                        assert body["channelAlertsQueued"] == 0

    @pytest.mark.asyncio 
    async def test_enhanced_late_detector_escalation(self):
        """Test that late detector triggers escalation."""
        from app.handlers import _late_detector_impl
        
        # Mock check ready for escalation
        alert_time = get_current_time_seconds() - (20 * 60)  # 20 minutes ago
        mock_check = Check(
            check_id="test-check",
            team_id="test-team",
            name="Test Check",
            token="test-token",
            period_seconds=3600,
            grace_seconds=300,
            created_at=get_iso_timestamp(),
            status=CheckStatus.LATE,
            escalation_minutes=15,
            escalation_alert_channels=["test-channel-id"],
            last_alert_at=get_iso_timestamp(alert_time),
        )

        with patch('app.handlers.create_db_client') as mock_create_db:
            mock_db = AsyncMock()
            mock_create_db.return_value = mock_db
            mock_db.query_due_checks.return_value = [mock_check]
            mock_db.get_team.return_value = MagicMock(name="Test Team", mattermost_webhook_url=None)
            
            with patch('app.handlers.get_settings') as mock_settings:
                mock_settings.return_value.aws_region = "us-east-1"
                with patch('app.handlers.get_current_time_seconds') as mock_current_time:
                    mock_current_time.return_value = get_current_time_seconds()  # Current time
                    with patch('app.handlers.get_metrics_client') as mock_metrics:
                        with patch('boto3.client') as mock_boto_client:
                            with patch('app.handlers._send_escalated_alerts') as mock_escalate:
                                result = await _late_detector_impl({}, None)
                                
                                # Should trigger escalation
                                assert result["statusCode"] == 200
                                body = eval(result["body"])
                                assert body["escalationsTriggered"] == 1
                                mock_escalate.assert_called_once()
