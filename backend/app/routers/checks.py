"""Check management endpoints."""
from collections import Counter
import math
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, HTTPException

from ..dependencies import AuthUser, Database, check_team_access
from ..errors import NotFoundError, ValidationError
from ..logging_config import get_logger, log_business_event
from ..metrics import get_metrics_client
from ..utils import generate_token, get_iso_timestamp, get_current_time_seconds, generate_slug
from ..utils.common import parse_iso_timestamp
from ..posthog_client import get_posthog_client, new_context, identify_context
from ..audit import record_audit

logger = get_logger(__name__)
from ..models import (
    CreateCheckRequest,
    UpdateCheckRequest,
    CheckResponse,
    CheckDetailResponse,
    CheckErrorIncidentResponse,
    CheckErrorSummaryResponse,
    CheckUptimeIncidentResponse,
    CheckUptimeResponse,
    CheckStatsResponse,
    ErrorCodeCountResponse,
    MaintenanceWindowResponse,
    PingResponse,
    OkResponse,
    Check,
    CheckStatus,
    CheckType,
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
    calculate_next_due_from_cron,
)

router = APIRouter(prefix="/teams/{team_id}/checks", tags=["checks"])

STATS_RANGE_SECONDS = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}


def _merge_intervals(intervals: List[tuple[int, int]]) -> List[tuple[int, int]]:
    """Merge overlapping second-based intervals."""
    if not intervals:
        return []

    ordered = sorted(intervals)
    merged = [ordered[0]]
    for start_at, end_at in ordered[1:]:
        previous_start, previous_end = merged[-1]
        if start_at <= previous_end:
            merged[-1] = (previous_start, max(previous_end, end_at))
        else:
            merged.append((start_at, end_at))
    return merged


def _overlap_seconds(start_at: int, end_at: int, intervals: List[tuple[int, int]]) -> int:
    """Return overlapped seconds between one interval and a list of merged intervals."""
    total = 0
    for interval_start, interval_end in intervals:
        overlap_start = max(start_at, interval_start)
        overlap_end = min(end_at, interval_end)
        if overlap_end > overlap_start:
            total += overlap_end - overlap_start
    return total


def _round_minutes(seconds: int) -> float:
    """Round seconds to minutes with 2 decimal precision."""
    return round(seconds / 60, 2)


def _serialize_maintenance_window(window) -> MaintenanceWindowResponse:
    """Convert a maintenance entity to API format."""
    return MaintenanceWindowResponse(
        windowId=window.window_id,
        teamId=window.team_id,
        checkId=window.check_id,
        startAt=window.start_at,
        endAt=window.end_at,
        label=window.label,
        createdBy=window.created_by,
        createdAt=window.created_at,
    )


def _percentile(values: List[int], percentile: float) -> int | None:
    """Return the nearest-rank percentile from a list of integers."""
    if not values:
        return None

    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100) * len(ordered)))
    return ordered[rank - 1]


def _ping_received_at_seconds(ping) -> int:
    """Return a ping timestamp in epoch seconds for stable sorting and duration math."""
    return parse_iso_timestamp(ping.received_at)


def _build_check_stats_response(pings: List, period: str) -> CheckStatsResponse:
    """Aggregate a check's recent pings into a stats payload."""
    success_count = sum(1 for ping in pings if ping.ping_type == CheckStatus.UP.value or ping.ping_type == "success")
    fail_count = sum(1 for ping in pings if ping.ping_type == "fail")
    total_pings = success_count + fail_count

    response_samples = [ping.response_time_ms for ping in pings if ping.response_time_ms is not None]
    response_series = [
        {
            "timestamp": ping.received_at,
            "responseTimeMs": ping.response_time_ms,
            "pingType": ping.ping_type,
        }
        for ping in sorted(pings, key=_ping_received_at_seconds)
        if ping.response_time_ms is not None
    ]

    latest_response_ms = response_series[-1]["responseTimeMs"] if response_series else None
    uptime_pct = round((success_count / total_pings) * 100, 2) if total_pings else 0.0

    return CheckStatsResponse(
        period=period,
        uptimePct=uptime_pct,
        totalPings=total_pings,
        successCount=success_count,
        failCount=fail_count,
        avgResponseMs=round(sum(response_samples) / len(response_samples)) if response_samples else None,
        p95ResponseMs=_percentile(response_samples, 95),
        maxResponseMs=max(response_samples) if response_samples else None,
        minResponseMs=min(response_samples) if response_samples else None,
        latestResponseMs=latest_response_ms,
        responseTimeSeries=response_series,
    )


