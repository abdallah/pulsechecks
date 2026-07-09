"""Tests for warm-standby sync, shadow mode, and auth provider override."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.standby_sync import apply_definitions, build_definitions_export
from app.models import AlertChannel, AlertChannelType, Check, CheckStatus, Role, Team, TeamMember

client = TestClient(app)


def _team():
    return Team(team_id="team-1", name="SRE", slug="sre",
                created_at="2026-01-01T00:00:00Z", created_by="user-1")


def _check(check_id="check-1", managed=False):
    return Check(
        check_id=check_id, team_id="team-1", name="Nightly Backup",
        token="tok-123", period_seconds=3600, grace_seconds=300,
        status=CheckStatus.UP, created_at="2026-01-01T00:00:00Z",
        alert_channels=["chan-1"], managed_by_sync=managed,
    )


def _channel():
    return AlertChannel(
        channel_id="chan-1", team_id="team-1", name="oncall",
        display_name="On-call", type=AlertChannelType.MATTERMOST,
        configuration={"webhook_url": "https://chat.example.com/hooks/x"},
        shared=False, created_at="2026-01-01T00:00:00Z", created_by="user-1",
    )


class TestAuthProviderOverride:
    def test_firebase_on_aws(self):
        from app.auth.factory import create_auth_client
        settings = MagicMock()
        settings.auth_provider = "firebase"
        settings.cloud_provider = "aws"
        settings.firebase_project_id = "proj"
        settings.gcp_project = ""
        with patch("app.auth.factory.get_settings", return_value=settings), \
             patch("app.auth.firebase.get_settings", return_value=settings):
            auth = create_auth_client()
        assert type(auth).__name__ == "FirebaseAuth"

    def test_default_derives_from_cloud(self):
        from app.auth.factory import create_auth_client
        settings = MagicMock()
        settings.auth_provider = ""
        settings.cloud_provider = "gcp"
        settings.firebase_project_id = "proj"
        settings.gcp_project = "proj"
        with patch("app.auth.factory.get_settings", return_value=settings), \
             patch("app.auth.firebase.get_settings", return_value=settings):
            auth = create_auth_client()
        assert type(auth).__name__ == "FirebaseAuth"


class TestExportImport:
    @pytest.mark.asyncio
    async def test_export_collects_all_definitions(self):
        db = AsyncMock()
        db.list_all_teams.return_value = [_team()]
        db.list_team_members.return_value = [TeamMember(
            team_id="team-1", user_id="user-1", role=Role.ADMIN,
            joined_at="2026-01-01T00:00:00Z")]
        db.list_team_checks.return_value = [_check()]
        db.list_alert_channels.return_value = [_channel()]

        payload = await build_definitions_export(db)

        assert payload["version"] == 1
        assert len(payload["teams"]) == 1
        entry = payload["teams"][0]
        assert entry["team"]["team_id"] == "team-1"
        assert entry["checks"][0]["token"] == "tok-123"  # tokens must survive failover
        assert entry["channels"][0]["configuration"]["webhook_url"].startswith("https://")
        # Payload must be JSON-serializable end to end
        json.dumps(payload)

    @pytest.mark.asyncio
    async def test_apply_upserts_and_stamps_sync_flag(self):
        db = AsyncMock()
        source = AsyncMock()
        source.list_all_teams.return_value = [_team()]
        source.list_team_members.return_value = []
        source.list_team_checks.return_value = [_check()]
        source.list_alert_channels.return_value = [_channel()]
        payload = await build_definitions_export(source)

        counts = await apply_definitions(db, payload)

        assert counts == {"teams": 1, "members": 0, "checks": 1, "channels": 1}
        imported_check = db.create_check.call_args[0][0]
        assert imported_check.managed_by_sync is True
        assert imported_check.token == "tok-123"


class TestExportEndpointAuth:
    def _settings(self, token):
        # Patched app-wide, so every field the middleware touches needs a
        # real value (MagicMock attributes break comparisons).
        settings = MagicMock()
        settings.sync_token = token
        settings.trusted_proxy_hops = 0
        settings.standby_mode = False
        return settings

    def test_missing_token_rejected(self):
        with patch("app.config.get_settings", return_value=self._settings("secret")):
            response = client.get("/internal/export-definitions")
        assert response.status_code == 403

    def test_wrong_token_rejected(self):
        with patch("app.config.get_settings", return_value=self._settings("secret")):
            response = client.get(
                "/internal/export-definitions", headers={"X-Sync-Token": "wrong"}
            )
        assert response.status_code == 403

    def test_unconfigured_token_rejects_everything(self):
        with patch("app.config.get_settings", return_value=self._settings("")):
            response = client.get(
                "/internal/export-definitions", headers={"X-Sync-Token": "anything"}
            )
        assert response.status_code == 403

    def test_valid_token_serves_export(self):
        db = AsyncMock()
        db.list_all_teams.return_value = []
        with patch("app.config.get_settings", return_value=self._settings("secret")), \
             patch("app.routers.internal.create_db_client", return_value=db):
            response = client.get(
                "/internal/export-definitions", headers={"X-Sync-Token": "secret"}
            )
        assert response.status_code == 200
        assert response.json() == {"version": 1, "teams": []}


class TestShadowMode:
    @pytest.mark.asyncio
    async def test_standby_skips_alerts_for_synced_checks(self):
        from app.handlers import _late_detector_impl

        db = AsyncMock()
        db.query_due_checks.return_value = [_check(managed=True)]
        db.update_check_to_late.return_value = True
        db.query_due_alert_deliveries.return_value = []

        settings = MagicMock()
        settings.standby_mode = True
        settings.heartbeat_url = ""

        with patch("app.handlers.create_db_client", return_value=db), \
             patch("app.handlers.get_settings", return_value=settings), \
             patch("app.handlers.get_metrics_client"), \
             patch("app.handlers.enqueue_check_alerts", new=AsyncMock()) as mock_enqueue:
            result = await _late_detector_impl({}, None)

        mock_enqueue.assert_not_called()  # shadow: detect, never alert
        body = json.loads(result["body"])
        assert body["checksProcessed"] == 1
        assert body["channelAlertsQueued"] == 0

    @pytest.mark.asyncio
    async def test_standby_still_alerts_for_native_checks(self):
        from app.handlers import _late_detector_impl

        db = AsyncMock()
        db.query_due_checks.return_value = [_check(managed=False)]  # sentinel watcher
        db.update_check_to_late.return_value = True
        db.query_due_alert_deliveries.return_value = []

        settings = MagicMock()
        settings.standby_mode = True
        settings.heartbeat_url = ""

        with patch("app.handlers.create_db_client", return_value=db), \
             patch("app.handlers.get_settings", return_value=settings), \
             patch("app.handlers.get_metrics_client"), \
             patch("app.handlers.enqueue_check_alerts", new=AsyncMock(return_value=[])) as mock_enqueue:
            await _late_detector_impl({}, None)

        mock_enqueue.assert_called_once()  # native checks alert even in standby

    @pytest.mark.asyncio
    async def test_promotion_restores_alerting(self):
        from app.handlers import _late_detector_impl

        db = AsyncMock()
        db.query_due_checks.return_value = [_check(managed=True)]
        db.update_check_to_late.return_value = True
        db.query_due_alert_deliveries.return_value = []

        settings = MagicMock()
        settings.standby_mode = False  # promoted
        settings.heartbeat_url = ""

        with patch("app.handlers.create_db_client", return_value=db), \
             patch("app.handlers.get_settings", return_value=settings), \
             patch("app.handlers.get_metrics_client"), \
             patch("app.handlers.enqueue_check_alerts", new=AsyncMock(return_value=[])) as mock_enqueue:
            await _late_detector_impl({}, None)

        mock_enqueue.assert_called_once()  # synced checks alert after promotion
