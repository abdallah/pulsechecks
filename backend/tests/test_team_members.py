"""Tests for team member management — add, list, pending invitations."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.entities import TeamMember, PendingInvitation
from app.models.enums import Role
from app.dependencies import CurrentUser


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    return {"user_id": "admin-user-1", "email": "admin@example.com", "name": "Admin"}


@pytest.fixture
def admin_member():
    return TeamMember(
        team_id="team-123",
        user_id="admin-user-1",
        role=Role.ADMIN,
        joined_at="2026-01-01T00:00:00Z",
    )


def auth_headers():
    return {"Authorization": "Bearer test-token"}


def mock_jwt(user):
    return patch("app.dependencies.verify_jwt_token", return_value={
        "sub": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "email_verified": True,
    })


def mock_db_client(mock_db):
    return patch("app.dependencies.create_db_client", return_value=mock_db)


class TestAddTeamMember:
    def test_add_existing_user_as_member(self, client, mock_user, admin_member):
        existing_user = MagicMock(user_id="user-2", email="shane@example.com", name="Shane")
        db = MagicMock()
        db.get_team_member = AsyncMock(side_effect=[admin_member, None])
        db.get_user_by_email = AsyncMock(return_value=existing_user)
        db.add_team_member = AsyncMock()

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.post("/teams/team-123/members",
                               json={"email": "shane@example.com", "role": "member"},
                               headers=auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "shane@example.com"
        assert data["status"] == "active"
        db.add_team_member.assert_called_once()

    def test_add_nonexistent_user_creates_pending_invitation(self, client, mock_user, admin_member):
        db = MagicMock()
        db.get_team_member = AsyncMock(return_value=admin_member)
        db.get_user_by_email = AsyncMock(return_value=None)
        db.get_pending_invitations_for_email = AsyncMock(return_value=[])
        db.create_pending_invitation = AsyncMock()

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.post("/teams/team-123/members",
                               json={"email": "newuser@example.com", "role": "member"},
                               headers=auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert data["status"] == "pending"
        db.create_pending_invitation.assert_called_once()

    def test_duplicate_invitation_returns_400(self, client, mock_user, admin_member):
        existing_invite = PendingInvitation(
            email="newuser@example.com", team_id="team-123",
            role=Role.MEMBER, invited_by="admin-user-1",
            invited_at="2026-01-01T00:00:00Z",
        )
        db = MagicMock()
        db.get_team_member = AsyncMock(return_value=admin_member)
        db.get_user_by_email = AsyncMock(return_value=None)
        db.get_pending_invitations_for_email = AsyncMock(return_value=[existing_invite])

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.post("/teams/team-123/members",
                               json={"email": "newuser@example.com", "role": "member"},
                               headers=auth_headers())

        assert resp.status_code == 400

    def test_non_admin_cannot_add_members(self, client, mock_user):
        non_admin = TeamMember(team_id="team-123", user_id="admin-user-1",
                               role=Role.MEMBER, joined_at="2026-01-01T00:00:00Z")
        db = MagicMock()
        db.get_team_member = AsyncMock(return_value=non_admin)

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.post("/teams/team-123/members",
                               json={"email": "someone@example.com", "role": "member"},
                               headers=auth_headers())

        assert resp.status_code == 403


class TestListTeamMembers:
    def test_list_includes_pending_invitations(self, client, mock_user, admin_member):
        pending = PendingInvitation(
            email="shane@example.com", team_id="team-123",
            role=Role.MEMBER, invited_by="admin-user-1",
            invited_at="2026-01-01T00:00:00Z",
        )
        admin_user_obj = MagicMock(user_id="admin-user-1", email="admin@example.com", name="Admin")
        db = MagicMock()
        db.get_team_member = AsyncMock(return_value=admin_member)
        db.list_team_members = AsyncMock(return_value=[admin_member])
        db.get_user = AsyncMock(return_value=admin_user_obj)
        db.list_pending_invitations_for_team = AsyncMock(return_value=[pending])

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.get("/teams/team-123/members", headers=auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        emails = [m["email"] for m in data]
        statuses = [m["status"] for m in data]
        assert "shane@example.com" in emails
        assert "pending" in statuses

    def test_list_calls_collection_group_query(self, client, mock_user, admin_member):
        """list_pending_invitations_for_team must be called with the team_id (collection group query)."""
        db = MagicMock()
        db.get_team_member = AsyncMock(return_value=admin_member)
        db.list_team_members = AsyncMock(return_value=[])
        db.list_pending_invitations_for_team = AsyncMock(return_value=[])

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.get("/teams/team-123/members", headers=auth_headers())

        assert resp.status_code == 200
        db.list_pending_invitations_for_team.assert_called_once_with("team-123")

    def test_list_returns_empty_when_no_members_or_invitations(self, client, mock_user, admin_member):
        db = MagicMock()
        db.get_team_member = AsyncMock(return_value=admin_member)
        db.list_team_members = AsyncMock(return_value=[])
        db.list_pending_invitations_for_team = AsyncMock(return_value=[])

        with mock_jwt(mock_user), mock_db_client(db):
            resp = client.get("/teams/team-123/members", headers=auth_headers())

        assert resp.status_code == 200
        assert resp.json() == []
