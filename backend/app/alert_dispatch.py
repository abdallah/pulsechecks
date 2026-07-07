"""Durable alert delivery pipeline.

Every alert (late / recovery / escalation) becomes an AlertDelivery record —
one per target channel — that is both a queue item and a permanent history
entry. Delivery is attempted immediately where the runtime allows, and any
failure is retried with exponential backoff by the late-detection scheduler
run (every 2 minutes) until it succeeds or exhausts max_attempts, at which
point the record lands in the terminal "failed" state (dead-letter) and a
metric fires.

This is deliberately database-backed rather than SQS/PubSub so the exact
same mechanism works on both clouds with zero extra infrastructure.
"""
import asyncio
from typing import List, Optional

from .models import AlertDelivery
from .utils import generate_id, get_iso_timestamp, get_current_time_seconds
from .logging_config import get_logger, log_business_event
from .metrics import get_metrics_client

logger = get_logger(__name__)

# Retry schedule: attempt 1 immediately, then 2m, 4m, 8m, 16m after each
# failure — five attempts spanning ~30 minutes before dead-lettering.
BACKOFF_BASE_SECONDS = 120
MAX_ATTEMPTS = 5
DELIVERY_CONCURRENCY = 10


async def enqueue_check_alerts(
    db,
    check,
    alert_type: str,
    channel_ids: Optional[List[str]] = None,
    team=None,
    attempt_now: bool = True,
) -> List[AlertDelivery]:
    """Create delivery records for a check's alert channels.

    With attempt_now=True (scheduler context) each delivery is attempted
    immediately; failures stay pending and are retried on later runs.
    With attempt_now=False (request context, e.g. the ping endpoint's
    recovery path) records are only enqueued, so the request never blocks
    on outbound notification calls — the next scheduler run (≤2 minutes)
    delivers them.
    """
    ids = channel_ids if channel_ids is not None else (check.alert_channels or [])
    if not ids:
        return []

    now = get_current_time_seconds()
    deliveries = []
    for channel_id in ids:
        channel = None
        try:
            channel = await db.get_alert_channel(check.team_id, channel_id)
        except Exception as e:
            logger.error(f"Failed to resolve channel {channel_id} for check {check.check_id}: {e}")

        delivery = AlertDelivery(
            delivery_id=generate_id(),
            team_id=check.team_id,
            check_id=check.check_id,
            check_name=check.name,
            channel_id=channel_id,
            channel_type=channel.type.value if channel else "unknown",
            channel_name=channel.display_name if channel else channel_id,
            alert_type=alert_type,
            status="pending",
            attempts=0,
            max_attempts=MAX_ATTEMPTS,
            next_attempt_at=now,
            created_at=get_iso_timestamp(),
        )
        if channel is None:
            # Dead-letter immediately — retrying a nonexistent channel is pointless.
            delivery.status = "failed"
            delivery.attempts = MAX_ATTEMPTS
            delivery.last_error = "Alert channel not found"
        await db.create_alert_delivery(delivery)
        deliveries.append(delivery)

    if attempt_now:
        pending = [d for d in deliveries if d.status == "pending"]
        semaphore = asyncio.Semaphore(DELIVERY_CONCURRENCY)

        async def _attempt(d):
            async with semaphore:
                await process_delivery(db, d, check=check, team=team)

        await asyncio.gather(*(_attempt(d) for d in pending), return_exceptions=True)

    return deliveries


async def process_delivery(db, delivery: AlertDelivery, check=None, team=None) -> bool:
    """Attempt one delivery and persist the outcome. Returns success."""
    from .handlers import _send_channel_alert  # deferred: avoid import cycle

    metrics = get_metrics_client()
    now = get_current_time_seconds()
    delivery.attempts += 1
    error: Optional[str] = None
    success = False

    try:
        if check is None:
            check = await db.get_check(delivery.team_id, delivery.check_id)
        if check is None:
            # Check was deleted since the alert was enqueued — dead-letter.
            delivery.status = "failed"
            delivery.last_error = "Check no longer exists"
            await db.update_alert_delivery(delivery)
            return False

        if team is None:
            team = await db.get_team(delivery.team_id)

        channel = await db.get_alert_channel(delivery.team_id, delivery.channel_id)
        if channel is None:
            delivery.status = "failed"
            delivery.last_error = "Alert channel no longer exists"
            await db.update_alert_delivery(delivery)
            return False

        success = await _send_channel_alert(
            channel, check, team, None, metrics, delivery.alert_type
        )
        if not success:
            error = "Channel send reported failure"
    except Exception as e:
        error = str(e)[:500]
        logger.error(
            f"Delivery {delivery.delivery_id} attempt {delivery.attempts} failed "
            f"({delivery.channel_type} channel for check {delivery.check_id}): {e}"
        )

    if success:
        delivery.status = "delivered"
        delivery.delivered_at = get_iso_timestamp()
        delivery.last_error = None
    else:
        delivery.last_error = error or "Delivery failed"
        if delivery.attempts >= delivery.max_attempts:
            delivery.status = "failed"
            metrics.increment_counter("AlertDeliveryExhausted", {
                "ChannelType": delivery.channel_type,
            })
            log_business_event(
                "alert_delivery_exhausted",
                team_id=delivery.team_id,
                check_id=delivery.check_id,
                channel_id=delivery.channel_id,
                channel_type=delivery.channel_type,
                alert_type=delivery.alert_type,
                attempts=delivery.attempts,
                error=delivery.last_error,
            )
        else:
            backoff = BACKOFF_BASE_SECONDS * (2 ** (delivery.attempts - 1))
            delivery.next_attempt_at = now + backoff

    await db.update_alert_delivery(delivery)
    return success


async def process_due_deliveries(db, limit: int = 100) -> dict:
    """Drain due pending deliveries (retries and request-context enqueues).

    Called from every late-detection run, so retries piggyback on the
    existing 2-minute scheduler on both clouds.
    """
    now = get_current_time_seconds()
    due = await db.query_due_alert_deliveries(now, limit=limit)
    if not due:
        return {"processed": 0, "delivered": 0, "failed": 0}

    semaphore = asyncio.Semaphore(DELIVERY_CONCURRENCY)
    results = []

    async def _attempt(d):
        async with semaphore:
            results.append(await process_delivery(db, d))

    await asyncio.gather(*(_attempt(d) for d in due), return_exceptions=True)

    delivered = sum(1 for r in results if r)
    stats = {"processed": len(due), "delivered": delivered, "failed": len(due) - delivered}
    if stats["processed"]:
        logger.info(f"Delivery queue drain: {stats}")
    return stats
