"""Standalone Lambda handlers for background jobs."""
import asyncio
import json
from typing import Dict, Any
import boto3
import httpx
from botocore.exceptions import ClientError

from .db import create_db_client
from .utils import get_current_time_seconds, get_iso_timestamp
from .config import get_settings
from .logging_config import get_logger, log_business_event
from .metrics import get_metrics_client
from .integrations.mattermost import create_mattermost_client

logger = get_logger(__name__)


async def _late_detector_impl(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Enhanced late detection Lambda handler with escalation and suppression.

    Queries checks that are past their alert time and sends alerts via SNS and Mattermost.
    Handles escalation chains and alert suppression rules.
    """
    db = create_db_client()
    settings = get_settings()
    metrics = get_metrics_client()

    current_time = get_current_time_seconds()

    # Query checks that are due
    due_checks = await db.query_due_checks(current_time, limit=100)

    alerts_queued = 0
    mattermost_alerts_sent = 0
    escalations_triggered = 0
    alerts_suppressed = 0
    
    # Initialize SNS client once if we have checks to process
    sns_client = None
    if due_checks:
        sns_client = boto3.client("sns", region_name=settings.aws_region)

    for check in due_checks:
        # Check if alerts are currently suppressed
        if _is_suppressed(check, current_time):
            alerts_suppressed += 1
            logger.info(f"Alerts suppressed for check {check.check_id} until {check.suppressed_until}")
            continue

        # Update check to late status (conditional - only if not already late/paused)
        went_late = await db.update_check_to_late(
            check.team_id, check.check_id, get_iso_timestamp()
        )

        if went_late:
            # Increment consecutive alert count
            await db.increment_consecutive_alerts(check.team_id, check.check_id)
            check.consecutive_alert_count += 1

            # Check if we should suppress future alerts
            if _should_suppress(check):
                suppress_until = current_time + (check.suppress_duration_minutes * 60)
                await db.suppress_check_alerts(check.team_id, check.check_id, get_iso_timestamp(suppress_until))
                logger.info(f"Suppressing alerts for check {check.check_id} after {check.consecutive_alert_count} consecutive alerts")

            # Get team info for Mattermost integration
            team = await db.get_team(check.team_id)
            
            # Send primary alerts (Mattermost + SNS)
            sns_sent, mattermost_sent = await _send_primary_alerts(check, team, sns_client, metrics)
            alerts_queued += sns_sent
            mattermost_alerts_sent += mattermost_sent

        # Check for escalation (even if check was already late)
        if _should_escalate(check, current_time):
            # Trigger escalation
            await db.mark_escalation_triggered(check.team_id, check.check_id, get_iso_timestamp())
            
            # Get team info
            team = await db.get_team(check.team_id)
            
            # Send escalated alerts
            await _send_escalated_alerts(check, team, sns_client, metrics)
            escalations_triggered += 1

    # Record enhanced metrics
    metrics.late_detection_run(len(due_checks), alerts_queued + mattermost_alerts_sent)
    log_business_event('enhanced_late_detection_run', 
        checks_processed=len(due_checks), 
        sns_alerts_queued=alerts_queued,
        mattermost_alerts_sent=mattermost_alerts_sent,
        escalations_triggered=escalations_triggered,
        alerts_suppressed=alerts_suppressed
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "checksProcessed": len(due_checks),
                "channelAlertsQueued": alerts_queued,
                "channelAlertsSent": mattermost_alerts_sent,
                "escalationsTriggered": escalations_triggered,
                "alertsSuppressed": alerts_suppressed,
            }
        ),
    }


def late_detector_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Late detection Lambda handler (EventBridge triggered).
    """
    return asyncio.run(_late_detector_impl(event, context))


def _is_suppressed(check, current_time: int) -> bool:
    """Check if alerts are currently suppressed for this check."""
    if not check.suppressed_until:
        return False
    
    # Parse suppressed_until timestamp and compare
    from .utils import parse_iso_timestamp
    suppressed_until_seconds = parse_iso_timestamp(check.suppressed_until)
    return current_time < suppressed_until_seconds


def _should_suppress(check) -> bool:
    """Check if we should start suppressing alerts for this check."""
    return (
        check.suppress_after_count and 
        check.suppress_duration_minutes and
        check.consecutive_alert_count >= check.suppress_after_count
    )


def _should_escalate(check, current_time: int) -> bool:
    """Check if we should escalate alerts for this check."""
    if not check.escalation_minutes or not check.escalation_alert_channels:
        return False
    
    if check.escalation_triggered_at:
        return False  # Already escalated
    
    if not check.last_alert_at:
        return False  # No initial alert sent yet
    
    # Check if enough time has passed since the initial alert
    from .utils import parse_iso_timestamp
    last_alert_seconds = parse_iso_timestamp(check.last_alert_at)
    escalation_time = last_alert_seconds + (check.escalation_minutes * 60)
    
    return current_time >= escalation_time


async def _send_primary_alerts(check, team, sns_client, metrics):
    """Send primary alerts (Mattermost + SNS + AlertChannels). Returns (sns_sent, mattermost_sent)."""
    sns_sent = 0
    mattermost_sent = 0
    
    # Legacy Mattermost webhooks removed - use AlertChannels only

    # Send new AlertChannel alerts
    if check.alert_channels:
        db = create_db_client()
        for channel_id in check.alert_channels:
            try:
                channel = await db.get_alert_channel(check.team_id, channel_id)
                if not channel:
                    logger.warning(f"Alert channel {channel_id} not found for check {check.check_id}")
                    continue
                
                success = await _send_channel_alert(channel, check, team, sns_client, metrics)
                if success:
                    logger.info(f"Alert sent via channel {channel.name} ({channel.type.value}) for check {check.check_id}")
                
            except Exception as e:
                logger.error(f"Failed to send alert via channel {channel_id} for check {check.check_id}: {e}")
    
    return sns_sent, mattermost_sent


async def _send_channel_alert(channel, check, team, sns_client, metrics, alert_type="late"):
    """Send alert via a specific AlertChannel. Returns success boolean."""
    from .models import AlertChannelType
    
    try:
        if channel.type == AlertChannelType.SNS:
            topic_arn = channel.configuration.get('topic_arn')
            if not topic_arn or not sns_client:
                return False
                
            message = {
                "checkId": check.check_id,
                "checkName": check.name,
                "teamId": check.team_id,
                "status": "late",
                "timestamp": get_iso_timestamp(),
                "channelName": channel.display_name,
            }

            sns_client.publish(
                TopicArn=topic_arn,
                Subject=f"⚠️ Check Late: {check.name}",
                Message=json.dumps(message, indent=2),
            )
            
            metrics.alert_sent(check.team_id, check.check_id, f'late_channel_{channel.type.value}', True)
            return True
            
        elif channel.type == AlertChannelType.MATTERMOST:
            webhook_url = channel.configuration.get('webhook_url')
            if not webhook_url:
                return False
                
            mattermost = create_mattermost_client(webhook_url)
            if alert_type == "recovery":
                success = await mattermost.send_recovery_alert(check, team.name)
            else:
                success = await mattermost.send_late_alert(check, team.name)
            
            metrics.alert_sent(check.team_id, check.check_id, f'late_channel_{channel.type.value}', success)
            return success

        elif channel.type == AlertChannelType.WEBHOOK:
            webhook_url = channel.configuration.get('webhook_url')
            if not webhook_url:
                return False

            payload = {
                "event": alert_type,
                "check": {
                    "id": check.check_id,
                    "name": check.name,
                    "teamId": check.team_id,
                    "status": check.status.value,
                },
                "team": {
                    "id": team.team_id,
                    "name": team.name,
                },
                "timestamp": get_iso_timestamp(),
                "channelName": channel.display_name,
            }

            headers = channel.configuration.get('headers') or {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload, headers=headers)
                success = 200 <= response.status_code < 300

            metrics.alert_sent(check.team_id, check.check_id, f'late_channel_{channel.type.value}', success)
            return success
            
        elif channel.type == AlertChannelType.TELEGRAM:
            # TODO: Implement Telegram integration
            logger.info(f"Telegram alerts not yet implemented for channel {channel.name}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send alert via {channel.type.value} channel {channel.name}: {e}")
        metrics.alert_sent(check.team_id, check.check_id, f'late_channel_{channel.type.value}', False)
        return False
    
    return False


async def _send_escalated_alerts(check, team, sns_client, metrics):
    """Send escalated alerts via AlertChannels only."""
    # Send escalated alerts via modern AlertChannels
    if check.escalation_alert_channels:
        db = create_db_client()
        for channel_id in check.escalation_alert_channels:
            try:
                channel = await db.get_alert_channel(check.team_id, channel_id)
                if not channel:
                    logger.warning(f"Escalation alert channel {channel_id} not found for check {check.check_id}")
                    continue
                
                success = await _send_channel_alert(channel, check, team, sns_client, metrics)
                if success:
                    logger.info(f"Escalation alert sent via channel {channel.name} ({channel.type.value}) for check {check.check_id}")
                
            except Exception as e:
                logger.error(f"Failed to send escalation alert via channel {channel_id} for check {check.check_id}: {e}")


def late_detector_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Late detection Lambda handler (EventBridge triggered).
    Wrapper to run async implementation in event loop.
    """
    return asyncio.run(_late_detector_impl(event, context))


# Export handlers
__all__ = ["late_detector_handler"]