def _serialize_ping(ping) -> PingResponse:
    """Convert a ping entity to API response format."""
    return PingResponse(
        checkId=ping.check_id,
        timestamp=ping.timestamp,
        receivedAt=ping.received_at,
        pingType=ping.ping_type,
        code=ping.code,
        data=ping.data,
        responseTimeMs=ping.response_time_ms,
    )


def _build_check_error_summary_response(pings: List, period: str) -> CheckErrorSummaryResponse:
    """Aggregate a check's failures into summary and incident data."""
    ordered_pings = sorted(pings, key=_ping_received_at_seconds)
    failures = [ping for ping in ordered_pings if ping.ping_type == "fail"]
    code_counts = Counter((ping.code or "unknown") for ping in failures)

    incidents = []
    current_incident = []
    for ping in ordered_pings:
        if ping.ping_type == "fail":
            current_incident.append(ping)
            continue

        if current_incident:
            incidents.append(current_incident)
            current_incident = []

    if current_incident:
        incidents.append(current_incident)

    longest_incident = None
    if incidents:
        longest = max(
            incidents,
            key=lambda incident: (
                _ping_received_at_seconds(incident[-1]) - _ping_received_at_seconds(incident[0]),
                len(incident),
            ),
        )
        longest_code = Counter((ping.code or "unknown") for ping in longest).most_common(1)[0][0]
        longest_incident = CheckErrorIncidentResponse(
            startedAt=longest[0].received_at,
            endedAt=longest[-1].received_at,
            durationSeconds=max(0, _ping_received_at_seconds(longest[-1]) - _ping_received_at_seconds(longest[0])),
            failureCount=len(longest),
            dominantCode=longest_code,
        )

    recent_failures = [_serialize_ping(ping) for ping in sorted(failures, key=_ping_received_at_seconds, reverse=True)[:10]]

    return CheckErrorSummaryResponse(
        period=period,
        totalFailures=len(failures),
        mostCommonCode=code_counts.most_common(1)[0][0] if code_counts else None,
        lastFailureAt=failures[-1].received_at if failures else None,
        longestIncident=longest_incident,
        failureCodes=[
            ErrorCodeCountResponse(code=code, count=count)
            for code, count in sorted(code_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        recentFailures=recent_failures,
    )


def _build_check_uptime_response(check, pings: List, windows: List, from_at: str, to_at: str, exclude_maintenance: bool) -> CheckUptimeResponse:
    """Aggregate uptime for an arbitrary reporting window."""
    range_start = parse_iso_timestamp(from_at)
    range_end = parse_iso_timestamp(to_at)
    ordered_pings = sorted(pings, key=_ping_received_at_seconds)

    maintenance_intervals = _merge_intervals([
        (
            max(range_start, parse_iso_timestamp(window.start_at)),
            min(range_end, parse_iso_timestamp(window.end_at)),
        )
        for window in windows
        if parse_iso_timestamp(window.end_at) > range_start and parse_iso_timestamp(window.start_at) < range_end
    ])

    excluded_seconds = sum(end_at - start_at for start_at, end_at in maintenance_intervals)

    observed_seconds = 0
    downtime_seconds = 0
    incidents = []
    current_incident = []

    for index, ping in enumerate(ordered_pings):
        ping_start = max(range_start, _ping_received_at_seconds(ping))
        next_ping_at = range_end
        if index + 1 < len(ordered_pings):
            next_ping_at = min(range_end, _ping_received_at_seconds(ordered_pings[index + 1]))

        if next_ping_at <= ping_start:
            continue

        maintenance_overlap = _overlap_seconds(ping_start, next_ping_at, maintenance_intervals) if exclude_maintenance else 0
        effective_seconds = max(0, next_ping_at - ping_start - maintenance_overlap)
        observed_seconds += effective_seconds

        if ping.ping_type == "fail":
            downtime_seconds += effective_seconds
            current_incident.append({
                "ping": ping,
                "start_at": ping_start,
                "end_at": next_ping_at,
                "effective_seconds": effective_seconds,
            })
        elif current_incident:
            incidents.append(current_incident)
            current_incident = []

    if current_incident:
        incidents.append(current_incident)

    incident_responses = []
    for incident in incidents:
        duration_seconds = sum(entry["effective_seconds"] for entry in incident)
        if duration_seconds <= 0:
            continue
        dominant_code = Counter((entry["ping"].code or "unknown") for entry in incident).most_common(1)[0][0]
        incident_responses.append(CheckUptimeIncidentResponse(
            startedAt=get_iso_timestamp(incident[0]["start_at"]),
            endedAt=get_iso_timestamp(incident[-1]["end_at"]),
            durationSeconds=duration_seconds,
            failureCount=len(incident),
            dominantCode=dominant_code,
        ))

    uptime_pct = round(((observed_seconds - downtime_seconds) / observed_seconds) * 100, 2) if observed_seconds else 0.0

    return CheckUptimeResponse(
        **{"from": from_at, "to": to_at},
        excludeMaintenance=exclude_maintenance,
        uptimePct=uptime_pct,
        totalObservedMinutes=_round_minutes(observed_seconds),
        downtimeMinutes=_round_minutes(downtime_seconds),
        excludedMaintenanceMinutes=_round_minutes(excluded_seconds if exclude_maintenance else 0),
        incidents=incident_responses,
        maintenanceWindows=[_serialize_maintenance_window(window) for window in windows],
    )


def _check_detail_response(check) -> CheckDetailResponse:
    """Build a CheckDetailResponse from a Check entity."""
    return CheckDetailResponse(
        checkId=check.check_id,
        teamId=check.team_id,
        name=check.name,
        status=check.status,
        periodSeconds=check.period_seconds,
        schedule=check.schedule,
        graceSeconds=check.grace_seconds,
        token=check.token,
        lastPingAt=check.last_ping_at,
        nextDueAt=check.next_due_at,
        alertAfterAt=check.alert_after_at,
        lastAlertAt=check.last_alert_at,
        createdAt=check.created_at,
        alertChannels=check.alert_channels,
        escalationMinutes=check.escalation_minutes,
        escalationAlertChannels=getattr(check, 'escalation_alert_channels', []) or [],
        escalationTriggeredAt=getattr(check, 'escalation_triggered_at', None),
        suppressAfterCount=getattr(check, 'suppress_after_count', None),
        suppressDurationMinutes=getattr(check, 'suppress_duration_minutes', None),
        consecutiveAlertCount=getattr(check, 'consecutive_alert_count', 0),
        suppressedUntil=getattr(check, 'suppressed_until', None),
        type=check.type,
        url=getattr(check, 'url', None),
        expectedStatusCode=getattr(check, 'expected_status_code', 200),
        expectedString=getattr(check, 'expected_string', None),
        failureThreshold=getattr(check, 'failure_threshold', 1),
        tags=getattr(check, 'tags', []) or [],
    )


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

    # Auto-generate slug from name
    slug = generate_slug(request.name)

    # TODO: Ensure slug uniqueness per team (handle duplicates with -2, -3, etc)

    # Create check
    check = Check(
        check_id=check_id,
        team_id=team_id,
        name=request.name,
        token=token,
        slug=slug,
        period_seconds=request.period_seconds,
        schedule=request.schedule,
        grace_seconds=request.grace_seconds,
        status=CheckStatus.PENDING,  # New checks start as pending
        created_at=get_iso_timestamp(),
        alert_channels=request.alert_channels,
        type=request.type,
        url=request.url,
        expected_status_code=request.expected_status_code,
        expected_string=request.expected_string,
        failure_threshold=request.failure_threshold,
        tags=request.tags,
    )
    # Pre-compute next_due_at for cron checks so the late detector can find them immediately
    if request.type == "cron":
        check.next_due_at = str(calculate_next_due_from_cron(request.schedule))
        check.alert_after_at = str(int(check.next_due_at) + request.grace_seconds)

    await db.create_check(check)
    await record_audit(db, team_id, current_user, "check.created", "check", check_id, request.name)

    # Record metrics and log business event
    metrics = get_metrics_client()
    metrics.check_created(team_id)
    log_business_event('check_created', team_id=team_id, check_id=check_id, check_name=request.name, slug=slug)

    posthog = get_posthog_client()
    with new_context(client=posthog):
        identify_context(current_user.user_id)
        posthog.capture(
            distinct_id=current_user.user_id,
            event="check_created",
            properties={
                "team_id": team_id,
                "check_id": check_id,
                "check_type": request.type,
                "period_seconds": request.period_seconds,
                "grace_seconds": request.grace_seconds,
            },
        )

    return _check_detail_response(check)


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
            schedule=check.schedule,
            graceSeconds=check.grace_seconds,
            lastPingAt=check.last_ping_at,
            nextDueAt=check.next_due_at,
            createdAt=check.created_at,
            type=check.type,
            url=check.url,
            expectedStatusCode=check.expected_status_code,
            expectedString=getattr(check, 'expected_string', None),
            failureThreshold=getattr(check, 'failure_threshold', 1),
            tags=getattr(check, 'tags', []) or [],
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

    return _check_detail_response(check)


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
        # 0 disables escalation
        updates["escalationMinutes"] = request.escalation_minutes or None
    if request.escalation_alert_channels is not None:
        updates["escalationAlertChannels"] = request.escalation_alert_channels
    if request.tags is not None:
        updates["tags"] = request.tags
    if request.suppress_after_count is not None:
        updates["suppressAfterCount"] = request.suppress_after_count or None
    if request.suppress_duration_minutes is not None:
        updates["suppressDurationMinutes"] = request.suppress_duration_minutes or None
    if request.url is not None:
        updates["url"] = request.url
    if request.expected_status_code is not None:
        updates["expectedStatusCode"] = request.expected_status_code
    if request.expected_string is not None:
        updates["expectedString"] = request.expected_string
    if request.failure_threshold is not None:
        updates["failureThreshold"] = request.failure_threshold
    if request.schedule is not None:
        updates["schedule"] = request.schedule

    if not updates:
        return _check_detail_response(check)

    # Recalculate next_due/alert_after when schedule or period/grace changes
    grace = updates.get("graceSeconds", check.grace_seconds)
    if "schedule" in updates:
        next_due = calculate_next_due_from_cron(updates["schedule"])
        updates["nextDueAt"] = str(next_due)
        updates["alertAfterAt"] = str(next_due + grace)
    elif ("periodSeconds" in updates or "graceSeconds" in updates) and check.last_ping_at:
        period = updates.get("periodSeconds", check.period_seconds)
        from datetime import datetime
        last_ping_seconds = int(datetime.fromisoformat(check.last_ping_at.replace("Z", "+00:00")).timestamp())
        updates["alertAfterAt"] = calculate_alert_after(last_ping_seconds, period, grace)
        updates["nextDueAt"] = calculate_next_due(last_ping_seconds, period)

    updated_check = await db.update_check(team_id, check_id, updates)
    await record_audit(
        db, team_id, current_user, "check.updated", "check", check_id, check.name,
        detail="changed: " + ", ".join(sorted(updates.keys())),
    )
    return _check_detail_response(updated_check)


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
    await record_audit(db, team_id, current_user, "check.paused", "check", check_id, check.name)

    posthog = get_posthog_client()
    with new_context(client=posthog):
        identify_context(current_user.user_id)
        posthog.capture(
            distinct_id=current_user.user_id,
            event="check_paused",
            properties={"team_id": team_id, "check_id": check_id},
        )

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
    await record_audit(db, team_id, current_user, "check.resumed", "check", check_id, check.name)

    posthog = get_posthog_client()
    with new_context(client=posthog):
        identify_context(current_user.user_id)
        posthog.capture(
            distinct_id=current_user.user_id,
            event="check_resumed",
            properties={"team_id": team_id, "check_id": check_id},
        )

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
    await record_audit(db, team_id, current_user, "check.token_rotated", "check", check_id, check.name)

    return _check_detail_response(updated_check)


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

    # Enqueue escalated alerts (durable delivery with retries)
    try:
        from ..alert_dispatch import enqueue_check_alerts

        team = await db.get_team(team_id)
        await enqueue_check_alerts(
            db, check, "escalation",
            channel_ids=check.escalation_alert_channels, team=team,
        )

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
    await record_audit(db, team_id, current_user, "check.deleted", "check", check_id, check.name)

    # Record metrics and log business event
    metrics = get_metrics_client()
    metrics.check_deleted(team_id)
    log_business_event('check_deleted', team_id=team_id, check_id=check_id, check_name=check.name)

    posthog = get_posthog_client()
    with new_context(client=posthog):
        identify_context(current_user.user_id)
        posthog.capture(
            distinct_id=current_user.user_id,
            event="check_deleted",
            properties={
                "team_id": team_id,
                "check_id": check_id,
                "check_type": check.type,
            },
        )

    return OkResponse(message="Check deleted successfully")


@router.get("/{check_id}/pings", response_model=List[PingResponse])
async def list_check_pings(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
    limit: int = Query(default=50, ge=1, le=100),
    since: int = Query(default=None, description="Unix timestamp in milliseconds to filter pings from"),
    ping_type: Optional[str] = Query(default=None, alias="type", pattern="^(fail|success|start)$"),
) -> List[PingResponse]:
    """Get ping history for a check."""
    # Check team access (requires VIEW permission)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    # Verify check exists
    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    query_limit = 5000 if ping_type else limit
    pings = await db.list_check_pings(check_id, query_limit, since)
    if ping_type:
        pings = [ping for ping in pings if ping.ping_type == ping_type][:limit]

    return [_serialize_ping(ping) for ping in pings]


@router.get("/{check_id}/stats", response_model=CheckStatsResponse)
async def get_check_stats(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
    range: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
) -> CheckStatsResponse:
    """Get aggregated response-time statistics for an HTTP check."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")
    if check.type != CheckType.HTTP:
        raise ValidationError("Stats are only available for HTTP checks")

    current_time = get_current_time_seconds()
    since_seconds = current_time - STATS_RANGE_SECONDS[range]
    recent_pings = await db.list_check_pings(check_id, limit=5000, since=None)
    filtered_pings = [
        ping for ping in recent_pings
        if parse_iso_timestamp(ping.received_at) >= since_seconds
    ]

    return _build_check_stats_response(filtered_pings, range)


@router.get("/{check_id}/errors/summary", response_model=CheckErrorSummaryResponse)
async def get_check_error_summary(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
    range: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
) -> CheckErrorSummaryResponse:
    """Get aggregated failure summary for a check."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    current_time = get_current_time_seconds()
    since_seconds = current_time - STATS_RANGE_SECONDS[range]
    recent_pings = await db.list_check_pings(check_id, limit=5000, since=None)
    filtered_pings = [
        ping for ping in recent_pings
        if _ping_received_at_seconds(ping) >= since_seconds
    ]

    return _build_check_error_summary_response(filtered_pings, range)


@router.get("/{check_id}/uptime", response_model=CheckUptimeResponse)
async def get_check_uptime(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
    from_at: str = Query(alias="from"),
    to_at: str = Query(alias="to"),
    exclude_maintenance: bool = Query(default=True, alias="exclude_maintenance"),
) -> CheckUptimeResponse:
    """Get uptime summary for an arbitrary reporting window."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    if parse_iso_timestamp(to_at) <= parse_iso_timestamp(from_at):
        raise ValidationError("to must be after from")

    pings = await db.list_check_pings_between(check_id, from_at, to_at)
    windows = await db.list_maintenance_windows(team_id, check_id)

    return _build_check_uptime_response(check, pings, windows, from_at, to_at, exclude_maintenance)


@router.get("/{check_id}/alert-history", response_model=List[Dict[str, Any]])
async def get_check_alert_history(
    team_id: str,
    check_id: str,
    current_user: AuthUser,
    db: Database,
    limit: int = Query(default=50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """List alert delivery history for a check, newest first."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    check = await db.get_check(team_id, check_id)
    if not check:
        raise NotFoundError("Check not found")

    deliveries = await db.list_alert_deliveries(team_id, check_id=check_id, limit=limit)
    return [
        {
            "deliveryId": d.delivery_id,
            "checkId": d.check_id,
            "checkName": d.check_name,
            "channelId": d.channel_id,
            "channelType": d.channel_type,
            "channelName": d.channel_name,
            "alertType": d.alert_type,
            "status": d.status,
            "attempts": d.attempts,
            "maxAttempts": d.max_attempts,
            "lastError": d.last_error,
            "createdAt": d.created_at,
            "deliveredAt": d.delivered_at,
        }
        for d in deliveries
    ]
