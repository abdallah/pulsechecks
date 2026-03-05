"""Alert topic management endpoints."""
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
import boto3
from botocore.exceptions import ClientError

from ..dependencies import AuthUser, Database, check_team_access
from ..models import (
    CreateAlertTopicRequest,
    AlertTopicResponse,
    OkResponse,
    Permission,
)
from ..config import get_settings

router = APIRouter(prefix="/teams/{team_id}/alerts", tags=["alerts"])


def _get_sns_client():
    """Get SNS client."""
    settings = get_settings()
    return boto3.client("sns", region_name=settings.aws_region)


def _get_topic_name_for_team(team_id: str, topic_name: str, shared: bool = False) -> str:
    """Generate SNS topic name for a team."""
    settings = get_settings()
    clean_name = topic_name.replace(" ", "-").replace("_", "-").lower()
    
    if shared:
        # Shared topics don't include team ID
        return f"{settings.project_name}-shared-{clean_name}"
    else:
        # Team-specific topics include team ID
        return f"{settings.project_name}-{team_id[:8]}-{clean_name}"


@router.post("", response_model=AlertTopicResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_topic(
    team_id: str,
    request: CreateAlertTopicRequest,
    current_user: AuthUser,
    db: Database,
) -> AlertTopicResponse:
    """Create a new SNS alert topic for a team."""
    # Check team access (requires EDIT permission)
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    sns = _get_sns_client()
    topic_name = _get_topic_name_for_team(team_id, request.name, getattr(request, 'shared', False))

    try:
        # Create SNS topic
        response = sns.create_topic(Name=topic_name)
        topic_arn = response["TopicArn"]

        # Set display name if provided
        if request.display_name:
            sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName="DisplayName",
                AttributeValue=request.display_name,
            )

        # Add tags for team association
        tags = [
            {"Key": "ManagedBy", "Value": "PulseChecks"},
        ]
        
        if getattr(request, 'shared', False):
            tags.append({"Key": "Type", "Value": "Shared"})
            tags.append({"Key": "CreatedByTeam", "Value": team_id})
        else:
            tags.append({"Key": "Team", "Value": team_id})
            
        sns.tag_resource(ResourceArn=topic_arn, Tags=tags)

        return AlertTopicResponse(
            topic_arn=topic_arn,
            topic_name=topic_name,
            display_name=request.display_name,
        )

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create SNS topic: {str(e)}",
        )


@router.get("", response_model=List[AlertTopicResponse])
async def list_alert_topics(
    team_id: str,
    current_user: AuthUser,
    db: Database,
) -> List[AlertTopicResponse]:
    """List all SNS alert topics for a team."""
    # Check team access (requires VIEW permission)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    try:
        sns = _get_sns_client()
        settings = get_settings()
        team_prefix = f"{settings.project_name}-{team_id[:8]}-"
        shared_prefix = f"{settings.project_name}-shared-"

        topics = []
        paginator = sns.get_paginator("list_topics")

        for page in paginator.paginate():
            for topic in page.get("Topics", []):
                topic_arn = topic["TopicArn"]
                topic_name = topic_arn.split(":")[-1]

                # Include team-specific topics and shared topics
                if topic_name.startswith(team_prefix) or topic_name.startswith(shared_prefix):
                    try:
                        # Get display name
                        attrs = sns.get_topic_attributes(TopicArn=topic_arn)
                        display_name = attrs.get("Attributes", {}).get("DisplayName")
                        
                        # Determine if shared
                        is_shared = topic_name.startswith(shared_prefix)
                        
                        topics.append(AlertTopicResponse(
                            topicArn=topic_arn,
                            topicName=topic_name,
                            displayName=display_name or topic_name,
                            shared=is_shared,
                        ))
                    except ClientError as e:
                        # Skip topics we can't access
                        print(f"Warning: Could not access topic {topic_arn}: {e}")
                        continue

        return topics

    except ClientError as e:
        print(f"Error listing SNS topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert topics: {str(e)}"
        )
    except Exception as e:
        print(f"Unexpected error listing alert topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list alert topics"
        )


