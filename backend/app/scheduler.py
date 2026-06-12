"""HTTP endpoint poller - background task that checks HTTP endpoints."""
import asyncio
import time
import httpx
from .db.factory import create_db_client
from .models.enums import CheckStatus, PingType
from .logging_config import get_logger
from .security import validate_webhook_url
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

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
        tasks = [_poll_single_check(client, db, check) for check in due_checks]
        await asyncio.gather(*tasks, return_exceptions=True)


async def _poll_single_check(client, db, check):
    """Poll a single HTTP check and record the result."""
    # Revalidate URL safety immediately before polling (fail closed)
    is_safe, ssrf_error = validate_webhook_url(check.url)
    if not is_safe:
        logger.warning(f"HTTP check {check.check_id} blocked by SSRF protection: {ssrf_error}")
        from .routers.ping import _record_ping_internal
        try:
            await _record_ping_internal(
                check.token,
                db,
                ping_type=PingType.FAIL,
                data=f"SSRF protection: {ssrf_error}",
                code="ssrf_blocked",
                response_time_ms=0,
            )
        except Exception as e:
            logger.error(f"Failed to record SSRF block for check {check.check_id}: {e}")
        return

    error_detail = None
    error_code = None
    response_time_ms = None
    success = False
    start_time = time.monotonic()

    try:
        resp = await client.get(check.url)
        response_time_ms = int((time.monotonic() - start_time) * 1000)
        if resp.status_code != check.expected_status_code:
            error_detail = f"Got {resp.status_code}, expected {check.expected_status_code}"
            error_code = str(resp.status_code)
        elif check.expected_string and check.expected_string not in resp.text:
            error_detail = f"Response body missing expected string: '{check.expected_string}'"
            error_code = "unexpected_response"
        else:
            success = True
    except httpx.TimeoutException:
        error_detail = f"Connection timeout after {HTTP_TIMEOUT}s"
        error_code = "timeout"
    except httpx.ConnectError as e:
        error_detail = f"Connection error: {str(e)}"
        error_code = "connection_error"
    except Exception as e:
        error_detail = f"Error: {str(e)}"
        error_code = "error"

    if response_time_ms is None:
        response_time_ms = int((time.monotonic() - start_time) * 1000)

    from .routers.ping import _record_ping_internal
    ping_type = PingType.SUCCESS if success else PingType.FAIL
    try:
        await _record_ping_internal(
            check.token,
            db,
            ping_type=ping_type,
            data=error_detail,
            code=error_code,
            response_time_ms=response_time_ms,
        )
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
