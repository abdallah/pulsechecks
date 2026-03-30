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
    """Poll all active HTTP checks that are due."""
    db = create_db_client()
    all_checks = await db.list_all_http_checks()

    if not all_checks:
        return

    # Only poll checks that are actually due (next_due_at <= now)
    now = get_current_time_seconds()
    due_checks = []
    for check in all_checks:
        if check.next_due_at is None:
            # Never been polled — poll now
            due_checks.append(check)
        else:
            try:
                from datetime import datetime, timezone
                due_dt = datetime.fromisoformat(check.next_due_at.replace("Z", "+00:00"))
                if due_dt.timestamp() <= now:
                    due_checks.append(check)
            except Exception:
                due_checks.append(check)

    if not due_checks:
        return

    logger.info(f"HTTP poller: {len(due_checks)} checks due out of {len(all_checks)} total")

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        tasks = [_poll_single_check(client, db, check) for check in due_checks]
        await asyncio.gather(*tasks, return_exceptions=True)


async def _poll_single_check(client, db, check):
    """Poll a single HTTP check and record the result."""
    error_detail = None
    success = False

    try:
        resp = await client.get(check.url)
        if resp.status_code != check.expected_status_code:
            error_detail = f"Got {resp.status_code}, expected {check.expected_status_code}"
        elif check.expected_string and check.expected_string not in resp.text:
            error_detail = f"Response body missing expected string: '{check.expected_string}'"
        else:
            success = True
    except httpx.TimeoutException:
        error_detail = f"Connection timeout after {HTTP_TIMEOUT}s"
    except httpx.ConnectError as e:
        error_detail = f"Connection error: {str(e)}"
    except Exception as e:
        error_detail = f"Error: {str(e)}"

    from .routers.ping import _record_ping_internal
    ping_type = PingType.SUCCESS if success else PingType.FAIL
    try:
        await _record_ping_internal(check.token, db, ping_type=ping_type, data=error_detail)
        if error_detail:
            logger.warning(f"HTTP check failed for {check.check_id} ({check.url}): {error_detail}")
        else:
            logger.debug(f"HTTP check OK for {check.check_id} ({check.url})")
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
