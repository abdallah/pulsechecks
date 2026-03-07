"""Async DynamoDB client using aioboto3."""
import aioboto3
import time
from typing import Optional, List, Dict, Any
from botocore.exceptions import ClientError
from contextlib import asynccontextmanager

from ..config import get_settings
from ..models import User, Team, TeamMember, Check, Ping, Role, CheckStatus, PendingInvitation, AlertChannel, AlertChannelType
from ..errors import PulsechecksError
from ..utils import get_iso_timestamp, get_current_time_seconds
from ..utils.retry import with_retry, RetryConfig
from ..logging_config import get_logger
from .interface import DatabaseInterface

logger = get_logger(__name__)


class DynamoDBClient(DatabaseInterface):
    """Async DynamoDB client for Pulsechecks single-table design."""

    def __init__(self, table_name: Optional[str] = None):
        settings = get_settings()
        self.table_name = table_name or settings.dynamodb_table
        self.session = aioboto3.Session()

    @asynccontextmanager
    async def _get_table(self):
        """Get DynamoDB table resource."""
        async with self.session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(self.table_name)
            yield table

    # User operations
    async def create_user(self, user: User) -> None:
        """Create a new user profile."""
        async with self._get_table() as table:
            await table.put_item(
                Item={
                    "PK": f"USER#{user.user_id}",
                    "SK": "PROFILE",
                    "userId": user.user_id,
                    "email": user.email,
                    "name": user.name,
                    "createdAt": user.created_at,
                    "lastLoginAt": user.last_login_at,
                }
            )

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user profile."""
        async with self._get_table() as table:
            response = await table.get_item(Key={"PK": f"USER#{user_id}", "SK": "PROFILE"})
            item = response.get("Item")
            if not item:
                return None
            return User(
                user_id=item["userId"],
                email=item["email"],
                name=item["name"],
                created_at=item["createdAt"],
                last_login_at=item.get("lastLoginAt"),
            )

    async def update_user_login(self, user_id: str, name: str) -> None:
        """Update user's last login time and name."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
                UpdateExpression="SET lastLoginAt = :login, #n = :name",
                ExpressionAttributeNames={"#n": "name"},
                ExpressionAttributeValues={
                    ":login": get_iso_timestamp(),
                    ":name": name,
                },
            )

    # Team operations
    async def create_team(self, team: Team) -> None:
        """Create a new team."""
        async with self._get_table() as table:
            await table.put_item(
                Item={
                    "PK": f"TEAM#{team.team_id}",
                    "SK": "METADATA",
                    "teamId": team.team_id,
                    "name": team.name,
                    "createdAt": team.created_at,
                    "createdBy": team.created_by,
                }
            )

    async def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        async with self._get_table() as table:
            response = await table.get_item(
                Key={"PK": f"TEAM#{team_id}", "SK": "METADATA"}
            )
            item = response.get("Item")
            if not item:
                return None
            return Team(
                team_id=item["teamId"],
                name=item["name"],
                created_at=item["createdAt"],
                created_by=item["createdBy"],
                mattermost_webhook_url=item.get("mattermostWebhookUrl"),
                mattermost_webhooks=item.get("mattermostWebhooks", []),
            )

    async def update_team(self, team: Team) -> None:
        """Update a team."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{team.team_id}", "SK": "METADATA"},
                UpdateExpression="SET #name = :name",
                ExpressionAttributeNames={"#name": "name"},
                ExpressionAttributeValues={":name": team.name}
            )

    async def list_user_teams(self, user_id: str) -> List[Dict[str, Any]]:
        """List all teams for a user with their role."""
        # Get all memberships for user (uses scan for MVP - optimize with GSI in production)
        memberships = await self._list_user_memberships(user_id)

        teams = []
        for membership in memberships:
            team = await self.get_team(membership["teamId"])
            if team:
                teams.append({
                    "team": team,
                    "role": membership["role"],
                })
        return teams

    async def _list_user_memberships(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all memberships for a user (scan-based for MVP)."""
        async with self._get_table() as table:
            # Use scan with filter for MVP - in production, add GSI3 for user->team lookups
            response = await table.scan(
                FilterExpression="begins_with(SK, :sk_prefix) AND userId = :user_id",
                ExpressionAttributeValues={
                    ":sk_prefix": "MEMBER#",
                    ":user_id": user_id,
                },
            )
            return response.get("Items", [])

    # Membership operations
    async def add_team_member(self, member: TeamMember) -> None:
        """Add a member to a team."""
        async with self._get_table() as table:
            await table.put_item(
                Item={
                    "PK": f"TEAM#{member.team_id}",
                    "SK": f"MEMBER#{member.user_id}",
                    "teamId": member.team_id,
                    "userId": member.user_id,
                    "role": member.role.value,
                    "joinedAt": member.joined_at,
                }
            )

    async def get_team_member(self, team_id: str, user_id: str) -> Optional[TeamMember]:
        """Get a team member."""
        async with self._get_table() as table:
            response = await table.get_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"MEMBER#{user_id}"}
            )
            item = response.get("Item")
            if not item:
                return None
            return TeamMember(
                team_id=item["teamId"],
                user_id=item["userId"],
                role=Role(item["role"]),
                joined_at=item["joinedAt"],
            )

    async def list_team_members(self, team_id: str) -> List[TeamMember]:
        """List all members of a team."""
        async with self._get_table() as table:
            response = await table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"TEAM#{team_id}",
                    ":sk_prefix": "MEMBER#",
                },
            )
            items = response.get("Items", [])
            return [
                TeamMember(
                    team_id=item["teamId"],
                    user_id=item["userId"],
                    role=Role(item["role"]),
                    joined_at=item["joinedAt"],
                )
                for item in items
            ]

    # Check operations
    async def create_check(self, check: Check) -> None:
        """Create a new check."""
        async with self._get_table() as table:
            item = {
                "PK": f"TEAM#{check.team_id}",
                "SK": f"CHECK#{check.check_id}",
                "checkId": check.check_id,
                "teamId": check.team_id,
                "name": check.name,
                "token": check.token,
                "periodSeconds": check.period_seconds,
                "graceSeconds": check.grace_seconds,
                "status": check.status.value,
                "createdAt": check.created_at,
            }

            # Add optional fields
            if check.last_ping_at:
                item["lastPingAt"] = check.last_ping_at
            if check.next_due_at:
                item["nextDueAt"] = check.next_due_at
            if check.alert_after_at:
                item["alertAfterAt"] = check.alert_after_at
                # Add to due index
                item["GSI1PK"] = "DUE"
                item["GSI1SK"] = check.alert_after_at
            if check.last_alert_at:
                item["lastAlertAt"] = check.last_alert_at
            if check.alert_channels:
                item["alertChannels"] = check.alert_channels

            # Add to token index
            item["GSI2PK"] = f"TOKEN#{check.token}"
            item["GSI2SK"] = "CHECK"

            await table.put_item(Item=item)

    async def get_check(self, team_id: str, check_id: str) -> Optional[Check]:
        """Get check by ID."""
        async with self._get_table() as table:
            response = await table.get_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"}
            )
            item = response.get("Item")
            if not item:
                return None
            return self._item_to_check(item)

    async def get_check_by_token(self, token: str) -> Optional[Check]:
        """Get check by ping token."""
        async with self._get_table() as table:
            response = await table.query(
                IndexName="TokenIndex",
                KeyConditionExpression="GSI2PK = :pk AND GSI2SK = :sk",
                ExpressionAttributeValues={
                    ":pk": f"TOKEN#{token}",
                    ":sk": "CHECK",
                },
            )
            items = response.get("Items", [])
            return self._item_to_check(items[0]) if items else None

    async def list_team_checks(self, team_id: str) -> List[Check]:
        """List all checks for a team."""
        async with self._get_table() as table:
            response = await table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"TEAM#{team_id}",
                    ":sk_prefix": "CHECK#",
                },
            )
            items = response.get("Items", [])
            return [self._item_to_check(item) for item in items]

    async def update_check(self, team_id: str, check_id: str, updates: Dict[str, Any]) -> Check:
        """Update check attributes."""
        async with self._get_table() as table:
            # Build update expression
            update_parts = []
            expr_names = {}
            expr_values = {}

            for key, value in updates.items():
                attr_name = f"#{key}"
                attr_value = f":{key}"
                update_parts.append(f"{attr_name} = {attr_value}")
                expr_names[attr_name] = key
                expr_values[attr_value] = value

            # Update GSI attributes if needed
            if "alertAfterAt" in updates:
                update_parts.append("GSI1PK = :gsi1pk")
                update_parts.append("GSI1SK = :gsi1sk")
                expr_values[":gsi1pk"] = "DUE"
                expr_values[":gsi1sk"] = updates["alertAfterAt"]

            update_expr = "SET " + ", ".join(update_parts)

            response = await table.update_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW",
            )
            return self._item_to_check(response["Attributes"])

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.5))
    async def update_check_on_ping(
        self, team_id: str, check_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update check on ping with conditional write.
        Only updates if check is not paused.

        Returns:
            True if update succeeded, False if condition failed (paused)
        """
        try:
            async with self._get_table() as table:
                update_parts = []
                expr_names = {}
                expr_values = {}

                for key, value in updates.items():
                    attr_name = f"#{key}"
                    attr_value = f":{key}"
                    update_parts.append(f"{attr_name} = {attr_value}")
                    expr_names[attr_name] = key
                    expr_values[attr_value] = value

                # Update GSI attributes
                if "alertAfterAt" in updates:
                    update_parts.append("GSI1PK = :gsi1pk")
                    update_parts.append("GSI1SK = :gsi1sk")
                    expr_values[":gsi1pk"] = "DUE"
                    expr_values[":gsi1sk"] = updates["alertAfterAt"]

                update_expr = "SET " + ", ".join(update_parts)

                await table.update_item(
                    Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                    UpdateExpression=update_expr,
                    ConditionExpression="attribute_not_exists(#status) OR #status <> :paused",
                    ExpressionAttributeNames={**expr_names, "#status": "status"},
                    ExpressionAttributeValues={**expr_values, ":paused": CheckStatus.PAUSED.value},
                )
                return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    async def update_check_to_late(
        self, team_id: str, check_id: str, alert_at: str
    ) -> bool:
        """
        Conditionally update check to late status.
        Only updates if current status is not already late or paused.

        Returns:
            True if update succeeded (check went late), False if already late/paused
        """
        try:
            async with self._get_table() as table:
                await table.update_item(
                    Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                    UpdateExpression="SET #status = :late, lastAlertAt = :alert_at",
                    ConditionExpression="#status <> :late AND #status <> :paused",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":late": CheckStatus.LATE.value,
                        ":paused": CheckStatus.PAUSED.value,
                        ":alert_at": alert_at,
                    },
                )
                return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    async def delete_check(self, team_id: str, check_id: str) -> None:
        """Delete a check and all its pings."""
        async with self._get_table() as table:
            # Delete the check itself
            await table.delete_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"}
            )
            
            # Delete all pings for this check
            # Query all pings first
            response = await table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"CHECK#{check_id}",
                    ":sk_prefix": "PING#",
                },
            )
            
            # Delete pings in batches
            items = response.get("Items", [])
            for item in items:
                await table.delete_item(
                    Key={"PK": item["PK"], "SK": item["SK"]}
                )

    async def update_check_status(self, team_id: str, check_id: str, status: str) -> None:
        """Update check status."""
        await self.update_check(team_id, check_id, {"status": status})

    async def update_check_timing(self, team_id: str, check_id: str, next_due_at: int, alert_after_at: int) -> None:
        """Update check timing fields."""
        await self.update_check(team_id, check_id, {
            "nextDueAt": next_due_at,
            "alertAfterAt": alert_after_at,
            "GSI1SK": alert_after_at  # Update GSI for late detection
        })

    # Ping operations
    async def create_ping(self, ping: Ping) -> None:
        """Create a ping event."""
        ttl = get_current_time_seconds() + (30 * 24 * 60 * 60)  # 30 days

        async with self._get_table() as table:
            await table.put_item(
                Item={
                    "PK": f"CHECK#{ping.check_id}",
                    "SK": f"PING#{ping.timestamp}",
                    "checkId": ping.check_id,
                    "timestamp": ping.timestamp,
                    "receivedAt": ping.received_at,
                    "pingType": ping.ping_type,
                    "data": ping.data or "",
                    "TTL": ttl,
                }
            )

    async def list_check_pings(self, check_id: str, limit: int = 50, since: int = None) -> List[Ping]:
        """List recent pings for a check."""
        async with self._get_table() as table:
            if since:
                # Query with time filter
                response = await table.query(
                    KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
                    ExpressionAttributeValues={
                        ":pk": f"CHECK#{check_id}",
                        ":start": f"PING#{since}",
                        ":end": f"PING#{int(time.time() * 1000)}",
                    },
                    ScanIndexForward=False,  # Descending order (newest first)
                    Limit=limit,
                )
            else:
                # Original query without time filter
                response = await table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                    ExpressionAttributeValues={
                        ":pk": f"CHECK#{check_id}",
                        ":sk_prefix": "PING#",
                    },
                    ScanIndexForward=False,  # Descending order (newest first)
                    Limit=limit,
                )
            items = response.get("Items", [])
            return [
                Ping(
                    check_id=item["checkId"],
                    timestamp=item["timestamp"],
                    received_at=item["receivedAt"],
                    ping_type=item.get("pingType", "success"),
                    data=item.get("data"),
                )
                for item in items
            ]

    # Late detection
    async def query_due_checks(self, current_time_seconds: int, limit: int = 100) -> List[Check]:
        """Query checks that are due for late detection."""
        async with self._get_table() as table:
            response = await table.query(
                IndexName="DueIndex",
                KeyConditionExpression="GSI1PK = :pk AND GSI1SK <= :time",
                ExpressionAttributeValues={
                    ":pk": "DUE",
                    ":time": current_time_seconds,
                },
                Limit=limit,
            )
            items = response.get("Items", [])
            checks = [self._item_to_check(item) for item in items]
            
            # Debug logging for checks that might be incorrectly marked as late
            for check in checks:
                if check.last_ping_at:
                    from ..utils import parse_iso_timestamp
                    last_ping_seconds = parse_iso_timestamp(check.last_ping_at)
                    time_since_ping = current_time_seconds - last_ping_seconds
                    logger.info(f"Check {check.check_id} due: last_ping={time_since_ping}s ago, period={check.period_seconds}s, grace={check.grace_seconds}s, alert_after={check.alert_after_at}")
            
            return checks

    @staticmethod
    def _item_to_check(item: Dict[str, Any]) -> Check:
        """Convert DynamoDB item to Check entity."""
        from decimal import Decimal

        # Helper to convert Decimal to int
        def convert_to_int(val):
            if val is None:
                return None
            if isinstance(val, Decimal):
                return int(val)
            return val

        # Helper to convert Decimal timestamp to string
        def convert_timestamp(val):
            if val is None:
                return None
            if isinstance(val, Decimal):
                return str(int(val))
            if isinstance(val, (int, float)):
                return str(int(val))
            return str(val) if val else None

        return Check(
            check_id=item["checkId"],
            team_id=item["teamId"],
            name=item["name"],
            token=item["token"],
            period_seconds=convert_to_int(item["periodSeconds"]),
            grace_seconds=convert_to_int(item["graceSeconds"]),
            status=CheckStatus(item["status"]),
            created_at=item["createdAt"],
            last_ping_at=item.get("lastPingAt"),  # Already a string (ISO format)
            next_due_at=convert_timestamp(item.get("nextDueAt")),  # Convert Decimal to string
            alert_after_at=convert_timestamp(item.get("alertAfterAt")),  # Convert Decimal to string
            last_alert_at=item.get("lastAlertAt"),  # Already a string (ISO format)
            alert_channels=item.get("alertChannels", []),
            escalation_minutes=convert_to_int(item.get("escalationMinutes")) if item.get("escalationMinutes") else None,
            escalation_alert_channels=item.get("escalationAlertChannels", []),
        )

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email (scan-based for MVP)."""
        async with self._get_table() as table:
            # Scan for user with matching email (not efficient, but works for MVP)
            response = await table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk AND email = :email",
                ExpressionAttributeValues={
                    ":pk_prefix": "USER#",
                    ":sk": "PROFILE",
                    ":email": email,
                },
            )
            
            items = response.get("Items", [])
            if not items:
                return None
                
            item = items[0]
            return User(
                user_id=item["PK"].replace("USER#", ""),
                email=item["email"],
                name=item["name"],
                created_at=item["createdAt"],
            )

    async def remove_team_member(self, team_id: str, user_id: str) -> None:
        """Remove a member from a team."""
        async with self._get_table() as table:
            await table.delete_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"MEMBER#{user_id}"}
            )

    async def update_team_member_role(self, team_id: str, user_id: str, new_role: Role) -> None:
        """Update a team member's role."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"MEMBER#{user_id}"},
                UpdateExpression="SET #role = :role",
                ExpressionAttributeNames={"#role": "role"},
                ExpressionAttributeValues={":role": new_role.value},
            )

    # Pending invitation operations
    async def create_pending_invitation(self, invitation: PendingInvitation) -> None:
        """Create a pending invitation for a user."""
        async with self._get_table() as table:
            await table.put_item(
                Item={
                    "PK": f"INVITATION#{invitation.email}",
                    "SK": f"TEAM#{invitation.team_id}",
                    "email": invitation.email,
                    "teamId": invitation.team_id,
                    "role": invitation.role.value,
                    "invitedBy": invitation.invited_by,
                    "invitedAt": invitation.invited_at,
                }
            )

    async def get_pending_invitations_for_email(self, email: str) -> List[PendingInvitation]:
        """Get all pending invitations for an email."""
        async with self._get_table() as table:
            response = await table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": f"INVITATION#{email}"},
            )
            
            return [
                PendingInvitation(
                    email=item["email"],
                    team_id=item["teamId"],
                    role=Role(item["role"]),
                    invited_by=item["invitedBy"],
                    invited_at=item["invitedAt"],
                )
                for item in response.get("Items", [])
            ]

    async def list_pending_invitations_for_team(self, team_id: str) -> List[PendingInvitation]:
        """List all pending invitations for a team."""
        async with self._get_table() as table:
            response = await table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
                ExpressionAttributeValues={
                    ":pk_prefix": "INVITATION#",
                    ":sk": f"TEAM#{team_id}",
                },
            )

            return [
                PendingInvitation(
                    email=item["email"],
                    team_id=item["teamId"],
                    role=Role(item["role"]),
                    invited_by=item["invitedBy"],
                    invited_at=item["invitedAt"],
                )
                for item in response.get("Items", [])
            ]

    async def delete_pending_invitation(self, email: str, team_id: str) -> None:
        """Delete a pending invitation."""
        async with self._get_table() as table:
            await table.delete_item(
                Key={"PK": f"INVITATION#{email}", "SK": f"TEAM#{team_id}"}
            )

    async def update_team_mattermost_webhook(self, team_id: str, webhook_url: Optional[str]) -> None:
        """Update team Mattermost webhook URL."""
        async with self._get_table() as table:
            if webhook_url:
                await table.update_item(
                    Key={"PK": f"TEAM#{team_id}", "SK": "METADATA"},
                    UpdateExpression="SET mattermostWebhookUrl = :url",
                    ExpressionAttributeValues={":url": webhook_url},
                )
            else:
                # Remove webhook URL
                await table.update_item(
                    Key={"PK": f"TEAM#{team_id}", "SK": "METADATA"},
                    UpdateExpression="REMOVE mattermostWebhookUrl",
                )

    async def update_team_mattermost_webhooks(self, team_id: str, webhooks: list[str]) -> None:
        """Update team Mattermost webhooks array."""
        async with self._get_table() as table:
            if webhooks:
                await table.update_item(
                    Key={"PK": f"TEAM#{team_id}", "SK": "METADATA"},
                    UpdateExpression="SET mattermostWebhooks = :webhooks",
                    ExpressionAttributeValues={":webhooks": webhooks},
                )
            else:
                # Remove webhooks array
                await table.update_item(
                    Key={"PK": f"TEAM#{team_id}", "SK": "METADATA"},
                    UpdateExpression="REMOVE mattermostWebhooks",
                )

    async def increment_consecutive_alerts(self, team_id: str, check_id: str) -> None:
        """Increment the consecutive alert count for a check."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                UpdateExpression="ADD consecutiveAlertCount :inc",
                ExpressionAttributeValues={":inc": 1},
            )

    async def suppress_check_alerts(self, team_id: str, check_id: str, suppressed_until: str) -> None:
        """Suppress alerts for a check until the specified time."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                UpdateExpression="SET suppressedUntil = :until",
                ExpressionAttributeValues={":until": suppressed_until},
            )

    async def mark_escalation_triggered(self, team_id: str, check_id: str, triggered_at: str) -> None:
        """Mark that escalation has been triggered for a check."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                UpdateExpression="SET escalationTriggeredAt = :at",
                ExpressionAttributeValues={":at": triggered_at},
            )

    async def reset_alert_state(self, team_id: str, check_id: str) -> None:
        """Reset alert state when check recovers (clear consecutive count, escalation, suppression)."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHECK#{check_id}"},
                UpdateExpression="SET consecutiveAlertCount = :zero REMOVE escalationTriggeredAt, suppressedUntil",
                ExpressionAttributeValues={":zero": 0},
            )

    # Alert Channel Management
    async def create_alert_channel(self, channel: AlertChannel) -> None:
        """Create a new alert channel."""
        async with self._get_table() as table:
            await table.put_item(
                Item={
                    "PK": f"TEAM#{channel.team_id}",
                    "SK": f"CHANNEL#{channel.channel_id}",
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
            )

    async def get_alert_channel(self, team_id: str, channel_id: str) -> Optional[AlertChannel]:
        """Get an alert channel by ID."""
        async with self._get_table() as table:
            response = await table.get_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHANNEL#{channel_id}"}
            )
            item = response.get("Item")
            if not item:
                return None
            return AlertChannel(
                channel_id=item["channelId"],
                team_id=item["teamId"],
                name=item["name"],
                display_name=item["displayName"],
                type=AlertChannelType(item["type"]),
                configuration=item["configuration"],
                shared=item.get("shared", False),
                created_at=item["createdAt"],
                created_by=item["createdBy"],
            )

    async def list_alert_channels(self, team_id: str) -> List[AlertChannel]:
        """List all alert channels for a team."""
        async with self._get_table() as table:
            response = await table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                ExpressionAttributeValues={
                    ":pk": f"TEAM#{team_id}",
                    ":sk": "CHANNEL#",
                },
            )
            
            channels = []
            for item in response.get("Items", []):
                channels.append(AlertChannel(
                    channel_id=item["channelId"],
                    team_id=item["teamId"],
                    name=item["name"],
                    display_name=item["displayName"],
                    type=AlertChannelType(item["type"]),
                    configuration=item["configuration"],
                    shared=item.get("shared", False),
                    created_at=item["createdAt"],
                    created_by=item["createdBy"],
                ))
            return channels

    async def update_alert_channel(self, channel: AlertChannel) -> None:
        """Update an alert channel."""
        async with self._get_table() as table:
            await table.update_item(
                Key={"PK": f"TEAM#{channel.team_id}", "SK": f"CHANNEL#{channel.channel_id}"},
                UpdateExpression="SET displayName = :display, configuration = :config, #shared = :shared",
                ExpressionAttributeNames={"#shared": "shared"},
                ExpressionAttributeValues={
                    ":display": channel.display_name,
                    ":config": channel.configuration,
                    ":shared": channel.shared,
                },
            )

    async def delete_alert_channel(self, team_id: str, channel_id: str) -> None:
        """Delete an alert channel."""
        async with self._get_table() as table:
            await table.delete_item(
                Key={"PK": f"TEAM#{team_id}", "SK": f"CHANNEL#{channel_id}"}
            )

    async def delete_team(self, team_id: str) -> None:
        """Delete a team and all associated data (cascade delete)."""
        try:
            async with self._get_table() as table:
                # Get all items for this team
                response = await table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": f"TEAM#{team_id}"}
                )
                
                items_to_delete = []
                check_ids = []
                
                # Collect team items and extract check IDs
                for item in response.get("Items", []):
                    items_to_delete.append({"PK": item["PK"], "SK": item["SK"]})
                    if item["SK"].startswith("CHECK#"):
                        check_ids.append(item["SK"].replace("CHECK#", ""))
                
                logger.info(f"Found {len(items_to_delete)} team items and {len(check_ids)} checks to delete")
                
                # Get all pings for each check
                for check_id in check_ids:
                    try:
                        ping_response = await table.query(
                            KeyConditionExpression="PK = :pk",
                            ExpressionAttributeValues={":pk": f"CHECK#{check_id}"}
                        )
                        ping_count = len(ping_response.get("Items", []))
                        logger.info(f"Found {ping_count} pings for check {check_id}")
                        for ping in ping_response.get("Items", []):
                            items_to_delete.append({"PK": ping["PK"], "SK": ping["SK"]})
                    except Exception as e:
                        logger.warning(f"Failed to get pings for check {check_id}: {e}")
                        continue
                
                # Get all invitations for this team
                try:
                    invitation_response = await table.scan(
                        FilterExpression="SK = :sk",
                        ExpressionAttributeValues={":sk": f"TEAM#{team_id}"}
                    )
                    invitation_count = len(invitation_response.get("Items", []))
                    logger.info(f"Found {invitation_count} invitations for team")
                    for invitation in invitation_response.get("Items", []):
                        items_to_delete.append({"PK": invitation["PK"], "SK": invitation["SK"]})
                except Exception as e:
                    logger.warning(f"Failed to get invitations for team {team_id}: {e}")
                
                logger.info(f"Total items to delete: {len(items_to_delete)}")
                
                # Delete items individually for better error handling
                deleted_count = 0
                failed_count = 0
                
                for item in items_to_delete:
                    try:
                        await table.delete_item(Key=item)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete item {item}: {e}")
                        failed_count += 1
                        continue
                
                logger.info(f"Team deletion completed: {deleted_count} deleted, {failed_count} failed")
                
                if failed_count > 0:
                    raise PulsechecksError(f"Team deletion partially failed: {failed_count} items could not be deleted")
                        
        except Exception as e:
            logger.error(f"Failed to delete team {team_id}: {e}")
            raise PulsechecksError(f"Failed to delete team: {str(e)}")
