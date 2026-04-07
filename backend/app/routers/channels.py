"""Alert channel management endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
import uuid
import boto3
from botocore.exceptions import ClientError

from ..dependencies import get_current_user, get_db, check_team_access, AuthUser, Database
from ..models import AlertChannel, AlertChannelType, Permission
from ..utils import get_iso_timestamp
from ..config import get_settings
from ..ssrf_utils import validate_webhook_url_strict, SSRFValidationError
from ..posthog_client import get_posthog_client, new_context, identify_context

router = APIRouter(prefix="/teams/{team_id}/channels", tags=["alert-channels"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_alert_channels(
    team_id: str,
    current_user: AuthUser,
    db: Database,
) -> List[Dict[str, Any]]:
    """List all alert channels for a team."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    
    channels = await db.list_alert_channels(team_id)
    
    # Convert to dict format for API response
    result = []
    for channel in channels:
        result.append({
            "channelId": channel.channel_id,
            "teamId": channel.team_id,
            "name": channel.name,
            "displayName": channel.display_name,
            "type": channel.type.value,
            "configuration": channel.configuration,
            "shared": channel.shared,
            "createdAt": channel.created_at,
            "createdBy": channel.created_by,
        })
    
    return result


@router.post("", response_model=Dict[str, Any])
async def create_alert_channel(
    team_id: str,
    request: Dict[str, Any],  # {"name": "...", "displayName": "...", "type": "sns", "configuration": {...}}
    current_user: AuthUser,
    db: Database,
) -> Dict[str, Any]:
    """Create a new alert channel."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)
    
    # Validate required fields
    name = request.get("name")
    display_name = request.get("displayName")
    channel_type = request.get("type")
    configuration = request.get("configuration", {})
    shared = request.get("shared", False)
    
    if not name or not display_name or not channel_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name, displayName, and type are required"
        )
    
    try:
        alert_type = AlertChannelType(channel_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel type. Must be one of: {[t.value for t in AlertChannelType]}"
        )
    
    # Validate configuration based on type
    _validate_channel_configuration(alert_type, configuration)
    
    # Auto-create SNS topic if needed
    if alert_type == AlertChannelType.SNS:
        topic_arn = await _create_sns_topic_for_channel(team_id, name, display_name, shared)
        configuration["topic_arn"] = topic_arn
    
    # Create channel
    channel_id = str(uuid.uuid4())
    channel = AlertChannel(
        channel_id=channel_id,
        team_id=team_id,
        name=name,
        display_name=display_name,
        type=alert_type,
        configuration=configuration,
        shared=shared,
        created_at=get_iso_timestamp(),
        created_by=current_user.user_id,
    )
    
    await db.create_alert_channel(channel)

    posthog = get_posthog_client()
    with new_context(client=posthog):
        identify_context(current_user.user_id)
        posthog.capture(
            distinct_id=current_user.user_id,
            event="alert_channel_created",
            properties={
                "team_id": team_id,
                "channel_type": alert_type.value,
                "shared": shared,
            },
        )

    return {
        "channelId": channel.channel_id,
        "teamId": channel.team_id,
        "name": channel.name,
        "displayName": channel.display_name,
        "type": channel.type.value,
        "configuration": channel.configuration,
        "shared": channel.shared,
        "createdAt": channel.created_at,
        "createdBy": channel.created_by,
    }


@router.get("/{channel_id}", response_model=Dict[str, Any])
async def get_alert_channel(
    team_id: str,
    channel_id: str,
    current_user: AuthUser,
    db: Database,
) -> Dict[str, Any]:
    """Get a specific alert channel."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    
    channel = await db.get_alert_channel(team_id, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert channel not found"
        )
    
    return {
        "channelId": channel.channel_id,
        "teamId": channel.team_id,
        "name": channel.name,
        "displayName": channel.display_name,
        "type": channel.type.value,
        "configuration": channel.configuration,
        "shared": channel.shared,
        "createdAt": channel.created_at,
        "createdBy": channel.created_by,
    }