@router.get("/{topic_arn:path}/details")
async def get_alert_topic_details(
    team_id: str,
    topic_arn: str,
    current_user: AuthUser,
    db: Database,
):
    """Get detailed information about an alert topic including subscriptions."""
    # Check team access (requires VIEW permission)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    sns = _get_sns_client()

    try:
        # Get topic attributes
        attrs_response = sns.get_topic_attributes(TopicArn=topic_arn)
        attributes = attrs_response.get("Attributes", {})
        
        # Get subscriptions
        subscriptions = []
        paginator = sns.get_paginator("list_subscriptions_by_topic")
        for page in paginator.paginate(TopicArn=topic_arn):
            for sub in page.get("Subscriptions", []):
                subscriptions.append({
                    "subscriptionArn": sub["SubscriptionArn"],
                    "protocol": sub["Protocol"],
                    "endpoint": sub["Endpoint"],
                    "confirmationWasAuthenticated": sub.get("ConfirmationWasAuthenticated", False),
                })
        
        # Get tags
        tags_response = sns.list_tags_for_resource(ResourceArn=topic_arn)
        tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("Tags", [])}
        
        return {
            "topicArn": topic_arn,
            "topicName": topic_arn.split(":")[-1],
            "displayName": attributes.get("DisplayName"),
            "subscriptionsConfirmed": attributes.get("SubscriptionsConfirmed", "0"),
            "subscriptionsPending": attributes.get("SubscriptionsPending", "0"),
            "subscriptionsDeleted": attributes.get("SubscriptionsDeleted", "0"),
            "deliveryPolicy": attributes.get("DeliveryPolicy"),
            "effectiveDeliveryPolicy": attributes.get("EffectiveDeliveryPolicy"),
            "subscriptions": subscriptions,
            "tags": tags,
            "shared": tags.get("Type") == "Shared",
        }

    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFound":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topic details: {str(e)}",
        )


@router.post("/{topic_arn:path}/subscribe")
async def subscribe_to_alert_topic(
    team_id: str,
    topic_arn: str,
    request: dict,  # {"protocol": "email", "endpoint": "user@example.com"}
    current_user: AuthUser,
    db: Database,
):
    """Subscribe to an alert topic."""
    # Check team access (requires VIEW permission to subscribe)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    protocol = request.get("protocol")
    endpoint = request.get("endpoint")
    
    if not protocol or not endpoint:
        raise HTTPException(status_code=400, detail="Protocol and endpoint are required")
    
    # Validate protocol
    valid_protocols = ["email", "sms", "http", "https", "sqs", "lambda"]
    if protocol not in valid_protocols:
        raise HTTPException(status_code=400, detail=f"Invalid protocol. Must be one of: {valid_protocols}")

    sns = _get_sns_client()

    try:
        response = sns.subscribe(
            TopicArn=topic_arn,
            Protocol=protocol,
            Endpoint=endpoint,
        )
        
        return {
            "subscriptionArn": response["SubscriptionArn"],
            "message": f"Subscription created. Check {endpoint} for confirmation if required."
        }

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}",
        )


@router.delete("/{topic_arn:path}/unsubscribe")
async def unsubscribe_from_alert_topic(
    team_id: str,
    topic_arn: str,
    request: dict,  # {"subscription_arn": "arn:aws:sns:..."}
    current_user: AuthUser,
    db: Database,
):
    """Unsubscribe from an alert topic."""
    # Check team access (requires VIEW permission to unsubscribe)
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    sns = _get_sns_client()

    try:
        # Verify topic belongs to this team by checking tags
        tags_response = sns.list_tags_for_resource(ResourceArn=topic_arn)
        tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("Tags", [])}

        if tags.get("Team") != team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Topic does not belong to this team",
            )

        subscription_arn = request.get("subscription_arn")
        if not subscription_arn:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="subscription_arn is required",
            )

        # Unsubscribe
        sns.unsubscribe(SubscriptionArn=subscription_arn)
        
        return {"message": "Unsubscribed successfully"}

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unsubscribe: {str(e)}",
        )


@router.delete("/{topic_arn:path}", response_model=OkResponse)
async def delete_alert_topic(
    team_id: str,
    topic_arn: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Delete an SNS alert topic."""
    # Check team access (requires EDIT permission)
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    sns = _get_sns_client()

    try:
        # Verify topic belongs to this team by checking tags
        tags_response = sns.list_tags_for_resource(ResourceArn=topic_arn)
        tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("Tags", [])}

        if tags.get("Team") != team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Topic does not belong to this team",
            )

        # Delete the topic
        sns.delete_topic(TopicArn=topic_arn)

        return OkResponse(message="Alert topic deleted")

    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFound":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete SNS topic: {str(e)}",
        )
