"""Test alert channels endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)

TEAM_ID = "testteam"
CHANNEL_ID = "testchannel"


@pytest.mark.skip(reason="Integration test - requires proper mocking setup")
def test_create_alert_channel():
    """Test creating a new alert channel."""
    channel_data = {
        "name": "test-channel",
        "displayName": "Test Channel",
        "type": "sns",
        "configuration": {},
        "shared": False
    }
    resp = client.post(f"/teams/{TEAM_ID}/channels", json=channel_data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-channel"
    assert data["type"] == "sns"


@pytest.mark.skip(reason="Integration test - requires proper mocking setup")
def test_list_alert_channels():
    """Test listing alert channels for a team."""
    resp = client.get(f"/teams/{TEAM_ID}/channels")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.skip(reason="Integration test - requires proper mocking setup")
def test_get_alert_channel():
    """Test getting a specific alert channel."""
    resp = client.get(f"/teams/{TEAM_ID}/channels/{CHANNEL_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["channelId"] == CHANNEL_ID


@pytest.mark.skip(reason="Integration test - requires proper mocking setup")
def test_update_alert_channel():
    """Test updating an alert channel."""
    update_data = {
        "displayName": "Updated Channel",
        "configuration": {"webhook_url": "https://example.com/webhook"}
    }
    resp = client.patch(f"/teams/{TEAM_ID}/channels/{CHANNEL_ID}", json=update_data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["displayName"] == "Updated Channel"


@pytest.mark.skip(reason="Integration test - requires proper mocking setup")
def test_delete_alert_channel():
    """Test deleting an alert channel."""
    resp = client.delete(f"/teams/{TEAM_ID}/channels/{CHANNEL_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data


@pytest.mark.skip(reason="Integration test - requires proper mocking setup")
def test_create_mattermost_channel():
    """Test creating a Mattermost alert channel."""
    channel_data = {
        "name": "mattermost-alerts",
        "displayName": "Mattermost Alerts",
        "type": "mattermost",
        "configuration": {
            "webhook_url": "https://mattermost.example.com/hooks/webhook123"
        },
        "shared": False
    }
    resp = client.post(f"/teams/{TEAM_ID}/channels", json=channel_data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "mattermost"
    assert "webhook_url" in data["configuration"]