@router.patch("/{channel_id}", response_model=Dict[str, Any])
async def update_alert_channel(
    team_id: str,
    channel_id: str,
    request: Dict[str, Any],  # {"displayName": "...", "configuration": {...}, "shared": bool}
    current_user: AuthUser,
    db: Database,
) -> Dict[str, Any]:
    """Update an alert channel."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)
    
    channel = await db.get_alert_channel(team_id, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert channel not found"
        )
    
    # Update fields if provided
    if "displayName" in request:
        channel.display_name = request["displayName"]
    if "configuration" in request:
        _validate_channel_configuration(channel.type, request["configuration"])
        channel.configuration = request["configuration"]
    if "shared" in request:
        channel.shared = request["shared"]
    
    await db.update_alert_channel(channel)
    
    return {
        "channelId": channel.channel_id,
        "teamId": channel.team_id,
        "name": channel.name,
        "displayName": channel.display_name,
        "type": channel.type.value,
        "configuration": channel.configuration,
        "shared": channel.shared,
        "createdAt": channel.created_at,
        "createdBy": channel.created_by,
    }


@router.delete("/{channel_id}")
async def delete_alert_channel(
    team_id: str,
    channel_id: str,
    current_user: AuthUser,
    db: Database,
) -> Dict[str, str]:
    """Delete an alert channel."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)
    
    channel = await db.get_alert_channel(team_id, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert channel not found"
        )
    
    # Delete associated SNS topic if it's an SNS channel
    if channel.type == AlertChannelType.SNS and "topic_arn" in channel.configuration:
        try:
            sns = _get_sns_client()
            topic_arn = channel.configuration["topic_arn"]
            sns.delete_topic(TopicArn=topic_arn)
        except ClientError as e:
            # Log but don't fail if topic deletion fails
            print(f"Warning: Failed to delete SNS topic {topic_arn}: {e}")
    
    await db.delete_alert_channel(team_id, channel_id)

    posthog = get_posthog_client()
    with new_context(client=posthog):
        identify_context(current_user.user_id)
        posthog.capture(
            distinct_id=current_user.user_id,
            event="alert_channel_deleted",
            properties={
                "team_id": team_id,
                "channel_type": channel.type.value,
                "shared": channel.shared,
            },
        )

    return {"message": "Alert channel deleted successfully"}


