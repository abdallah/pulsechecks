"""Tests for slug-based ping URLs and team slug functionality.

Covers:
- Team slug auto-generation on create
- Team slug exposed in API responses
- /ping/{team_slug}/{check_slug}/success  (new clean URL)
- /ping/{team_slug}/{check_slug}/fail     (new clean URL)
- /ping/{team_slug}/{check_slug}          (shorthand -> success)
- /ping/by-slug/{check_slug}/success?team_id=  (legacy, kept for backward compat)
- 404 handling for unknown team slug or check slug
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.models.entities import Check, CheckStatus, Team


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_team():
    return Team(
        team_id="team-abc",
        name="My Team",
        slug="my-team",
        created_at="2025-01-01T00:00:00Z",
        created_by="user-1",
    )


@pytest.fixture
def mock_check():
    return Check(
        check_id="check-xyz",
        team_id="team-abc",
        name="Daily Backup",
        token="secret-token-123",
        slug="daily-backup",
        period_seconds=86400,
        grace_seconds=3600,
        status=CheckStatus.UP,
        created_at="2025-01-01T00:00:00Z",
    )


def _mock_db_for_slug(mock_team, mock_check):
    """Return a mock DB wired for slug lookups."""
    db = MagicMock()
    db.get_team_by_slug = AsyncMock(return_value=mock_team)
    db.get_check_by_slug = AsyncMock(return_value=mock_check)
    db.get_check_by_team_slug_and_check_slug = AsyncMock(return_value=mock_check)
    db.get_check_by_token = AsyncMock(return_value=mock_check)
    db.create_ping = AsyncMock()
    db.update_check_on_ping = AsyncMock(return_value=True)
    db.reset_alert_state = AsyncMock()
    db.get_team = AsyncMock(return_value=mock_team)
    db.get_alert_channel = AsyncMock(return_value=None)
    return db


# ── Team slug auto-generation ────────────────────────────────────────────────

class TestTeamSlugGeneration:
    """Team slug is auto-generated from name on create."""

    def test_slug_generated_on_create(self, client):
        from app.models.entities import User
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_user = {"user_id": "u1", "email": "u@example.com", "name": "User"}
        token = "test.jwt.token"

        with patch("app.dependencies.verify_jwt_token") as mock_verify, \
             patch("app.dependencies.create_db_client") as mock_create_db:

            mock_verify.return_value = {
                "sub": mock_user["user_id"],
                "email": mock_user["email"],
                "name": mock_user["name"],
                "email_verified": True,
            }
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_user = AsyncMock(return_value=User(
                user_id="u1", email="u@example.com", name="User",
                created_at="2025-01-01T00:00:00Z",
            ))
            db.create_team = AsyncMock()
            db.add_team_member = AsyncMock()

            # Capture the Team object passed to create_team
            created_teams = []
            async def capture_team(team):
                created_teams.append(team)
            db.create_team.side_effect = capture_team

            response = client.post(
                "/teams",
                headers={"Authorization": f"Bearer {token}"},
                json={"name": "Staging Infra"}
            )

            assert response.status_code == 201
            assert len(created_teams) == 1
            assert created_teams[0].slug == "staging-infra"

    def test_slug_spaces_and_caps(self, client):
        """Slug lowercases and replaces spaces with dashes."""
        from app.utils import generate_slug
        assert generate_slug("My Daily Backup") == "my-daily-backup"

    def test_slug_special_chars_stripped(self):
        from app.utils import generate_slug
        assert generate_slug("backup!! 2025 (prod)") == "backup-2025-prod"

    def test_slug_consecutive_dashes_collapsed(self):
        from app.utils import generate_slug
        assert generate_slug("a  --  b") == "a-b"

    def test_slug_empty_fallback(self):
        from app.utils import generate_slug
        assert generate_slug("!!!") == "check"


# ── Team API returns slug ────────────────────────────────────────────────────

class TestTeamApiSlug:
    """slug field is returned in team API responses."""

    def test_list_teams_includes_slug(self, client):
        from app.models.entities import User, Role
        mock_user = {"user_id": "u1", "email": "u@example.com", "name": "User"}
        token = "test.jwt.token"

        with patch("app.dependencies.verify_jwt_token") as mock_verify, \
             patch("app.dependencies.create_db_client") as mock_create_db:

            mock_verify.return_value = {
                "sub": "u1", "email": "u@example.com",
                "name": "User", "email_verified": True,
            }
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_user = AsyncMock(return_value=User(
                user_id="u1", email="u@example.com", name="User",
                created_at="2025-01-01T00:00:00Z",
            ))
            db.list_user_teams = AsyncMock(return_value=[{
                "team": Team(
                    team_id="t1", name="Prod Team", slug="prod-team",
                    created_at="2025-01-01T00:00:00Z", created_by="u1"
                ),
                "role": Role.ADMIN,
            }])

            response = client.get(
                "/teams",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            teams = response.json()
            assert teams[0]["slug"] == "prod-team"

    def test_get_team_includes_slug(self, client, mock_team):
        from app.models.entities import User, Role
        token = "test.jwt.token"

        with patch("app.dependencies.verify_jwt_token") as mock_verify, \
             patch("app.dependencies.create_db_client") as mock_create_db:

            mock_verify.return_value = {
                "sub": "u1", "email": "u@example.com",
                "name": "User", "email_verified": True,
            }
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_user = AsyncMock(return_value=None)
            db.get_team = AsyncMock(return_value=mock_team)
            db.get_team_member = AsyncMock(return_value=MagicMock(role=Role.ADMIN))

            response = client.get(
                f"/teams/{mock_team.team_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            assert response.json()["slug"] == "my-team"


# ── Clean slug ping routes ───────────────────────────────────────────────────

class TestCleanSlugPingRoutes:
    """Tests for /ping/{team_slug}/{check_slug}/action routes."""

    def test_success_route_get(self, client, mock_team, mock_check):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.get("/ping/my-team/daily-backup/success")

            assert response.status_code == 200
            assert response.json()["ok"] is True
            db.get_check_by_team_slug_and_check_slug.assert_called_once_with(
                "my-team", "daily-backup"
            )

    def test_success_route_post(self, client, mock_team, mock_check):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.post("/ping/my-team/daily-backup/success")

            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_fail_route_get(self, client, mock_team, mock_check):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.get("/ping/my-team/daily-backup/fail")

            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_fail_route_post(self, client, mock_team, mock_check):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.post("/ping/my-team/daily-backup/fail")

            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_shorthand_get(self, client, mock_team, mock_check):
        """GET /ping/{team_slug}/{check_slug} (no action suffix) defaults to success."""
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.get("/ping/my-team/daily-backup")

            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_shorthand_post(self, client, mock_team, mock_check):
        """POST /ping/{team_slug}/{check_slug} defaults to success."""
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.post("/ping/my-team/daily-backup")

            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_unknown_team_slug_returns_404(self, client):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_check_by_team_slug_and_check_slug = AsyncMock(return_value=None)

            response = client.get("/ping/nonexistent-team/some-check/success")

            assert response.status_code == 404

    def test_unknown_check_slug_returns_404(self, client, mock_team):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_check_by_team_slug_and_check_slug = AsyncMock(return_value=None)

            response = client.get("/ping/my-team/nonexistent-check/success")

            assert response.status_code == 404

    def test_fail_route_with_data(self, client, mock_team, mock_check):
        """Fail ping with data body."""
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.post(
                "/ping/my-team/daily-backup/fail",
                json={"data": "Disk full on /dev/sda1"}
            )

            assert response.status_code == 200
            assert response.json()["ok"] is True


# ── Legacy by-slug routes (backward compat) ──────────────────────────────────

class TestTokenCodeFallback:
    """Two-segment handler falls back to token+code when slug lookup fails."""

    def test_token_plus_code_still_works(self, client, mock_check):
        """/{token}/{code} still records failure when slug lookup returns nothing."""
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            # Slug lookup fails
            db.get_check_by_team_slug_and_check_slug = AsyncMock(return_value=None)
            # Token lookup succeeds
            db.get_check_by_token = AsyncMock(return_value=mock_check)
            db.create_ping = AsyncMock()
            db.update_check_on_ping = AsyncMock(return_value=True)

            response = client.get(f"/ping/{mock_check.token}/500")

            assert response.status_code == 200
            assert "500" in response.json()["message"]

    def test_token_plus_invalid_code_returns_400(self, client):
        """Invalid code format returns 400 even after slug miss."""
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_check_by_team_slug_and_check_slug = AsyncMock(return_value=None)

            response = client.get("/ping/some-token/invalid code!")

            assert response.status_code == 400

    def test_slug_takes_priority_over_token(self, client, mock_team, mock_check):
        """When slug lookup succeeds, it wins over token+code interpretation.
        get_check_by_team_slug_and_check_slug is called first; if it returns
        a check, get_check_by_token is only called internally by _record_ping_internal
        (not as the two-segment fallback path).
        """
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = _mock_db_for_slug(mock_team, mock_check)
            mock_create_db.return_value = db

            response = client.get("/ping/my-team/daily-backup")

            assert response.status_code == 200
            # Slug lookup must have been attempted first
            db.get_check_by_team_slug_and_check_slug.assert_called_once_with(
                "my-team", "daily-backup"
            )


class TestLegacyBySlugRoutes:
    """Legacy /ping/by-slug/{slug}?team_id= routes still work."""

    def test_legacy_success_route(self, client, mock_check):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_check_by_slug = AsyncMock(return_value=mock_check)
            db.get_check_by_token = AsyncMock(return_value=mock_check)
            db.create_ping = AsyncMock()
            db.update_check_on_ping = AsyncMock(return_value=True)
            db.reset_alert_state = AsyncMock()
            db.get_team = AsyncMock(return_value=None)

            response = client.get(
                "/ping/by-slug/daily-backup/success?team_id=team-abc"
            )

            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_legacy_fail_route(self, client, mock_check):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_check_by_slug = AsyncMock(return_value=mock_check)
            db.get_check_by_token = AsyncMock(return_value=mock_check)
            db.create_ping = AsyncMock()
            db.update_check_on_ping = AsyncMock(return_value=True)
            db.reset_alert_state = AsyncMock()
            db.get_team = AsyncMock(return_value=None)

            response = client.get(
                "/ping/by-slug/daily-backup/fail?team_id=team-abc"
            )

            assert response.status_code == 200

    def test_legacy_missing_team_id_returns_400(self, client):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db

            response = client.get("/ping/by-slug/daily-backup/success")

            assert response.status_code == 400

    def test_legacy_unknown_check_returns_404(self, client):
        with patch("app.dependencies.create_db_client") as mock_create_db:
            db = MagicMock()
            mock_create_db.return_value = db
            db.get_check_by_slug = AsyncMock(return_value=None)

            response = client.get(
                "/ping/by-slug/nonexistent/success?team_id=team-abc"
            )

            assert response.status_code == 404


# ── DB layer: get_team_by_slug and get_check_by_team_slug_and_check_slug ─────

class TestDbSlugLookup:
    """Unit tests for the new DB methods."""

    @pytest.mark.asyncio
    async def test_get_team_by_slug_found(self):
        from app.db.firestore import FirestoreClient
        from unittest.mock import patch, MagicMock, AsyncMock

        db = FirestoreClient.__new__(FirestoreClient)
        mock_fs = MagicMock()
        db.db = mock_fs

        doc = MagicMock()
        doc.to_dict.return_value = {
            "teamId": "team-abc",
            "name": "My Team",
            "slug": "my-team",
            "createdAt": "2025-01-01T00:00:00Z",
            "createdBy": "user-1",
        }
        mock_query = MagicMock()
        mock_fs.collection.return_value.where.return_value.limit.return_value = mock_query
        mock_query.get = AsyncMock(return_value=[doc])

        result = await db.get_team_by_slug("my-team")
        assert result is not None
        assert result.team_id == "team-abc"
        assert result.slug == "my-team"

    @pytest.mark.asyncio
    async def test_get_team_by_slug_not_found(self):
        from app.db.firestore import FirestoreClient

        db = FirestoreClient.__new__(FirestoreClient)
        mock_fs = MagicMock()
        db.db = mock_fs

        mock_query = MagicMock()
        mock_fs.collection.return_value.where.return_value.limit.return_value = mock_query
        mock_query.get = AsyncMock(return_value=[])

        result = await db.get_team_by_slug("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_check_by_team_slug_and_check_slug(self):
        from app.db.firestore import FirestoreClient

        db = FirestoreClient.__new__(FirestoreClient)

        # Mock get_team_by_slug to return a team
        team = Team(
            team_id="team-abc", name="My Team", slug="my-team",
            created_at="2025-01-01T00:00:00Z", created_by="user-1"
        )
        db.get_team_by_slug = AsyncMock(return_value=team)

        # Mock get_check_by_slug to return a check
        check = Check(
            check_id="check-xyz", team_id="team-abc", name="Daily Backup",
            token="tok", slug="daily-backup", period_seconds=86400,
            grace_seconds=3600, status=CheckStatus.UP,
            created_at="2025-01-01T00:00:00Z"
        )
        db.get_check_by_slug = AsyncMock(return_value=check)

        result = await db.get_check_by_team_slug_and_check_slug("my-team", "daily-backup")
        assert result is not None
        assert result.check_id == "check-xyz"
        db.get_team_by_slug.assert_called_once_with("my-team")
        db.get_check_by_slug.assert_called_once_with("team-abc", "daily-backup")

    @pytest.mark.asyncio
    async def test_get_check_by_team_slug_and_check_slug_team_not_found(self):
        from app.db.firestore import FirestoreClient

        db = FirestoreClient.__new__(FirestoreClient)
        db.get_team_by_slug = AsyncMock(return_value=None)

        result = await db.get_check_by_team_slug_and_check_slug("bad-team", "some-check")
        assert result is None
