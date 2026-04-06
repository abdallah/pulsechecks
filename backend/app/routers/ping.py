"""Public ping endpoint (no auth required)."""
import json
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, status, Body
from typing import Optional

from ..dependencies import Database
from ..models import OkResponse, Ping, CheckStatus, PingType
from ..utils import (
    get_iso_timestamp,
    get_current_time_seconds,
    calculate_next_due,
    calculate_alert_after,
    calculate_next_due_from_cron,
)
from ..logging_config import get_logger, log_business_event
from ..metrics import get_metrics_client

logger = get_logger(__name__)
from ..config import get_settings

router = APIRouter(prefix="/ping", tags=["ping"])


async def _record_ping_internal(
    token: str,
    db: Database,
    ping_type: PingType = PingType.SUCCESS,
    data: Optional[str] = None
) -> OkResponse:
    """Internal helper to record a ping."""
    metrics = get_metrics_client()
    
    # Look up check by token
    check = await db.get_check_by_token(token)

    if not check:
        # Record failed ping metric
        metrics.increment_counter('PingFailed', {'Reason': 'CheckNotFound'})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found",
        )

    # Heartbeat checks only accept success pings — no start/fail signals
    if check.type == 'heartbeat' and ping_type != PingType.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Heartbeat checks only accept simple pings. Use /ping/{token} without /start or /fail.",
        )

    # Check if this is a recovery (late -> up transition) or first ping (pending -> up)
    was_late = check.status == CheckStatus.LATE.value
    was_pending = check.status == CheckStatus.PENDING.value
    
    # Record ping
    timestamp = get_iso_timestamp()
    current_time_seconds = get_current_time_seconds()

    ping = Ping(
        check_id=check.check_id,
        timestamp=timestamp,
        received_at=timestamp,
        ping_type=ping_type.value,
        data=data,
    )
    await db.create_ping(ping)

    # Update check with new ping time (only if not paused)
    if check.type == 'cron' and check.schedule:
        next_due = calculate_next_due_from_cron(check.schedule, current_time_seconds)
    else:
        next_due = calculate_next_due(current_time_seconds, check.period_seconds)
    alert_after = next_due + check.grace_seconds

    # Determine check status based on ping type
    # START: keep current status (job started, wait for completion)
    # SUCCESS: mark as UP
    # FAIL: mark as LATE (failed state)
    if ping_type == PingType.START:
        # Don't update status, just record the start
        return OkResponse(message="Start signal recorded")

    new_status = CheckStatus.UP.value if ping_type == PingType.SUCCESS else CheckStatus.LATE.value

    # Failure threshold: only go LATE if consecutive failures >= threshold
    failure_threshold = getattr(check, 'failure_threshold', 1) or 1
    consecutive = getattr(check, 'consecutive_failure_count', 0) or 0

    if ping_type == PingType.FAIL:
        consecutive += 1
        if consecutive < failure_threshold:
            new_status = check.status if check.status != CheckStatus.PAUSED.value else CheckStatus.UP.value

    updates = {
        "lastPingAt": timestamp,
        "nextDueAt": next_due,
        "alertAfterAt": alert_after,
        "status": new_status,
        "consecutiveFailureCount": 0 if ping_type == PingType.SUCCESS else consecutive,
    }

    # Conditional update - only if not paused
    success = await db.update_check_on_ping(check.team_id, check.check_id, updates)

    if success:
        # Reset alert state if check recovered (late -> up)
        if was_late and ping_type == PingType.SUCCESS:
            await db.reset_alert_state(check.team_id, check.check_id)
        
        # Record successful ping metrics
        metrics.ping_received(check.team_id, check.check_id, True)
        
        # Log business event
        log_business_event('ping_received', 
            team_id=check.team_id, 
            check_id=check.check_id, 
            ping_type=ping_type.value,
            was_late=was_late,
            was_pending=was_pending
        )
        
        # Send recovery alert if check was late and is now up
        if was_late and ping_type == PingType.SUCCESS:
            try:
                await _send_recovery_alert_async(check)
                metrics.alert_sent(check.team_id, check.check_id, 'recovery', True)
            except Exception as e:
                logger.error(f"Recovery alert failed for check {check.check_id}: {e}")
                metrics.alert_sent(check.team_id, check.check_id, 'recovery', False)
                # Continue - don't let alert failure break the ping
            
        message = "Ping recorded" if ping_type == PingType.SUCCESS else "Failure recorded"
        return OkResponse(message=message)
    else:
        # Check is paused, still record ping but don't update status
        metrics.ping_received(check.team_id, check.check_id, True)
        log_business_event('ping_received_paused', team_id=check.team_id, check_id=check.check_id)
        return OkResponse(message="Ping recorded (check is paused)")


