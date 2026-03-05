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
    next_due = calculate_next_due(current_time_seconds, check.period_seconds)
    alert_after = calculate_alert_after(
        current_time_seconds, check.period_seconds, check.grace_seconds
    )

    # Determine check status based on ping type
    # START: keep current status (job started, wait for completion)
    # SUCCESS: mark as UP
    # FAIL: mark as LATE (failed state)
    if ping_type == PingType.START:
        # Don't update status, just record the start
        return OkResponse(message="Start signal recorded")

    # Update check with new ping time (only if not paused)
    next_due = calculate_next_due(current_time_seconds, check.period_seconds)
    alert_after = calculate_alert_after(
        current_time_seconds, check.period_seconds, check.grace_seconds
    )

    new_status = CheckStatus.UP.value if ping_type == PingType.SUCCESS else CheckStatus.LATE.value
    
    updates = {
        "lastPingAt": timestamp,
        "nextDueAt": next_due,
        "alertAfterAt": alert_after,
        "status": new_status,
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
