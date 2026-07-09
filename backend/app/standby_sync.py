"""Cross-cloud definition sync for the warm standby.

The standby (AWS) periodically pulls *definitions* — teams, members, checks
(including ping tokens, so customer URLs survive failover), and alert
channels — from the primary (GCP) and mirrors them into its own database.
Ping history is deliberately not synced: it is ephemeral (90-day TTL) and
irrelevant to taking over ingestion + alerting.

Security: the export endpoint is protected by SYNC_TOKEN, a shared secret
compared in constant time. The payload includes check tokens and channel
configurations (webhook URLs, SMTP recipients), so treat the token with
the same care as a database credential.
"""
import asyncio
from typing import Any, Dict

import httpx

from .config import get_settings
from .models import AlertChannel, Check, Team, TeamMember
from .logging_config import get_logger, log_business_event

logger = get_logger(__name__)

SYNC_HTTP_TIMEOUT = 30.0


async def build_definitions_export(db) -> Dict[str, Any]:
    """Collect every team's definitions into a portable payload."""
    teams = await db.list_all_teams()
    payload = {"version": 1, "teams": []}

    for team in teams:
        members = await db.list_team_members(team.team_id)
        checks = await db.list_team_checks(team.team_id)
        channels = await db.list_alert_channels(team.team_id)
        payload["teams"].append({
            "team": team.model_dump(),
            "members": [m.model_dump() for m in members],
            "checks": [c.model_dump() for c in checks],
            "channels": [c.model_dump() for c in channels],
        })

    return payload


async def apply_definitions(db, payload: Dict[str, Any]) -> Dict[str, int]:
    """Mirror an export payload into the local database (upsert semantics).

    Synced checks are stamped managed_by_sync=True so the late detector's
    shadow mode knows not to alert for them while STANDBY_MODE is on.
    Entities deleted on the primary linger here until promotion cleanup —
    acceptable for a standby whose job is to not miss anything.
    """
    counts = {"teams": 0, "members": 0, "checks": 0, "channels": 0}

    for entry in payload.get("teams", []):
        team = Team(**entry["team"])
        await db.create_team(team)
        counts["teams"] += 1

        for member_data in entry.get("members", []):
            await db.add_team_member(TeamMember(**member_data))
            counts["members"] += 1

        for check_data in entry.get("checks", []):
            check = Check(**check_data)
            check.managed_by_sync = True
            await db.create_check(check)
            counts["checks"] += 1

        for channel_data in entry.get("channels", []):
            await db.create_alert_channel(AlertChannel(**channel_data))
            counts["channels"] += 1

    return counts


async def pull_definitions_from_primary(db) -> Dict[str, int]:
    """Fetch the primary's export and mirror it locally."""
    settings = get_settings()
    if not settings.primary_export_url or not settings.sync_token:
        raise RuntimeError(
            "Standby sync requires PRIMARY_EXPORT_URL and SYNC_TOKEN to be set"
        )

    async with httpx.AsyncClient(timeout=SYNC_HTTP_TIMEOUT) as client:
        response = await client.get(
            settings.primary_export_url,
            headers={"X-Sync-Token": settings.sync_token},
        )
        response.raise_for_status()
        payload = response.json()

    counts = await apply_definitions(db, payload)
    log_business_event("standby_sync_completed", **counts)
    logger.info(f"Standby sync completed: {counts}")
    return counts


def standby_sync_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda entry point (EventBridge scheduled) for the standby sync pull."""
    from .db import create_db_client

    async def _run():
        db = create_db_client()
        return await pull_definitions_from_primary(db)

    try:
        counts = asyncio.run(_run())
        return {"statusCode": 200, "body": str(counts)}
    except Exception as e:
        logger.error(f"Standby sync failed: {e}")
        return {"statusCode": 500, "body": str(e)}