async def _send_recovery_alert_async(check):
    """Send recovery alert via AlertChannels only."""
    try:
        from ..db import DynamoDBClient
        db = DynamoDBClient()
        
        # Get team info for alert channels
        team = await db.get_team(check.team_id)
        
        # Send recovery alerts via modern AlertChannels only
        if check.alert_channels:
            for channel_id in check.alert_channels:
                try:
                    channel = await db.get_alert_channel(check.team_id, channel_id)
                    if not channel:
                        logger.warning(f"Recovery alert channel {channel_id} not found for check {check.check_id}")
                        continue
                    
                    # Send recovery alert via the channel
                    from ..handlers import _send_channel_alert
                    success = await _send_channel_alert(channel, check, team, None, None, "recovery")
                    if success:
                        logger.info(f"Recovery alert sent via channel {channel.name} ({channel.type.value}) for check {check.check_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send recovery alert via channel {channel_id} for check {check.check_id}: {e}")
        else:
            logger.info(f"No alert channels configured for check {check.check_id} - no recovery alert sent")
                    
    except Exception as e:
        logger.error(f"Error in _send_recovery_alert_async: {e}")
        raise  # Re-raise so the caller can handle it


@router.get("/{token}", response_model=OkResponse)
async def record_ping_get(token: str, db: Database) -> OkResponse:
    """Record a successful ping via GET request (public endpoint)."""
    return await _record_ping_internal(token, db, PingType.SUCCESS)


@router.post("/{token}", response_model=OkResponse)
async def record_ping_post(
    token: str,
    db: Database,
    data: Optional[str] = Body(default=None, embed=True),
) -> OkResponse:
    """Record a successful ping via POST request with optional data (public endpoint)."""
    return await _record_ping_internal(token, db, PingType.SUCCESS, data)


@router.get("/{token}/fail", response_model=OkResponse)
@router.post("/{token}/fail", response_model=OkResponse)
async def record_ping_fail(
    token: str,
    db: Database,
    data: Optional[str] = Body(default=None, embed=True),
) -> OkResponse:
    """Record a failure ping - job ran but failed (public endpoint)."""
    return await _record_ping_internal(token, db, PingType.FAIL, data)


@router.get("/{token}/start", response_model=OkResponse)
@router.post("/{token}/start", response_model=OkResponse)
async def record_ping_start(
    token: str,
    db: Database,
    data: Optional[str] = Body(default=None, embed=True),
) -> OkResponse:
    """Record a start ping - job has started (public endpoint)."""
    return await _record_ping_internal(token, db, PingType.START, data)


