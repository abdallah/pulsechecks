"""HTTP endpoint poller - background task that checks HTTP endpoints."""
import asyncio
import httpx
from .db.factory import create_db_client
from .models.enums import CheckStatus, PingType
from .logging_config import get_logger
from .utils import get_iso_timestamp, get_current_time_seconds, calculate_next_due, calculate_alert_after

logger = get_logger(__name__)

HTTP_TIMEOUT = 10  # seconds


async def poll_http_checks():
    """Poll all active HTTP checks and record results."""
    db = create_db_client()
    checks = await db.list_all_http_checks()

    if not checks:
        return

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        tasks = [_poll_single_check(client, db, check) for check in checks]
        await asyncio.gather(*tasks, return_exceptions=True)


async def _poll_single_check(client, db, check):
    """Poll a single HTTP check and record the result."""
    try:
        resp = await client.get(check.url)
        success = resp.status_code == check.expected_status_code
    except Exception:
        success = False

    # Record result using the same logic as ping
    from .routers.ping import _record_ping_internal
    ping_type = PingType.SUCCESS if success else PingType.FAIL
    try:
        await _record_ping_internal(check.token, db, ping_type=ping_type)
    except Exception as e:
        logger.error(f"Failed to record HTTP check result for {check.check_id}: {e}")


async def _scheduler_loop():
    """Run the HTTP poller every 60 seconds."""
    while True:
        try:
            await poll_http_checks()
        except Exception as e:
            logger.error(f"HTTP poller error: {e}")
        await asyncio.sleep(60)


_scheduler_task = None


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("HTTP endpoint poller started")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("HTTP endpoint poller stopped")
