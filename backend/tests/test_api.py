"""Integration tests for FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.models import User, Team, Check, CheckStatus, Role, TeamMember


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
    }


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token."""
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test.token"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.dependencies.verify_jwt_token")
def test_get_me_unauthorized(mock_verify, client):
    """Test /me endpoint without authorization."""
    response = client.get("/me")
    assert response.status_code == 401  # Missing auth header triggers 401


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_get_me_authorized(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test /me endpoint with valid token."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
        last_login_at="2025-01-01T01:00:00Z",
    ))

    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == mock_user["user_id"]
    assert data["email"] == mock_user["email"]


def test_ping_endpoint_not_found(client):
    """Test ping endpoint with invalid token."""
    with patch("app.dependencies.create_db_client") as mock_create_db:
        mock_db = MagicMock()
        mock_create_db.return_value = mock_db
        mock_db.get_check_by_token = AsyncMock(return_value=None)

        response = client.get("/ping/invalid-token")
        assert response.status_code == 404


def test_ping_endpoint_success(client):
    """Test successful ping."""
    with patch("app.dependencies.create_db_client") as mock_create_db:
        mock_db = MagicMock()
        mock_create_db.return_value = mock_db

        # Mock check lookup
        mock_check = Check(
            check_id="check-123",
            team_id="team-123",
            name="Test Check",
            token="valid-token",
            period_seconds=3600,
            grace_seconds=600,
            status=CheckStatus.UP,
            created_at="2025-01-01T00:00:00Z",
        )
        mock_db.get_check_by_token = AsyncMock(return_value=mock_check)
        mock_db.create_ping = AsyncMock()
        mock_db.update_check_on_ping = AsyncMock(return_value=True)

        response = client.get("/ping/valid-token")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["message"] == "Ping recorded"


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_create_team(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test team creation."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))
    mock_db.create_team = AsyncMock()
    mock_db.add_team_member = AsyncMock()

    response = client.post(
        "/teams",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"name": "My Team"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Team"
    assert data["role"] == "admin"
    assert "teamId" in data


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_create_team_validation_error(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test team creation with invalid data."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))

    # Test with empty name
    response = client.post(
        "/teams",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"name": "   "}  # Whitespace only
    )

    assert response.status_code == 422  # Validation error


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_rotate_check_token_success(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test successful token rotation."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id=mock_user["user_id"],
        role=Role.ADMIN,
        joined_at="2025-01-01T00:00:00Z",
    ))
    
    # Mock check
    mock_check = Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="old-token",
        period_seconds=3600,
        grace_seconds=600,
        status=CheckStatus.UP,
        created_at="2025-01-01T00:00:00Z",
    )
    mock_db.get_check = AsyncMock(return_value=mock_check)
    
    # Mock updated check with new token
    updated_check = Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="new-token-123",
        period_seconds=3600,
        grace_seconds=600,
        status=CheckStatus.UP,
        created_at="2025-01-01T00:00:00Z",
    )
    mock_db.update_check = AsyncMock(return_value=updated_check)

    response = client.post(
        "/teams/team-123/checks/check-123/rotate-token",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "new-token-123"
    assert data["checkId"] == "check-123"


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_rotate_check_token_not_found(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test token rotation for non-existent check."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id=mock_user["user_id"],
        role=Role.ADMIN,
        joined_at="2025-01-01T00:00:00Z",
    ))
    mock_db.get_check = AsyncMock(return_value=None)

    response = client.post(
        "/teams/team-123/checks/nonexistent/rotate-token",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 404


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_delete_check_success(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test successful check deletion."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id=mock_user["user_id"],
        role=Role.ADMIN,
        joined_at="2025-01-01T00:00:00Z",
    ))
    
    # Mock check
    mock_check = Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=600,
        status=CheckStatus.UP,
        created_at="2025-01-01T00:00:00Z",
    )
    mock_db.get_check = AsyncMock(return_value=mock_check)
    mock_db.delete_check = AsyncMock()

    response = client.delete(
        "/teams/team-123/checks/check-123",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Check deleted successfully"
    mock_db.delete_check.assert_called_once_with("team-123", "check-123")


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_delete_check_insufficient_permissions(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test check deletion with insufficient permissions."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))
    # User is only a member, not admin
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id=mock_user["user_id"],
        role=Role.MEMBER,
        joined_at="2025-01-01T00:00:00Z",
    ))

    response = client.delete(
        "/teams/team-123/checks/check-123",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 403


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_correlation_id_in_error_response(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test that correlation ID is included in error responses."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }

    # Mock database to return None (not found)
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2025-01-01T00:00:00Z",
    ))
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id=mock_user["user_id"],
        role=Role.ADMIN,
        joined_at="2025-01-01T00:00:00Z",
    ))
    mock_db.get_check = AsyncMock(return_value=None)  # Not found

    # Test with custom correlation ID
    custom_correlation_id = "test-correlation-123"
    response = client.post(
        "/teams/team-123/checks/nonexistent/rotate-token",
        headers={
            "Authorization": f"Bearer {mock_jwt_token}",
            "X-Correlation-ID": custom_correlation_id
        }
    )

    assert response.status_code == 404
    data = response.json()
    assert "correlation_id" in data
    assert data["correlation_id"] == custom_correlation_id
    # Check response header too
    assert response.headers.get("X-Correlation-ID") == custom_correlation_id


