"""Tests for team deletion functionality."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.routers.teams import delete_team
from app.models import Role, Team, TeamMember


@pytest.mark.asyncio
async def test_delete_team_success():
    """Test successful team deletion."""
    # Mock dependencies
    mock_db = AsyncMock()
    mock_user = AsyncMock()
    mock_user.user_id = "user123"
    
    # Mock team member (admin)
    mock_member = TeamMember(
        team_id="team123",
        user_id="user123", 
        role=Role.ADMIN,
        joined_at="2024-01-01T00:00:00Z"
    )
    mock_db.get_team_member.return_value = mock_member
    
    # Mock team
    mock_team = Team(
        team_id="team123",
        name="Test Team",
        created_at="2024-01-01T00:00:00Z",
        created_by="user123"
    )
    mock_db.get_team.return_value = mock_team
    
    # Mock delete_team method
    mock_db.delete_team.return_value = None
    
    # Test request
    request = {"team_name": "Test Team"}
    
    # Call the endpoint
    result = await delete_team("team123", request, mock_user, mock_db)
    
    # Verify calls
    mock_db.get_team_member.assert_called_once_with("team123", "user123")
    mock_db.get_team.assert_called_once_with("team123")
    mock_db.delete_team.assert_called_once_with("team123")
    
    # Verify response
    assert result["message"] == "Team 'Test Team' and all associated data deleted successfully"


@pytest.mark.asyncio
async def test_delete_team_not_admin():
    """Test team deletion fails for non-admin user."""
    mock_db = AsyncMock()
    mock_user = AsyncMock()
    mock_user.user_id = "user123"
    
    # Mock team member (not admin)
    mock_member = TeamMember(
        team_id="team123",
        user_id="user123",
        role=Role.MEMBER,  # Not admin
        joined_at="2024-01-01T00:00:00Z"
    )
    mock_db.get_team_member.return_value = mock_member
    
    request = {"team_name": "Test Team"}
    
    # Should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_team("team123", request, mock_user, mock_db)
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin access required"


@pytest.mark.asyncio
async def test_delete_team_wrong_name():
    """Test team deletion fails with wrong team name."""
    mock_db = AsyncMock()
    mock_user = AsyncMock()
    mock_user.user_id = "user123"
    
    # Mock team member (admin)
    mock_member = TeamMember(
        team_id="team123",
        user_id="user123",
        role=Role.ADMIN,
        joined_at="2024-01-01T00:00:00Z"
    )
    mock_db.get_team_member.return_value = mock_member
    
    # Mock team
    mock_team = Team(
        team_id="team123",
        name="Test Team",
        created_at="2024-01-01T00:00:00Z",
        created_by="user123"
    )
    mock_db.get_team.return_value = mock_team
    
    # Wrong team name in request
    request = {"team_name": "Wrong Name"}
    
    # Should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_team("team123", request, mock_user, mock_db)
    
    assert exc_info.value.status_code == 400
    assert "Team name confirmation does not match" in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_team_not_found():
    """Test team deletion fails when team doesn't exist."""
    mock_db = AsyncMock()
    mock_user = AsyncMock()
    mock_user.user_id = "user123"
    
    # Mock team member (admin)
    mock_member = TeamMember(
        team_id="team123",
        user_id="user123",
        role=Role.ADMIN,
        joined_at="2024-01-01T00:00:00Z"
    )
    mock_db.get_team_member.return_value = mock_member
    
    # Team not found
    mock_db.get_team.return_value = None
    
    request = {"team_name": "Test Team"}
    
    # Should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_team("team123", request, mock_user, mock_db)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Team not found"
