"""Check management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, Query, status, HTTPException

from ..dependencies import AuthUser, Database, check_team_access
from ..errors import NotFoundError, ValidationError
from ..logging_config import get_logger, log_business_event
from ..metrics import get_metrics_client
from ..utils import generate_token, get_iso_timestamp, get_current_time_seconds

logger = get_logger(__name__)
from ..models import (
    CreateCheckRequest,
    UpdateCheckRequest,
    CheckResponse,
    CheckDetailResponse,
    PingResponse,
    OkResponse,
    Check,
    CheckStatus,
    Permission,
    Role,
)
from ..utils import (
    generate_id,
    generate_token,
    get_iso_timestamp,
    get_current_time_seconds,
    calculate_next_due,
    calculate_alert_after,
)

router = APIRouter(prefix="/teams/{team_id}/checks", tags=["checks"])


# Bulk Operations (must be defined before individual check operations to avoid routing conflicts)
@router.post("/bulk/pause", response_model=OkResponse)
async def bulk_pause_checks(
    team_id: str,
    request: dict,  # {"check_ids": ["id1", "id2", ...]}
    current_user: AuthUser,
    db: Database,
):
    """Pause multiple checks at once."""
    # Check team access (requires EDIT permission for bulk operations)
    await check_team_access(team_id, current_user, db, Permission.EDIT)
    
    check_ids = request.get("check_ids", [])
    
    paused_count = 0
    for check_id in check_ids:
        try:
            check = await db.get_check(team_id, check_id)
            if check:
                logger.info(f"Check {check_id} current status: {check.status}")
                if check.status != CheckStatus.PAUSED.value:
                    await db.update_check_status(team_id, check_id, CheckStatus.PAUSED.value)
                    paused_count += 1
                    logger.info(f"Successfully paused check {check_id}")
                else:
                    logger.warning(f"Check {check_id} is already paused, skipping")
            else:
                logger.warning(f"Check {check_id} not found")
        except Exception as e:
            logger.warning(f"Failed to pause check {check_id}: {e}")
    
    log_business_event('bulk_pause_checks', 
        team_id=team_id, 
        user_id=current_user.user_id,
        checks_requested=len(check_ids),
        checks_paused=paused_count
    )
    
    return OkResponse(message=f"Paused {paused_count} of {len(check_ids)} checks")


@router.post("/bulk/resume", response_model=OkResponse)
async def bulk_resume_checks(
    team_id: str,
    request: dict,  # {"check_ids": ["id1", "id2", ...]}
    current_user: AuthUser,
    db: Database,
):
    """Resume multiple checks at once."""
    # Check team access (requires EDIT permission for bulk operations)
    await check_team_access(team_id, current_user, db, Permission.EDIT)
    
    check_ids = request.get("check_ids", [])
    
    resumed_count = 0
    current_time = get_current_time_seconds()
    
    for check_id in check_ids:
        try:
            check = await db.get_check(team_id, check_id)
            if check:
                logger.info(f"Check {check_id} current status: {check.status}")
                if check.status == CheckStatus.PAUSED.value:
                    # Calculate new due times when resuming
                    next_due_at = calculate_next_due(current_time, check.period_seconds)
                    alert_after_at = calculate_alert_after(current_time, check.period_seconds, check.grace_seconds)
                    
                    await db.update_check_status(team_id, check_id, CheckStatus.PENDING.value)
                    await db.update_check_timing(team_id, check_id, next_due_at, alert_after_at)
                    resumed_count += 1
                    logger.info(f"Successfully resumed check {check_id}")
                else:
                    logger.warning(f"Check {check_id} is not paused (status: {check.status}), skipping")
            else:
                logger.warning(f"Check {check_id} not found")
        except Exception as e:
            logger.warning(f"Failed to resume check {check_id}: {e}")
    
    log_business_event('bulk_resume_checks', 
        team_id=team_id, 
        user_id=current_user.user_id,
        checks_requested=len(check_ids),
        checks_resumed=resumed_count
    )
    
    return OkResponse(message=f"Resumed {resumed_count} of {len(check_ids)} checks")


@router.post("", response_model=CheckDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_check(
    team_id: str,
    request: CreateCheckRequest,
    current_user: AuthUser,
    db: Database,
) -> CheckDetailResponse:
    """Create a new check for a team."""
    # Check team access (requires EDIT permission)
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    # Generate check ID and token
    check_id = generate_id()
    token = generate_token()

    # Create check
    check = Check(
        check_id=check_id,
        team_id=team_id,
        name=request.name,
        token=token,
        period_seconds=request.period_seconds,
        grace_seconds=request.grace_seconds,
        status=CheckStatus.PENDING,  # New checks start as pending
        created_at=get_iso_timestamp(),
        alert_channels=request.alert_channels,
    )
    await db.create_check(check)
    
    # Record metrics and log business event
    metrics = get_metrics_client()
    metrics.check_created(team_id)
    log_business_event('check_created', team_id=team_id, check_id=check_id, check_name=request.name)

    return CheckDetailResponse(
        checkId=check_id,
        teamId=team_id,
        name=request.name,
        status=CheckStatus.PENDING,  # New checks start as pending
        periodSeconds=request.period_seconds,
        graceSeconds=request.grace_seconds,
        token=token,
        createdAt=check.created_at,
        alertChannels=request.alert_channels,
    )


@router.get("", response_model=List[CheckResponse])
async def list_team_checks(
    team_id: str,
    current_user: AuthUser,
    db: Database,
) -> List[CheckResponse]:
    """List all checks for a team."""
    # Check team access (requires VIEW permission)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    checks = await db.list_team_checks(team_id)

    return [
        CheckResponse(
            checkId=check.check_id,
            teamId=check.team_id,
            name=check.name,
            status=check.status,
            periodSeconds=check.period_seconds,
            graceSeconds=check.grace_seconds,
            lastPingAt=check.last_ping_at,
            nextDueAt=check.next_due_at,
            createdAt=check.created_at,
        )
        for check in checks
    ]


@router.get("/{check_id}", response_model=CheckDetailResponse)
async def get_check_detail(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> CheckDetailResponse:
    """Get detailed information about a check."""
    # Check team access (requires VIEW permission)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    check = await db.get_check(team_id, check_id)

    if not check:
        raise NotFoundError("Check not found")

    return CheckDetailResponse(
        checkId=check.check_id,
        teamId=check.team_id,
        name=check.name,
        status=check.status,
        periodSeconds=check.period_seconds,
        graceSeconds=check.grace_seconds,
        token=check.token,
        lastPingAt=check.last_ping_at,
        nextDueAt=check.next_due_at,
        alertAfterAt=check.alert_after_at,
        lastAlertAt=check.last_alert_at,
        createdAt=check.created_at,
        alertChannels=check.alert_channels,
        escalationMinutes=check.escalation_minutes,
        escalationTriggeredAt=getattr(check, 'escalation_triggered_at', None),
        suppressAfterCount=getattr(check, 'suppress_after_count', None),
        suppressDurationMinutes=getattr(check, 'suppress_duration_minutes', None),
        consecutiveAlertCount=getattr(check, 'consecutive_alert_count', 0),
        suppressedUntil=getattr(check, 'suppressed_until', None),
    )


@router.patch("/{check_id}", response_model=CheckDetailResponse)
async def update_check(
    team_id: str,
    check_id: str,
    request: UpdateCheckRequest,
    current_user: AuthUser,
    db: Database,
) -> CheckDetailResponse:
    """Update check configuration."""
    # Check team access (requires EDIT permission)
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    # Build updates dict (only include provided fields)
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.period_seconds is not None:
        updates["periodSeconds"] = request.period_seconds
    if request.grace_seconds is not None:
        updates["graceSeconds"] = request.grace_seconds
    if request.alert_channels is not None:
        updates["alertChannels"] = request.alert_channels
    if request.escalation_minutes is not None:
        updates["escalationMinutes"] = request.escalation_minutes
    if request.suppress_after_count is not None:
        updates["suppressAfterCount"] = request.suppress_after_count
    if request.suppress_duration_minutes is not None:
        updates["suppressDurationMinutes"] = request.suppress_duration_minutes

    if not updates:
        # No updates provided, return current check
        return CheckDetailResponse(
            checkId=check.check_id,
            teamId=check.team_id,
            name=check.name,
            status=check.status,
            periodSeconds=check.period_seconds,
            graceSeconds=check.grace_seconds,
            token=check.token,
            lastPingAt=check.last_ping_at,
            nextDueAt=check.next_due_at,
            alertAfterAt=check.alert_after_at,
            lastAlertAt=check.last_alert_at,
            createdAt=check.created_at,
            alertChannels=check.alert_channels,
            escalationMinutes=check.escalation_minutes,
            escalationAlertChannels=check.escalation_alert_channels,
            escalationTriggeredAt=getattr(check, 'escalation_triggered_at', None),
            suppressAfterCount=getattr(check, 'suppress_after_count', None),
            suppressDurationMinutes=getattr(check, 'suppress_duration_minutes', None),
            consecutiveAlertCount=getattr(check, 'consecutive_alert_count', 0),
            suppressedUntil=getattr(check, 'suppressed_until', None),
        )

    # Recalculate alert time if period or grace changed
    if ("periodSeconds" in updates or "graceSeconds" in updates) and check.last_ping_at:
        period = updates.get("periodSeconds", check.period_seconds)
        grace = updates.get("graceSeconds", check.grace_seconds)
        # Parse last ping time to seconds
        from datetime import datetime

        last_ping_dt = datetime.fromisoformat(check.last_ping_at.replace("Z", "+00:00"))
        last_ping_seconds = int(last_ping_dt.timestamp())
        updates["alertAfterAt"] = calculate_alert_after(last_ping_seconds, period, grace)
        updates["nextDueAt"] = calculate_next_due(last_ping_seconds, period)

    # Perform update
    updated_check = await db.update_check(team_id, check_id, updates)

    return CheckDetailResponse(
        checkId=updated_check.check_id,
        teamId=updated_check.team_id,
        name=updated_check.name,
        status=updated_check.status,
        periodSeconds=updated_check.period_seconds,
        graceSeconds=updated_check.grace_seconds,
        token=updated_check.token,
        lastPingAt=updated_check.last_ping_at,
        nextDueAt=updated_check.next_due_at,
        alertAfterAt=updated_check.alert_after_at,
        lastAlertAt=updated_check.last_alert_at,
        createdAt=updated_check.created_at,
        alertChannels=updated_check.alert_channels,
        escalationMinutes=updated_check.escalation_minutes,
        escalationTriggeredAt=getattr(updated_check, 'escalation_triggered_at', None),
        suppressAfterCount=getattr(updated_check, 'suppress_after_count', None),
        suppressDurationMinutes=getattr(updated_check, 'suppress_duration_minutes', None),
        consecutiveAlertCount=getattr(updated_check, 'consecutive_alert_count', 0),
        suppressedUntil=getattr(updated_check, 'suppressed_until', None),
    )


@router.post("/{check_id}/pause", response_model=OkResponse)
async def pause_check(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Pause monitoring for a check."""
    # Check team access (requires EDIT permission)
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    # Update status to paused
    await db.update_check(team_id, check_id, {"status": CheckStatus.PAUSED.value})

    return OkResponse(message="Check paused")