@pytest.fixture
def mock_pings():
    """Mock ping data for testing."""
    return [
        {
            "checkId": "check-123",
            "timestamp": "1735027200000",  # 2024-12-24 10:00:00
            "receivedAt": "2024-12-24T10:00:00Z",
            "pingType": "success",
            "data": "Test ping 1"
        },
        {
            "checkId": "check-123", 
            "timestamp": "1735023600000",  # 2024-12-24 09:00:00
            "receivedAt": "2024-12-24T09:00:00Z",
            "pingType": "success",
            "data": "Test ping 2"
        }
    ]


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_list_check_pings_without_since(mock_create_db, mock_verify, client, mock_user, mock_jwt_token, mock_pings):
    """Test listing check pings without time filter."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": "user-123",
        "email": "test@example.com",
        "name": "Test User"
    }
    
    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    
    # Mock team membership
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id="user-123",
        role=Role.MEMBER,
        joined_at="2025-01-01T00:00:00Z",
    ))
    
    # Mock check
    mock_check = Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=600,
        status=CheckStatus.UP,
        created_at="2025-01-01T00:00:00Z",
    )
    mock_db.get_check = AsyncMock(return_value=mock_check)
    
    # Mock pings
    from app.models import Ping
    mock_ping_objects = [
        Ping(
            check_id=ping["checkId"],
            timestamp=ping["timestamp"],
            received_at=ping["receivedAt"],
            ping_type=ping["pingType"],
            data=ping["data"]
        ) for ping in mock_pings
    ]
    mock_db.list_check_pings = AsyncMock(return_value=mock_ping_objects)

    response = client.get(
        "/teams/team-123/checks/check-123/pings?limit=50",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["checkId"] == "check-123"
    assert data[0]["data"] == "Test ping 1"
    
    # Verify database call without since parameter
    mock_db.list_check_pings.assert_called_once_with("check-123", 50, None)


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_list_check_pings_with_since(mock_create_db, mock_verify, client, mock_user, mock_jwt_token, mock_pings):
    """Test listing check pings with time filter."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": "user-123",
        "email": "test@example.com",
        "name": "Test User"
    }
    
    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    
    # Mock team membership
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id="user-123",
        role=Role.MEMBER,
        joined_at="2025-01-01T00:00:00Z",
    ))
    
    # Mock check
    mock_check = Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=600,
        status=CheckStatus.UP,
        created_at="2025-01-01T00:00:00Z",
    )
    mock_db.get_check = AsyncMock(return_value=mock_check)
    
    # Mock filtered pings (only one ping after the since timestamp)
    from app.models import Ping
    filtered_pings = [mock_pings[0]]  # Only the newer ping
    mock_ping_objects = [
        Ping(
            check_id=ping["checkId"],
            timestamp=ping["timestamp"],
            received_at=ping["receivedAt"],
            ping_type=ping["pingType"],
            data=ping["data"]
        ) for ping in filtered_pings
    ]
    mock_db.list_check_pings = AsyncMock(return_value=mock_ping_objects)

    # Request with since parameter (timestamp between the two pings)
    since_timestamp = 1735025400000  # 2024-12-24 09:30:00
    response = client.get(
        f"/teams/team-123/checks/check-123/pings?limit=100&since={since_timestamp}",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["checkId"] == "check-123"
    assert data[0]["data"] == "Test ping 1"
    
    # Verify database call with since parameter
    mock_db.list_check_pings.assert_called_once_with("check-123", 100, since_timestamp)


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_list_check_pings_check_not_found(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test listing pings for non-existent check."""
    # Mock JWT verification
    mock_verify.return_value = {
        "sub": "user-123",
        "email": "test@example.com",
        "name": "Test User"
    }
    
    # Mock database
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    
    # Mock team membership
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-123",
        user_id="user-123",
        role=Role.MEMBER,
        joined_at="2025-01-01T00:00:00Z",
    ))
    
    # Mock check not found
    mock_db.get_check = AsyncMock(return_value=None)

    response = client.get(
        "/teams/team-123/checks/nonexistent/pings",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "Check not found"


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_update_check_with_escalation(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test updating check with escalation configuration."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    # Mock existing check
    mock_check = Check(
        check_id="check-456",
        team_id="team-123",
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.UP,
        created_at="2023-01-01T00:00:00Z",
        alert_channels=[]
    )
    mock_db.get_check.return_value = mock_check
    
    # Mock updated check with escalation
    updated_check = Check(
        check_id="check-456",
        team_id="team-123", 
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.UP,
        created_at="2023-01-01T00:00:00Z",
        alert_channels=[],
        escalation_minutes=15,
        escalation_alert_channels=["critical-channel-id"]
    )
    mock_db.update_check.return_value = updated_check
    
    # Make request
    response = client.patch(
        "/teams/team-123/checks/check-456",
        json={
            "escalationMinutes": 15,
            "escalationAlertTopics": ["arn:aws:sns:us-east-1:123456789012:critical"]
        },
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["escalationMinutes"] == 15
    # escalationAlertTopics removed - using modern alert channels only


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_escalate_check_immediately(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test immediate escalation endpoint."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    # Mock check with escalation configured
    mock_check = Check(
        check_id="check-456",
        team_id="team-123",
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.LATE,
        created_at="2023-01-01T00:00:00Z",
        escalation_minutes=15,
        escalation_alert_channels=["critical-channel-id"]
    )
    mock_db.get_check.return_value = mock_check
    mock_db.get_team.return_value = MagicMock(name="Test Team")
    
    with patch("app.handlers._send_escalated_alerts") as mock_escalate:
        response = client.post(
            "/teams/team-123/checks/check-456/escalate",
            headers={"Authorization": f"Bearer {mock_jwt_token}"}
        )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Escalation triggered successfully"
    mock_db.mark_escalation_triggered.assert_called_once()


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_suppress_check_immediately(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test immediate suppression endpoint."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    # Mock check with suppression configured
    mock_check = Check(
        check_id="check-456",
        team_id="team-123",
        name="Test Check",
        token="test-token",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.LATE,
        created_at="2023-01-01T00:00:00Z",
        suppress_duration_minutes=120
    )
    mock_db.get_check.return_value = mock_check
    
    response = client.post(
        "/teams/team-123/checks/check-456/suppress",
        headers={"Authorization": f"Bearer {mock_jwt_token}"}
    )
    
    assert response.status_code == 200
    assert "120 minutes" in response.json()["message"]
    mock_db.suppress_check_alerts.assert_called_once()


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_bulk_pause_checks_success(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test successful bulk pause of checks."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access with MANAGE permission
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    # Mock checks exist
    mock_db.get_check.side_effect = [
        Check(check_id="check-1", team_id="team-123", name="Check 1", token="token-1", 
              period_seconds=3600, grace_seconds=300, status=CheckStatus.UP, created_at="2023-01-01T00:00:00Z"),
        Check(check_id="check-2", team_id="team-123", name="Check 2", token="token-2", 
              period_seconds=3600, grace_seconds=300, status=CheckStatus.LATE, created_at="2023-01-01T00:00:00Z")
    ]
    
    response = client.post(
        "/teams/team-123/checks/bulk/pause",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"check_ids": ["check-1", "check-2"]}
    )
    
    assert response.status_code == 200
    assert "Paused 2 of 2 checks" in response.json()["message"]
    assert mock_db.update_check_status.call_count == 2


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_bulk_resume_checks_success(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test successful bulk resume of checks."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access with MANAGE permission
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    # Mock paused checks
    mock_db.get_check.side_effect = [
        Check(check_id="check-1", team_id="team-123", name="Check 1", token="token-1", 
              period_seconds=3600, grace_seconds=300, status=CheckStatus.PAUSED, created_at="2023-01-01T00:00:00Z"),
        Check(check_id="check-2", team_id="team-123", name="Check 2", token="token-2", 
              period_seconds=3600, grace_seconds=300, status=CheckStatus.PAUSED, created_at="2023-01-01T00:00:00Z")
    ]
    
    response = client.post(
        "/teams/team-123/checks/bulk/resume",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"check_ids": ["check-1", "check-2"]}
    )
    
    assert response.status_code == 200
    assert "Resumed 2 of 2 checks" in response.json()["message"]
    assert mock_db.update_check_status.call_count == 2
    assert mock_db.update_check_timing.call_count == 2


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_bulk_pause_checks_insufficient_permission(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test bulk pause with insufficient permissions."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access with VIEW permission (insufficient for bulk operations)
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.MEMBER,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    response = client.post(
        "/teams/team-123/checks/bulk/pause",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"check_ids": ["check-1", "check-2"]}
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["error"]


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_bulk_operations_partial_success(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test bulk operations with partial success (some checks fail)."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access with MANAGE permission
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    # Mock one check exists, one doesn't
    mock_db.get_check.side_effect = [
        Check(check_id="check-1", team_id="team-123", name="Check 1", token="token-1", 
              period_seconds=3600, grace_seconds=300, status=CheckStatus.UP, created_at="2023-01-01T00:00:00Z"),
        None  # Second check doesn't exist
    ]
    
    response = client.post(
        "/teams/team-123/checks/bulk/pause",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"check_ids": ["check-1", "check-2"]}
    )
    
    assert response.status_code == 200
    assert "Paused 1 of 2 checks" in response.json()["message"]
    assert mock_db.update_check_status.call_count == 1


@patch("app.dependencies.verify_jwt_token")
@patch('app.dependencies.create_db_client')
def test_bulk_operations_empty_check_ids(mock_create_db, mock_verify, client, mock_user, mock_jwt_token):
    """Test bulk operations with empty check_ids list."""
    # Setup mocks
    mock_verify.return_value = {
        "sub": mock_user["user_id"],
        "email": mock_user["email"],
        "name": mock_user["name"],
        "email_verified": True,
    }
    mock_db = AsyncMock()
    mock_create_db.return_value = mock_db
    
    # Mock user
    mock_db.get_user = AsyncMock(return_value=User(
        user_id=mock_user["user_id"],
        email=mock_user["email"],
        name=mock_user["name"],
        created_at="2023-01-01T00:00:00Z",
    ))
    
    # Mock team access with MANAGE permission
    mock_db.get_team_member.return_value = TeamMember(
        user_id=mock_user["user_id"],
        team_id="team-123",
        role=Role.ADMIN,
        joined_at="2023-01-01T00:00:00Z"
    )
    
    response = client.post(
        "/teams/team-123/checks/bulk/pause",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={"check_ids": []}
    )
    
    assert response.status_code == 200
    assert "Paused 0 of 0 checks" in response.json()["message"]
