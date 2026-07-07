"""Tests for the team audit log."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.audit import record_audit
from app.models import AuditEvent, TeamMember, Role, User

client = TestClient(app)


class TestRecordAudit:
    @pytest.mark.asyncio
    async def test_records_event_with_actor(self):
        db = AsyncMock()
        actor = MagicMock(user_id="user-1", email="admin@example.com")

        await record_audit(db, "team-1", actor, "check.deleted", "check", "check-9", "Nightly Backup")

        db.create_audit_event.assert_called_once()
        event = db.create_audit_event.call_args[0][0]
        assert event.team_id == "team-1"
        assert event.actor_email == "admin@example.com"
        assert event.action == "check.deleted"
        assert event.target_name == "Nightly Backup"

    @pytest.mark.asyncio
    async def test_audit_failure_never_raises(self):
        db = AsyncMock()
        db.create_audit_event.side_effect = RuntimeError("db down")
        actor = MagicMock(user_id="user-1", email="admin@example.com")

        # Must not raise — audit failures can't break admin actions
        await record_audit(db, "team-1", actor, "check.deleted", "check", "check-9")


@patch('app.dependencies.create_db_client')
@patch("app.dependencies.verify_jwt_token")
def test_audit_endpoint_admin_only(mock_verify, mock_create_db, mock_jwt_token="tok"):
    mock_verify.return_value = {
        "sub": "user-1", "email": "member@example.com",
        "email_verified": True, "name": "Member",
    }
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-1", user_id="user-1", role=Role.MEMBER,
        joined_at="2025-01-01T00:00:00Z",
    ))

    response = client.get("/teams/team-1/audit", headers={"Authorization": "Bearer tok"})
    assert response.status_code == 403


@patch('app.dependencies.create_db_client')
@patch("app.dependencies.verify_jwt_token")
def test_audit_endpoint_returns_events(mock_verify, mock_create_db):
    mock_verify.return_value = {
        "sub": "user-1", "email": "admin@example.com",
        "email_verified": True, "name": "Admin",
    }
    mock_db = MagicMock()
    mock_create_db.return_value = mock_db
    mock_db.get_team_member = AsyncMock(return_value=TeamMember(
        team_id="team-1", user_id="user-1", role=Role.ADMIN,
        joined_at="2025-01-01T00:00:00Z",
    ))
    mock_db.list_audit_events = AsyncMock(return_value=[
        AuditEvent(
            event_id="evt-1", team_id="team-1", actor_id="user-1",
            actor_email="admin@example.com", action="check.deleted",
            target_type="check", target_id="check-9", target_name="Nightly Backup",
            created_at="2026-01-01T00:00:00Z",
        ),
    ])

    response = client.get("/teams/team-1/audit", headers={"Authorization": "Bearer tok"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["action"] == "check.deleted"
    assert data[0]["actorEmail"] == "admin@example.com"
    assert data[0]["targetName"] == "Nightly Backup"
