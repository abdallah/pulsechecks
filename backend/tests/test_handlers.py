"""Tests for Lambda handler functions."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError

from app.handlers import late_detector_handler
from app.models import Check, CheckStatus


@pytest.fixture
def sample_check():
    """Sample check for testing."""
    return Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="token-123",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.UP,
        created_at="2023-01-01T00:00:00Z",
        alert_channels=["test-channel-id"]
    )


@pytest.fixture
def eventbridge_event():
    """Sample EventBridge event."""
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2023-01-01T00:00:00Z",
        "region": "us-east-1",
        "detail": {}
    }


@pytest.fixture
def sqs_event():
    """Sample SQS event."""
    return {
        "Records": [
            {
                "messageId": "test-message-id",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "checkId": "check-123",
                    "checkName": "Test Check",
                    "teamId": "team-123",
                    "topicArns": ["arn:aws:sns:us-east-1:123456789012:test-topic"]
                }),
                "attributes": {},
                "messageAttributes": {},
                "md5OfBody": "test-md5",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                "awsRegion": "us-east-1"
            }
        ]
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    return context


class TestLateDetectorHandler:
    """Test late detector Lambda handler."""

    @patch('app.handlers.get_settings')
    @patch('app.handlers.create_db_client')
    @patch('app.handlers.boto3.client')
    @patch('app.handlers.get_current_time_seconds')
    @patch('app.handlers.get_iso_timestamp')
    def test_late_detector_no_due_checks(
        self, mock_timestamp, mock_current_time, mock_boto3, mock_create_db, mock_settings,
        eventbridge_event, lambda_context
    ):
        """Test late detector with no due checks."""
        # Setup mocks
        mock_current_time.return_value = 1672531200
        mock_timestamp.return_value = "2023-01-01T00:00:00Z"
        mock_settings.return_value.aws_region = "us-east-1"
        
        mock_db = AsyncMock()
        mock_db.query_due_checks.return_value = []
        mock_create_db.return_value = mock_db

        # Execute handler
        result = late_detector_handler(eventbridge_event, lambda_context)

        # Verify result
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["checksProcessed"] == 0
        assert body["channelAlertsQueued"] == 0
        assert body["channelAlertsSent"] == 0

        # Verify database was queried
        mock_db.query_due_checks.assert_called_once_with(1672531200, limit=100)

    @patch('app.handlers.get_settings')
    @patch('app.handlers.create_db_client')
    @patch('app.handlers.boto3.client')
    @patch('app.handlers.get_current_time_seconds')
    @patch('app.handlers.get_iso_timestamp')
    def test_late_detector_with_due_checks_success(
        self, mock_timestamp, mock_current_time, mock_boto3, mock_create_db, mock_settings,
        eventbridge_event, lambda_context, sample_check
    ):
        """Test late detector with due checks that go late successfully."""
        # Setup mocks
        mock_current_time.return_value = 1672531200
        mock_timestamp.return_value = "2023-01-01T00:00:00Z"
        mock_settings.return_value.aws_region = "us-east-1"
        
        mock_db = AsyncMock()
        mock_db.query_due_checks.return_value = [sample_check]
        mock_db.update_check_to_late.return_value = True  # Successfully went late
        mock_create_db.return_value = mock_db

        mock_sns = MagicMock()
        mock_boto3.return_value = mock_sns

        # Execute handler
        result = late_detector_handler(eventbridge_event, lambda_context)

        # Verify result
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["checksProcessed"] == 1
        assert body["channelAlertsQueued"] == 0  # No channels - using modern alert channels only
        assert body["channelAlertsSent"] == 0  # No channels configured

        # Verify database operations
        mock_db.query_due_checks.assert_called_once_with(1672531200, limit=100)
        mock_db.update_check_to_late.assert_called_once_with(
            "team-123", "check-123", "2023-01-01T00:00:00Z"
        )

        # SNS publish no longer called - using modern alert channels only

    @patch('app.handlers.get_settings')
    @patch('app.handlers.create_db_client')
    @patch('app.handlers.boto3.client')
    @patch('app.handlers.get_current_time_seconds')
    @patch('app.handlers.get_iso_timestamp')
    def test_late_detector_check_already_late(
        self, mock_timestamp, mock_current_time, mock_boto3, mock_create_db, mock_settings,
        eventbridge_event, lambda_context, sample_check
    ):
        """Test late detector when check is already late (conditional update fails)."""
        # Setup mocks
        mock_current_time.return_value = 1672531200
        mock_timestamp.return_value = "2023-01-01T00:00:00Z"
        mock_settings.return_value.aws_region = "us-east-1"
        
        mock_db = AsyncMock()
        mock_db.query_due_checks.return_value = [sample_check]
        mock_db.update_check_to_late.return_value = False  # Already late
        mock_create_db.return_value = mock_db

        mock_sns = MagicMock()
        mock_boto3.return_value = mock_sns

        # Execute handler
        result = late_detector_handler(eventbridge_event, lambda_context)

        # Verify result
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["checksProcessed"] == 1
        assert body["channelAlertsQueued"] == 0  # No alert sent because already late
        assert body["channelAlertsSent"] == 0

        # Verify SNS was not called
        mock_sns.publish.assert_not_called()

    @patch('app.handlers.get_settings')
    @patch('app.handlers.create_db_client')
    @patch('app.handlers.boto3.client')
    @patch('app.handlers.get_current_time_seconds')
    @patch('app.handlers.get_iso_timestamp')
    def test_late_detector_sns_error(
        self, mock_timestamp, mock_current_time, mock_boto3, mock_create_db, mock_settings,
        eventbridge_event, lambda_context, sample_check
    ):
        """Test late detector when SNS publish fails."""
        # Setup mocks
        mock_current_time.return_value = 1672531200
        mock_timestamp.return_value = "2023-01-01T00:00:00Z"
        mock_settings.return_value.aws_region = "us-east-1"
        
        mock_db = AsyncMock()
        mock_db.query_due_checks.return_value = [sample_check]
        mock_db.update_check_to_late.return_value = True
        mock_create_db.return_value = mock_db

        mock_sns = MagicMock()
        mock_sns.publish.side_effect = ClientError(
            {'Error': {'Code': 'InvalidParameter'}}, 'Publish'
        )
        mock_boto3.return_value = mock_sns

        # Execute handler (should not raise exception)
        result = late_detector_handler(eventbridge_event, lambda_context)

        # Verify result
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["checksProcessed"] == 1
        assert body["channelAlertsQueued"] == 0  # Failed to queue alert
        assert body["channelAlertsSent"] == 0

    @patch('app.handlers.get_settings')
    @patch('app.handlers.create_db_client')
    @patch('app.handlers.boto3.client')
    @patch('app.handlers.get_current_time_seconds')
    @patch('app.handlers.get_iso_timestamp')
    def test_late_detector_check_without_alert_topics(
        self, mock_timestamp, mock_current_time, mock_boto3, mock_create_db, mock_settings,
        eventbridge_event, lambda_context
    ):
        """Test late detector with check that has no alert topics."""
        # Create check without alert topics
        check_no_alerts = Check(
            check_id="check-123",
            team_id="team-123",
            name="Test Check",
            token="token-123",
            period_seconds=3600,
            grace_seconds=300,
            status=CheckStatus.UP,
            created_at="2023-01-01T00:00:00Z",
            alert_channels=[]  # No alert topics
        )

        # Setup mocks
        mock_current_time.return_value = 1672531200
        mock_timestamp.return_value = "2023-01-01T00:00:00Z"
        mock_settings.return_value.aws_region = "us-east-1"
        
        mock_db = AsyncMock()
        mock_db.query_due_checks.return_value = [check_no_alerts]
        mock_db.update_check_to_late.return_value = True
        mock_create_db.return_value = mock_db

        mock_sns = MagicMock()
        mock_boto3.return_value = mock_sns

        # Execute handler
        result = late_detector_handler(eventbridge_event, lambda_context)

        # Verify result
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["checksProcessed"] == 1
        assert body["channelAlertsQueued"] == 0  # No alerts because no channels
        assert body["channelAlertsSent"] == 0

        # Verify SNS was not called
        mock_sns.publish.assert_not_called()


class TestEventBridgeIntegration:
    """Test EventBridge integration scenarios."""

    @patch('app.handlers.get_settings')
    @patch('app.handlers.create_db_client')
    @patch('app.handlers.boto3.client')
    @patch('app.handlers.get_current_time_seconds')
    @patch('app.handlers.get_iso_timestamp')
    def test_eventbridge_scheduled_execution(
        self, mock_timestamp, mock_current_time, mock_boto3, mock_create_db, mock_settings,
        lambda_context
    ):
        """Test EventBridge scheduled execution (every 2 minutes)."""
        # Real EventBridge event structure
        eventbridge_scheduled_event = {
            "version": "0",
            "id": "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "account": "123456789012",
            "time": "1970-01-01T00:00:00Z",
            "region": "us-east-1",
            "detail": {},
            "resources": [
                "arn:aws:events:us-east-1:123456789012:rule/pulsechecks-late-detector-prod"
            ]
        }

        # Setup mocks
        mock_current_time.return_value = 1672531200
        mock_timestamp.return_value = "2023-01-01T00:00:00Z"
        mock_settings.return_value.aws_region = "us-east-1"
        
        mock_db = AsyncMock()
        mock_db.query_due_checks.return_value = []
        mock_create_db.return_value = mock_db

        # Execute handler
        result = late_detector_handler(eventbridge_scheduled_event, lambda_context)

        # Verify EventBridge integration works
        assert result["statusCode"] == 200
        mock_db.query_due_checks.assert_called_once_with(1672531200, limit=100)