@router.post("/{check_id}/resume", response_model=OkResponse)
async def resume_check(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Resume monitoring for a paused check."""
    # Check team access (requires EDIT permission)
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    # Update status to up
    await db.update_check(team_id, check_id, {"status": CheckStatus.UP.value})

    return OkResponse(message="Check resumed")


@router.post("/{check_id}/rotate-token", response_model=CheckDetailResponse)
async def rotate_check_token(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> CheckDetailResponse:
    """Rotate check token (admin/owner only)."""
    # Check team access (requires ADMIN permission)
    await check_team_access(team_id, current_user, db, Permission.ADMIN)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    # Generate new token
    new_token = generate_token()
    
    # Update check with new token
    updates = {"token": new_token}
    updated_check = await db.update_check(team_id, check_id, updates)

    return CheckDetailResponse(
        checkId=updated_check.check_id,
        teamId=updated_check.team_id,
        name=updated_check.name,
        status=updated_check.status,
        periodSeconds=updated_check.period_seconds,
        graceSeconds=updated_check.grace_seconds,
        token=updated_check.token,
        lastPingAt=updated_check.last_ping_at,
        nextDueAt=updated_check.next_due_at,
        alertAfterAt=updated_check.alert_after_at,
        lastAlertAt=updated_check.last_alert_at,
        createdAt=updated_check.created_at,
        alertChannels=updated_check.alert_channels,
        escalationMinutes=updated_check.escalation_minutes,
        escalationTriggeredAt=getattr(updated_check, 'escalation_triggered_at', None),
        suppressAfterCount=getattr(updated_check, 'suppress_after_count', None),
        suppressDurationMinutes=getattr(updated_check, 'suppress_duration_minutes', None),
        consecutiveAlertCount=getattr(updated_check, 'consecutive_alert_count', 0),
        suppressedUntil=getattr(updated_check, 'suppressed_until', None),
    )


@router.post("/{check_id}/escalate", response_model=OkResponse)
async def escalate_check_immediately(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Trigger immediate escalation for a check (admin/owner only)."""
    # Check team access (requires ADMIN permission)
    await check_team_access(team_id, current_user, db, Permission.ADMIN)

    # Verify check exists and has escalation configured
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")
    
    if not getattr(check, 'escalation_minutes', None) or not getattr(check, 'escalation_alert_channels', []):
        raise ValidationError("Check does not have escalation configured")

    # Mark escalation as triggered
    await db.mark_escalation_triggered(team_id, check_id, get_iso_timestamp())
    
    # Send escalated alerts immediately
    try:
        from ..handlers import _send_escalated_alerts
        import boto3
        from ..config import get_settings
        
        settings = get_settings()
        sns_client = boto3.client("sns", region_name=settings.aws_region)
        team = await db.get_team(team_id)
        
        await _send_escalated_alerts(check, team, sns_client, get_metrics_client())
        
        return OkResponse(message="Escalation triggered successfully")
    except Exception as e:
        logger.error(f"Failed to trigger escalation for check {check_id}: {e}")
        raise ValidationError("Failed to trigger escalation")


@router.post("/{check_id}/suppress", response_model=OkResponse)
async def suppress_check_immediately(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Suppress alerts for a check immediately (admin/owner only)."""
    # Check team access (requires ADMIN permission)
    await check_team_access(team_id, current_user, db, Permission.ADMIN)

    # Verify check exists and has suppression configured
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")
    
    if not getattr(check, 'suppress_duration_minutes', None):
        raise ValidationError("Check does not have suppression configured")

    # Calculate suppression end time
    current_time = get_current_time_seconds()
    suppress_until = current_time + (check.suppress_duration_minutes * 60)
    
    # Suppress alerts
    await db.suppress_check_alerts(team_id, check_id, get_iso_timestamp(suppress_until))
    
    return OkResponse(message=f"Alerts suppressed for {check.suppress_duration_minutes} minutes")


@router.post("/{check_id}/rotate-token", response_model=CheckDetailResponse)
async def rotate_check_token(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> CheckDetailResponse:
    """Rotate the token for a check (admin/owner only)."""
    # Check team access (requires ADMIN permission for token rotation)
    await check_team_access(team_id, current_user, db, Permission.ADMIN)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    # Generate new token
    new_token = generate_token()
    
    # Update check with new token
    updated_check = await db.update_check(team_id, check_id, {"token": new_token})

    return CheckDetailResponse(
        checkId=updated_check.check_id,
        teamId=updated_check.team_id,
        name=updated_check.name,
        status=updated_check.status,
        periodSeconds=updated_check.period_seconds,
        graceSeconds=updated_check.grace_seconds,
        token=updated_check.token,
        lastPingAt=updated_check.last_ping_at,
        nextDueAt=updated_check.next_due_at,
        alertAfterAt=updated_check.alert_after_at,
        lastAlertAt=updated_check.last_alert_at,
        createdAt=updated_check.created_at,
        alertChannels=updated_check.alert_channels,
    )


@router.delete("/{check_id}", response_model=OkResponse)
async def delete_check(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Delete a check and all its pings (admin/owner only)."""
    # Check team access (requires ADMIN permission for deletion)
    await check_team_access(team_id, current_user, db, Permission.ADMIN)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    # Delete check (this should cascade delete pings)
    await db.delete_check(team_id, check_id)
    
    # Record metrics and log business event
    metrics = get_metrics_client()
    metrics.check_deleted(team_id)
    log_business_event('check_deleted', team_id=team_id, check_id=check_id, check_name=check.name)

    return OkResponse(message="Check deleted successfully")


@router.get("/{check_id}/pings", response_model=List[PingResponse])
async def list_check_pings(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
    limit: int = Query(default=50, ge=1, le=100),
    since: int = Query(default=None, description="Unix timestamp in milliseconds to filter pings from"),
) -> List[PingResponse]:
    """Get ping history for a check."""
    # Check team access (requires VIEW permission)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    pings = await db.list_check_pings(check_id, limit, since)

    return [
        PingResponse(
            checkId=ping.check_id,
            timestamp=ping.timestamp,
            receivedAt=ping.received_at,
            pingType=ping.ping_type,
            data=ping.data,
        )
        for ping in pings
    ]