@router.get("/{first}/{second}", response_model=OkResponse)
@router.post("/{first}/{second}", response_model=OkResponse)
async def record_ping_two_segment(
    first: str,
    second: str,
    db: Database,
    data: Optional[str] = Body(default=None, embed=True),
) -> OkResponse:
    """Two-segment ping handler — resolves in order:
    1. /ping/{team_slug}/{check_slug}  → success ping via name-based URL
    2. /ping/{token}/{code}            → failure ping with error code (legacy)
    """
    import re

    # ── 1. Try team_slug + check_slug lookup first ────────────────────────
    check = await db.get_check_by_team_slug_and_check_slug(first, second)
    if check:
        return await _record_ping_internal(check.token, db, PingType.SUCCESS)

    # ── 2. Fall back to token + error code ───────────────────────────────
    if not re.match(r'^[a-zA-Z0-9_]{1,50}$', second):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error code must be 1-50 alphanumeric characters or underscores",
        )

    metrics = get_metrics_client()
    check = await db.get_check_by_token(first)

    if not check:
        metrics.increment_counter('PingFailed', {'Reason': 'CheckNotFound'})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found",
        )

    # Record ping with code
    timestamp = get_iso_timestamp()
    ping = Ping(
        check_id=check.check_id,
        timestamp=timestamp,
        received_at=timestamp,
        ping_type=PingType.FAIL.value,
        code=second,
        data=data,
    )
    await db.create_ping(ping)

    current_time_seconds = get_current_time_seconds()
    if check.type == 'cron' and check.schedule:
        next_due = calculate_next_due_from_cron(check.schedule, current_time_seconds)
    else:
        next_due = calculate_next_due(current_time_seconds, check.period_seconds)

    updates = {
        "lastPingAt": timestamp,
        "nextDueAt": next_due,
        "alertAfterAt": next_due + check.grace_seconds,
        "status": CheckStatus.LATE.value,
    }

    await db.update_check_on_ping(check.team_id, check.check_id, updates)
    metrics.ping_received(check.team_id, check.check_id, False)

    return OkResponse(message=f"Failure recorded with code: {second}")


@router.get("/by-slug/{slug}/success", response_model=OkResponse)
@router.post("/by-slug/{slug}/success", response_model=OkResponse)
async def record_ping_by_slug_success(
    slug: str,
    db: Database,
    team_id: Optional[str] = None,
) -> OkResponse:
    """Record a successful ping using check slug (legacy — use /{team_slug}/{check_slug}/success instead)."""
    if not team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="team_id is required for slug-based pinging",
        )
    check = await db.get_check_by_slug(team_id, slug)
    if not check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")
    return await _record_ping_internal(check.token, db, PingType.SUCCESS)


@router.get("/by-slug/{slug}/fail", response_model=OkResponse)
@router.post("/by-slug/{slug}/fail", response_model=OkResponse)
async def record_ping_by_slug_fail(
    slug: str,
    db: Database,
    team_id: Optional[str] = None,
    data: Optional[str] = Body(default=None, embed=True),
) -> OkResponse:
    """Record a failure ping using check slug (legacy — use /{team_slug}/{check_slug}/fail instead)."""
    if not team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="team_id is required for slug-based pinging",
        )
    check = await db.get_check_by_slug(team_id, slug)
    if not check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")
    return await _record_ping_internal(check.token, db, PingType.FAIL, data)


# ─── Clean slug routes: /ping/{team_slug}/{check_slug}/{action} ───────────────

@router.get("/{team_slug}/{check_slug}/success", response_model=OkResponse)
@router.post("/{team_slug}/{check_slug}/success", response_model=OkResponse)
async def record_ping_by_team_and_check_slug_success(
    team_slug: str,
    check_slug: str,
    db: Database,
) -> OkResponse:
    """Record a successful ping using team slug + check slug.
    Usage: /ping/my-team/backup-job/success
    """
    check = await db.get_check_by_team_slug_and_check_slug(team_slug, check_slug)
    if not check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")
    return await _record_ping_internal(check.token, db, PingType.SUCCESS)


@router.get("/{team_slug}/{check_slug}/fail", response_model=OkResponse)
@router.post("/{team_slug}/{check_slug}/fail", response_model=OkResponse)
async def record_ping_by_team_and_check_slug_fail(
    team_slug: str,
    check_slug: str,
    db: Database,
    data: Optional[str] = Body(default=None, embed=True),
) -> OkResponse:
    """Record a failure ping using team slug + check slug.
    Usage: /ping/my-team/backup-job/fail
    """
    check = await db.get_check_by_team_slug_and_check_slug(team_slug, check_slug)
    if not check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")
    return await _record_ping_internal(check.token, db, PingType.FAIL, data)