@router.post("/{channel_id}/test")
async def test_alert_channel(
    team_id: str,
    channel_id: str,
    current_user: AuthUser,
    db: Database,
) -> Dict[str, str]:
    """Send a test notification through an alert channel."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    channel = await db.get_alert_channel(team_id, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert channel not found"
        )

    try:
        await _send_test_notification(channel, team_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Test notification failed: {str(e)}"
        )

    return {"message": "Test notification sent successfully"}


async def _send_test_notification(channel: "AlertChannel", team_id: str) -> None:
    """Send a test notification through the given channel."""
    import json
    import httpx
    from ..integrations.mattermost import create_mattermost_client
    from ..utils import get_iso_timestamp

    if channel.type == AlertChannelType.SNS:
        topic_arn = channel.configuration.get("topic_arn")
        if not topic_arn:
            raise ValueError("SNS topic ARN not configured")
        sns = _get_sns_client()
        sns.publish(
            TopicArn=topic_arn,
            Subject="🔔 PulseChecks Test Notification",
            Message=json.dumps({
                "event": "test",
                "channelName": channel.display_name,
                "teamId": team_id,
                "timestamp": get_iso_timestamp(),
            }, indent=2),
        )

    elif channel.type == AlertChannelType.MATTERMOST:
        webhook_url = channel.configuration.get("webhook_url")
        if not webhook_url:
            raise ValueError("Webhook URL not configured")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json={
                "text": f"🔔 **PulseChecks Test** — channel *{channel.display_name}* is working!"
            })
            if resp.status_code >= 400:
                raise ValueError(f"Mattermost returned HTTP {resp.status_code}")

    elif channel.type == AlertChannelType.WEBHOOK:
        webhook_url = channel.configuration.get("webhook_url")
        if not webhook_url:
            raise ValueError("Webhook URL not configured")
        headers = channel.configuration.get("headers") or {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json={
                "event": "test",
                "channelName": channel.display_name,
                "teamId": team_id,
                "timestamp": get_iso_timestamp(),
            }, headers=headers)
            if resp.status_code >= 400:
                raise ValueError(f"Webhook returned HTTP {resp.status_code}")

    elif channel.type == AlertChannelType.TELEGRAM:
        bot_token = channel.configuration.get("bot_token")
        chat_id = channel.configuration.get("chat_id")
        if not bot_token or not chat_id:
            raise ValueError("Telegram bot_token and chat_id required")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": f"🔔 PulseChecks Test — channel {channel.display_name} is working!"},
            )
            if resp.status_code >= 400:
                raise ValueError(f"Telegram returned HTTP {resp.status_code}")

    else:
        raise ValueError(f"Unsupported channel type: {channel.type.value}")


def _validate_channel_configuration(channel_type: AlertChannelType, config: Dict[str, Any]) -> None:
    """Validate channel configuration based on type."""
    if channel_type == AlertChannelType.SNS:
        # SNS channels will have topic_arn auto-created, no validation needed
        pass
    elif channel_type in [AlertChannelType.MATTERMOST, AlertChannelType.WEBHOOK]:
        if "webhook_url" not in config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{channel_type.value.title()} channels require 'webhook_url' in configuration"
            )
        webhook_url = config["webhook_url"]
        if not webhook_url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{channel_type.value.title()} webhook_url must start with http:// or https://"
            )
        # Validate webhook URL against SSRF attacks
        try:
            validate_webhook_url_strict(webhook_url)
        except SSRFValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    elif channel_type == AlertChannelType.TELEGRAM:
        if "bot_token" not in config or "chat_id" not in config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram channels require 'bot_token' and 'chat_id' in configuration"
            )


def _get_sns_client():
    """Get SNS client."""
    settings = get_settings()
    return boto3.client("sns", region_name=settings.aws_region)


def _get_topic_name_for_channel(team_id: str, channel_name: str, shared: bool = False) -> str:
    """Generate SNS topic name for a channel."""
    settings = get_settings()
    clean_name = channel_name.replace(" ", "-").replace("_", "-").lower()
    
    if shared:
        return f"{settings.project_name}-shared-{clean_name}"
    else:
        return f"{settings.project_name}-{team_id[:8]}-{clean_name}"


async def _create_sns_topic_for_channel(team_id: str, channel_name: str, display_name: str, shared: bool = False) -> str:
    """Create SNS topic for a channel and return the topic ARN."""
    sns = _get_sns_client()
    topic_name = _get_topic_name_for_channel(team_id, channel_name, shared)

    try:
        # Create SNS topic
        response = sns.create_topic(Name=topic_name)
        topic_arn = response["TopicArn"]

        # Set display name
        sns.set_topic_attributes(
            TopicArn=topic_arn,
            AttributeName="DisplayName",
            AttributeValue=display_name,
        )

        # Add tags for team association
        tags = [
            {"Key": "ManagedBy", "Value": "PulseChecks"},
            {"Key": "Type", "Value": "AlertChannel"},
        ]
        
        if shared:
            tags.append({"Key": "Shared", "Value": "true"})
            tags.append({"Key": "CreatedByTeam", "Value": team_id})
        else:
            tags.append({"Key": "Team", "Value": team_id})
            
        sns.tag_resource(ResourceArn=topic_arn, Tags=tags)

        return topic_arn

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create SNS topic: {str(e)}",
        )
