"""Tests for API token management — create, list, revoke, and pc_ auth."""
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.routers.api_tokens import _generate_token, _hash_token
from app.dependencies import CurrentUser
from app.models.entities import TeamMember
from app.models.enums import Role


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    return {"user_id": "user-1", "email": "admin@example.com", "name": "Admin"}


@pytest.fixture
def admin_member():
    return TeamMember(
        team_id="team-123", user_id="user-1",
        role=Role.ADMIN, joined_at="2026-01-01T00:00:00Z",
    )


def auth_headers():
    return {"Authorization": "Bearer test-token"}


def mock_jwt(user):
    return patch("app.dependencies.verify_jwt_token", return_value={
        "sub": user["user_id"], "email": user["email"],
        "name": user["name"], "email_verified": True,
    })


def mock_db_client(mock_db):
    return patch("app.dependencies.create_db_client", return_value=mock_db)


# ── Token generation helpers ──────────────────────────────────────────────────

class TestTokenHelpers:
    def test_generate_token_format(self):
        token = _generate_token()
        assert token.startswith("pc_")
        assert len(token) == 67  # pc_ + 64 hex chars

    def test_generate_token_uniqueness(self):
        tokens = {_generate_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_hash_token_is_sha256(self):
        token = "pc_" + "a" * 64
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert _hash_token(token) == expected

    def test_hash_is_deterministic(self):
        token = _generate_token()
        assert _hash_token(token) == _hash_token(token)


# ── Create token ──────────────────────────────────────────────────────────────

class TestCreateApiToken:
    def test_create_returns_plaintext_token_once(self, client, mock_user, admin_member):
        mock_db = MagicMock()
        mock_db.get_team_member = AsyncMock(return_value=admin_member)
        col_mock = MagicMock()
        doc_mock = MagicMock()
        doc_mock.set = AsyncMock()
        col_mock.document.return_value = doc_mock
        mock_db.db.collection.return_value = col_mock

        with mock_jwt(mock_user), mock_db_client(mock_db):
            resp = client.post("/teams/team-123/api-tokens",
                               json={"name": "CI Token"},
                               headers=auth_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token"].startswith("pc_")
        assert len(data["token"]) == 67
        assert "token_hash" in data
        assert data["token_hash"] == _hash_token(data["token"])
        assert data["name"] == "CI Token"

    def test_create_requires_name(self, client, mock_user, admin_member):
        mock_db = MagicMock()
        mock_db.get_team_member = AsyncMock(return_value=admin_member)

        with mock_jwt(mock_user), mock_db_client(mock_db):
            resp = client.post("/teams/team-123/api-tokens",
                               json={},
                               headers=auth_headers())

        assert resp.status_code == 422

    def test_token_stored_as_hash_not_plaintext(self, client, mock_user, admin_member):
        stored_doc = {}
        mock_db = MagicMock()
        mock_db.get_team_member = AsyncMock(return_value=admin_member)
        col_mock = MagicMock()
        doc_mock = MagicMock()

        async def capture_set(data):
            stored_doc.update(data)
        doc_mock.set = capture_set
        col_mock.document.return_value = doc_mock
        mock_db.db.collection.return_value = col_mock

        with mock_jwt(mock_user), mock_db_client(mock_db):
            resp = client.post("/teams/team-123/api-tokens",
                               json={"name": "Test"},
                               headers=auth_headers())

        assert resp.status_code == 200
        plaintext = resp.json()["token"]
        # Stored doc must not contain plaintext token
        assert "token" not in stored_doc
        assert stored_doc.get("token_hash") == _hash_token(plaintext)


# ── List tokens ───────────────────────────────────────────────────────────────

class TestListApiTokens:
    def test_list_never_returns_token_hash(self, client, mock_user, admin_member):
        mock_db = MagicMock()
        mock_db.get_team_member = AsyncMock(return_value=admin_member)
        col_mock = MagicMock()

        async def fake_stream():
            doc = MagicMock()
            doc.to_dict.return_value = {
                "token_id": "tid-1", "team_id": "team-123",
                "user_id": "user-1", "name": "CI Token",
                "token_hash": "somehash", "created_at": "2026-01-01T00:00:00Z",
                "last_used_at": None, "expires_at": None,
            }
            yield doc

        query_mock = MagicMock()
        query_mock.stream = fake_stream
        col_mock.where.return_value = query_mock
        mock_db.db.collection.return_value = col_mock

        with mock_jwt(mock_user), mock_db_client(mock_db):
            resp = client.get("/teams/team-123/api-tokens", headers=auth_headers())

        assert resp.status_code == 200
        tokens = resp.json()
        assert len(tokens) == 1
        assert "token_hash" not in tokens[0]
        assert "token" not in tokens[0]
        assert tokens[0]["name"] == "CI Token"


# ── Revoke token ──────────────────────────────────────────────────────────────

class TestRevokeApiToken:
    def test_revoke_deletes_token(self, client, mock_user, admin_member):
        mock_db = MagicMock()
        mock_db.get_team_member = AsyncMock(return_value=admin_member)
        col_mock = MagicMock()
        doc_ref = MagicMock()
        doc_snapshot = MagicMock()
        doc_snapshot.exists = True
        doc_snapshot.to_dict.return_value = {"team_id": "team-123"}
        doc_ref.get = AsyncMock(return_value=doc_snapshot)
        doc_ref.delete = AsyncMock()
        col_mock.document.return_value = doc_ref
        mock_db.db.collection.return_value = col_mock

        with mock_jwt(mock_user), mock_db_client(mock_db):
            resp = client.delete("/teams/team-123/api-tokens/tid-1",
                                 headers=auth_headers())

        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        doc_ref.delete.assert_called_once()

    def test_revoke_returns_404_for_missing_token(self, client, mock_user, admin_member):
        mock_db = MagicMock()
        mock_db.get_team_member = AsyncMock(return_value=admin_member)
        col_mock = MagicMock()
        doc_ref = MagicMock()
        doc_snapshot = MagicMock()
        doc_snapshot.exists = False
        doc_ref.get = AsyncMock(return_value=doc_snapshot)
        col_mock.document.return_value = doc_ref
        mock_db.db.collection.return_value = col_mock

        with mock_jwt(mock_user), mock_db_client(mock_db):
            resp = client.delete("/teams/team-123/api-tokens/nonexistent",
                                 headers=auth_headers())

        assert resp.status_code == 404


# ── pc_ token auth middleware ─────────────────────────────────────────────────

class TestPcTokenAuth:
    @pytest.mark.asyncio
    async def test_pc_token_resolves_user(self):
        from app.dependencies import _resolve_api_token
        import asyncio
        token = _generate_token()
        token_hash = _hash_token(token)

        doc = MagicMock()
        doc.to_dict.return_value = {
            "token_id": "tid-1",
            "user_id": "user-1", "team_id": "team-123",
            "token_hash": token_hash, "expires_at": None,
        }

        async def fake_stream():
            yield doc

        doc_ref_mock = MagicMock()
        doc_ref_mock.update = AsyncMock()

        query_mock = MagicMock()
        query_mock.stream = fake_stream
        col_mock = MagicMock()
        col_mock.where.return_value = query_mock
        col_mock.document.return_value = doc_ref_mock

        mock_db = MagicMock()
        mock_db.db.collection.return_value = col_mock

        with patch("asyncio.ensure_future", return_value=None):
            user = await _resolve_api_token(token, mock_db)

        assert user.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_pc_token_invalid_raises_unauthorized(self):
        from app.dependencies import _resolve_api_token
        from app.errors import UnauthorizedError

        async def fake_stream():
            if False:
                yield  # empty async generator

        query_mock = MagicMock()
        query_mock.stream = fake_stream
        col_mock = MagicMock()
        col_mock.where.return_value = query_mock
        mock_db = MagicMock()
        mock_db.db.collection.return_value = col_mock

        with pytest.raises(UnauthorizedError):
            await _resolve_api_token("pc_invalid", mock_db)
