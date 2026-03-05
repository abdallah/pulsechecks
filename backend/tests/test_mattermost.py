"""Tests for Mattermost integration."""
import pytest
from unittest.mock import AsyncMock, patch
from app.integrations.mattermost import MattermostClient, create_mattermost_client
from app.models import Check, CheckStatus


@pytest.fixture
def sample_check():
    """Sample check for testing."""
    return Check(
        check_id="check-123",
        team_id="team-456", 
        name="Test Check",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.LATE,
        last_ping_at="2025-12-19T15:00:00Z",
        next_due_at="2025-12-19T16:00:00Z",
        alert_after_at="2025-12-19T16:05:00Z",
        token="test-token",
        created_at="2025-12-19T14:00:00Z",
        alert_channels=[]
    )


def test_create_mattermost_client():
    """Test Mattermost client factory."""
    webhook_url = "https://chat.example.com/hooks/abc123"
    client = create_mattermost_client(webhook_url)
    
    assert isinstance(client, MattermostClient)
    assert client.webhook_url == webhook_url


class TestMattermostClient:
    """Test Mattermost client functionality."""
    
    def test_format_late_alert(self, sample_check):
        """Test late alert message formatting."""
        client = MattermostClient("https://chat.example.com/hooks/abc123")
        message = client._format_late_alert(sample_check, "Test Team")
        
        assert message["username"] == "Pulsechecks"
        assert message["icon_emoji"] == ":warning:"
        assert len(message["attachments"]) == 1
        
        attachment = message["attachments"][0]
        assert attachment["color"] == "danger"  # Mattermost semantic color
        assert "Test Check" in attachment["title"]
        assert "Test Team" in attachment["text"]
        assert len(attachment["fields"]) == 5  # Team, Status, Expected Every, Grace Period, Last Ping
        assert "title_link" in attachment  # Check has clickable title
        assert "View Check Details" in attachment["text"]  # Check has clickable link in text
    
    def test_format_recovery_alert(self, sample_check):
        """Test recovery alert message formatting."""
        client = MattermostClient("https://chat.example.com/hooks/abc123")
        message = client._format_recovery_alert(sample_check, "Test Team")
        
        assert message["username"] == "Pulsechecks"
        assert message["icon_emoji"] == ":white_check_mark:"
        assert len(message["attachments"]) == 1
        
        attachment = message["attachments"][0]
        assert attachment["color"] == "good"  # Mattermost semantic color
        assert "Test Check" in attachment["title"]
        assert "Test Team" in attachment["text"]
        assert len(attachment["fields"]) == 4  # Team, Status, Last Ping, Next Expected
    
    @pytest.mark.asyncio
    async def test_send_late_alert_success(self, sample_check):
        """Test successful late alert sending."""
        client = MattermostClient("https://chat.example.com/hooks/abc123")
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await client.send_late_alert(sample_check, "Test Team")
            
            assert result is True
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_failure(self, sample_check):
        """Test alert sending failure handling."""
        client = MattermostClient("https://chat.example.com/hooks/abc123")
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = Exception("Network error")
            
            result = await client.send_late_alert(sample_check, "Test Team")
            
            assert result is False  # Should not raise, just return False
    
    @pytest.mark.asyncio
    async def test_send_recovery_alert_success(self, sample_check):
        """Test successful recovery alert sending."""
        client = MattermostClient("https://chat.example.com/hooks/abc123")
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await client.send_recovery_alert(sample_check, "Test Team")
            
            assert result is True
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(self, sample_check):
        """Test circuit breaker protection for Mattermost webhook calls."""
        import httpx
        
        client = MattermostClient("https://chat.example.com/hooks/abc123")
        
        with patch("httpx.AsyncClient") as mock_client:
            # Mock RequestError to trigger circuit breaker
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.RequestError("Connection failed")
            
            # Circuit breaker should catch errors and return False
            result1 = await client.send_late_alert(sample_check, "Test Team")
            result2 = await client.send_late_alert(sample_check, "Test Team") 
            result3 = await client.send_late_alert(sample_check, "Test Team")
            
            # All should return False (errors caught by circuit breaker)
            assert result1 is False
            assert result2 is False  
            assert result3 is False
