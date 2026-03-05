"""Firestore database client for GCP."""
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from ..config import get_settings
from ..models import (
    User, Team, TeamMember, Check, Ping, Role, CheckStatus,
    PendingInvitation, AlertChannel, AlertChannelType
)
from ..errors import PulsechecksError
from ..utils import get_iso_timestamp, get_current_time_seconds
from ..logging_config import get_logger
from .interface import DatabaseInterface

logger = get_logger(__name__)


class FirestoreClient(DatabaseInterface):
    """
    Firestore database client for Google Cloud Platform.

    Collection Structure:
    - users/{userId} - User profiles
    - teams/{teamId} - Team metadata
    - teams/{teamId}/members/{userId} - Team memberships
    - checks/{checkId} - Health checks (top-level for querying)
    - checks/{checkId}/pings/{pingId} - Ping events
    - teams/{teamId}/channels/{channelId} - Alert channels
    - invitations/{email}/teams/{teamId} - Pending invitations
    """

    def __init__(self, database: Optional[str] = None):
        """Initialize Firestore client."""
        try:
            from google.cloud import firestore
        except ImportError:
            raise ImportError(
                "google-cloud-firestore is not installed. "
                "Install it with: pip install google-cloud-firestore"
            )

        settings = get_settings()
        self.project_id = settings.gcp_project
        self.database_name = database or settings.firestore_database

        if not self.project_id:
            raise ValueError(
                "GCP_PROJECT environment variable must be set for Firestore"
            )

        # Initialize Firestore client
        self.db = firestore.AsyncClient(
            project=self.project_id,
            database=self.database_name
        )

        logger.info(f"Initialized Firestore client for project {self.project_id}")

    # User operations
    async def create_user(self, user: User) -> None:
        """Create a new user profile."""
        doc_ref = self.db.collection('users').document(user.user_id)
        await doc_ref.set({
            'userId': user.user_id,
            'email': user.email,
            'name': user.name,
            'createdAt': user.created_at,
            'lastLoginAt': user.last_login_at,
        })

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user profile by ID."""
        doc_ref = self.db.collection('users').document(user_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        return User(
            user_id=data['userId'],
            email=data['email'],
            name=data['name'],
            created_at=data['createdAt'],
            last_login_at=data.get('lastLoginAt'),
        )

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user profile by email address."""
        users_ref = self.db.collection('users')
        query = users_ref.where('email', '==', email).limit(1)
        docs = await query.get()

        if not docs:
            return None

        data = docs[0].to_dict()
        return User(
            user_id=data['userId'],
            email=data['email'],
            name=data['name'],
            created_at=data['createdAt'],
            last_login_at=data.get('lastLoginAt'),
        )

    async def update_user_login(self, user_id: str, name: str) -> None:
        """Update user's last login time and name."""
        doc_ref = self.db.collection('users').document(user_id)
        await doc_ref.update({
            'lastLoginAt': get_iso_timestamp(),
            'name': name,
        })

    # Team operations
    async def create_team(self, team: Team) -> None:
        """Create a new team."""
        doc_ref = self.db.collection('teams').document(team.team_id)
        await doc_ref.set({
            'teamId': team.team_id,
            'name': team.name,
            'createdAt': team.created_at,
            'createdBy': team.created_by,
            'mattermostWebhookUrl': team.mattermost_webhook_url or None,
            'mattermostWebhooks': team.mattermost_webhooks or [],
        })

    async def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        doc_ref = self.db.collection('teams').document(team_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        return Team(
            team_id=data['teamId'],
            name=data['name'],
            created_at=data['createdAt'],
            created_by=data['createdBy'],
            mattermost_webhook_url=data.get('mattermostWebhookUrl'),
            mattermost_webhooks=data.get('mattermostWebhooks', []),
        )

    async def update_team(self, team: Team) -> None:
        """Update team information."""
        doc_ref = self.db.collection('teams').document(team.team_id)
        await doc_ref.update({
            'name': team.name,
        })

    async def delete_team(self, team_id: str) -> None:
        """Delete a team and all associated data (cascade delete)."""
        try:
            from google.cloud import firestore

            # Delete team members subcollection
            members_ref = self.db.collection('teams').document(team_id).collection('members')
            async for doc in members_ref.stream():
                await doc.reference.delete()

            # Delete alert channels subcollection
            channels_ref = self.db.collection('teams').document(team_id).collection('channels')
            async for doc in channels_ref.stream():
                await doc.reference.delete()

            # Find and delete all checks for this team
            checks_ref = self.db.collection('checks')
            query = checks_ref.where('teamId', '==', team_id)
            async for check_doc in query.stream():
                check_id = check_doc.id

                # Delete pings for this check
                pings_ref = self.db.collection('checks').document(check_id).collection('pings')
                async for ping_doc in pings_ref.stream():
                    await ping_doc.reference.delete()

                # Delete the check
                await check_doc.reference.delete()

            # Delete invitations for this team
            invitations_ref = self.db.collection_group('teams')
            query = invitations_ref.where(firestore.FieldPath.document_id(), '==', team_id)
            async for inv_doc in query.stream():
                await inv_doc.reference.delete()

            # Finally, delete the team document itself
            team_ref = self.db.collection('teams').document(team_id)
            await team_ref.delete()

            logger.info(f"Successfully deleted team {team_id} and all associated data")

        except Exception as e:
            logger.error(f"Failed to delete team {team_id}: {e}")
            raise PulsechecksError(f"Failed to delete team: {str(e)}")

    async def list_user_teams(self, user_id: str) -> List[Dict[str, Any]]:
        """List all teams for a user with their role."""
        teams = []

        # Query all team memberships for this user across all teams
        # Use collection group query to search all members subcollections
        from google.cloud import firestore
        members_query = self.db.collection_group('members').where('userId', '==', user_id)

        async for member_doc in members_query.stream():
            # Get team_id from parent document
            team_id = member_doc.reference.parent.parent.id

            # Fetch team details
            team = await self.get_team(team_id)
            if team:
                member_data = member_doc.to_dict()
                teams.append({
                    'team': team,
                    'role': Role(member_data['role']),
                })

        return teams

    async def update_team_mattermost_webhook(self, team_id: str, webhook_url: Optional[str]) -> None:
        """Update team Mattermost webhook URL (legacy)."""
        doc_ref = self.db.collection('teams').document(team_id)
        if webhook_url:
            await doc_ref.update({'mattermostWebhookUrl': webhook_url})
        else:
            from google.cloud import firestore
            await doc_ref.update({'mattermostWebhookUrl': firestore.DELETE_FIELD})

    async def update_team_mattermost_webhooks(self, team_id: str, webhooks: list[str]) -> None:
        """Update team Mattermost webhooks array."""
        doc_ref = self.db.collection('teams').document(team_id)
        await doc_ref.update({'mattermostWebhooks': webhooks})

    # Team membership operations
    async def add_team_member(self, member: TeamMember) -> None:
        """Add a member to a team."""
        doc_ref = (self.db.collection('teams').document(member.team_id)
                   .collection('members').document(member.user_id))
        await doc_ref.set({
            'teamId': member.team_id,
            'userId': member.user_id,
            'role': member.role.value,
            'joinedAt': member.joined_at,
        })

    async def get_team_member(self, team_id: str, user_id: str) -> Optional[TeamMember]:
        """Get a team member."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('members').document(user_id))
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        return TeamMember(
            team_id=data['teamId'],
            user_id=data['userId'],
            role=Role(data['role']),
            joined_at=data['joinedAt'],
        )

    async def list_team_members(self, team_id: str) -> List[TeamMember]:
        """List all members of a team."""
        members_ref = (self.db.collection('teams').document(team_id)
                       .collection('members'))

        members = []
        async for doc in members_ref.stream():
            data = doc.to_dict()
            members.append(TeamMember(
                team_id=data['teamId'],
                user_id=data['userId'],
                role=Role(data['role']),
                joined_at=data['joinedAt'],
            ))

        return members

    async def remove_team_member(self, team_id: str, user_id: str) -> None:
        """Remove a member from a team."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('members').document(user_id))
        await doc_ref.delete()

    async def update_team_member_role(self, team_id: str, user_id: str, new_role: Role) -> None:
        """Update a team member's role."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('members').document(user_id))
        await doc_ref.update({'role': new_role.value})

    # Check operations
    async def create_check(self, check: Check) -> None:
        """Create a new health check."""
        doc_ref = self.db.collection('checks').document(check.check_id)

        data = {
            'checkId': check.check_id,
            'teamId': check.team_id,
            'name': check.name,
            'token': check.token,
            'periodSeconds': check.period_seconds,
            'graceSeconds': check.grace_seconds,
            'status': check.status.value,
            'createdAt': check.created_at,
            'lastPingAt': check.last_ping_at,
            'nextDueAt': int(check.next_due_at) if check.next_due_at else None,
            'alertAfterAt': int(check.alert_after_at) if check.alert_after_at else None,
            'lastAlertAt': check.last_alert_at,
            'alertChannels': check.alert_channels or [],
            'escalationMinutes': check.escalation_minutes,
            'escalationAlertChannels': check.escalation_alert_channels or [],
        }

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        await doc_ref.set(data)

    async def get_check(self, team_id: str, check_id: str) -> Optional[Check]:
        """Get check by ID."""
        doc_ref = self.db.collection('checks').document(check_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()

        # Verify it belongs to the team
        if data.get('teamId') != team_id:
            return None

        return self._dict_to_check(data)

    async def get_check_by_token(self, token: str) -> Optional[Check]:
        """Get check by ping token."""
        checks_ref = self.db.collection('checks')
        query = checks_ref.where('token', '==', token).limit(1)
        docs = await query.get()

        if not docs:
            return None

        data = docs[0].to_dict()
        return self._dict_to_check(data)

    async def list_team_checks(self, team_id: str) -> List[Check]:
        """List all checks for a team."""
        checks_ref = self.db.collection('checks')
        query = checks_ref.where('teamId', '==', team_id)

        checks = []
        async for doc in query.stream():
            data = doc.to_dict()
            checks.append(self._dict_to_check(data))

        return checks

    async def update_check(self, team_id: str, check_id: str, updates: Dict[str, Any]) -> Check:
        """Update check attributes. Returns updated check."""
        doc_ref = self.db.collection('checks').document(check_id)

        # Convert numeric strings to integers for timestamp fields
        firestore_updates = {}
        for key, value in updates.items():
            if key in ['nextDueAt', 'alertAfterAt'] and value is not None:
                firestore_updates[key] = int(value) if isinstance(value, str) else value
            else:
                firestore_updates[key] = value

        await doc_ref.update(firestore_updates)

        # Fetch and return updated check
        doc = await doc_ref.get()
        data = doc.to_dict()
        return self._dict_to_check(data)

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
            from google.cloud import firestore

            doc_ref = self.db.collection('checks').document(check_id)

            # Use transaction for conditional update
            @firestore.async_transactional
            async def update_if_not_paused(transaction, ref):
                snapshot = await ref.get(transaction=transaction)
                if not snapshot.exists:
                    return False

                data = snapshot.to_dict()
                if data.get('status') == CheckStatus.PAUSED.value:
                    return False

                # Convert updates
                firestore_updates = {}
                for key, value in updates.items():
                    if key in ['nextDueAt', 'alertAfterAt'] and value is not None:
                        firestore_updates[key] = int(value) if isinstance(value, str) else value
                    else:
                        firestore_updates[key] = value

                transaction.update(ref, firestore_updates)
                return True

            transaction = self.db.transaction()
            result = await update_if_not_paused(transaction, doc_ref)
            return result

        except Exception as e:
            logger.error(f"Error updating check on ping: {e}")
            return False

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
            from google.cloud import firestore

            doc_ref = self.db.collection('checks').document(check_id)

            @firestore.async_transactional
            async def update_if_not_late_or_paused(transaction, ref):
                snapshot = await ref.get(transaction=transaction)
                if not snapshot.exists:
                    return False

                data = snapshot.to_dict()
                current_status = data.get('status')

                if current_status in [CheckStatus.LATE.value, CheckStatus.PAUSED.value]:
                    return False

                transaction.update(ref, {
                    'status': CheckStatus.LATE.value,
                    'lastAlertAt': alert_at,
                })
                return True

            transaction = self.db.transaction()
            result = await update_if_not_late_or_paused(transaction, doc_ref)
            return result

        except Exception as e:
            logger.error(f"Error updating check to late: {e}")
            return False

    async def delete_check(self, team_id: str, check_id: str) -> None:
        """Delete a check and all its pings."""
        # Delete all pings first
        pings_ref = self.db.collection('checks').document(check_id).collection('pings')
        async for doc in pings_ref.stream():
            await doc.reference.delete()

        # Delete the check
        check_ref = self.db.collection('checks').document(check_id)
        await check_ref.delete()

    async def update_check_status(self, team_id: str, check_id: str, status: str) -> None:
        """Update check status."""
        doc_ref = self.db.collection('checks').document(check_id)
        await doc_ref.update({'status': status})

    async def update_check_timing(
        self, team_id: str, check_id: str, next_due_at: int, alert_after_at: int
    ) -> None:
        """Update check timing fields."""
        doc_ref = self.db.collection('checks').document(check_id)
        await doc_ref.update({
            'nextDueAt': int(next_due_at),
            'alertAfterAt': int(alert_after_at),
        })

    async def increment_consecutive_alerts(self, team_id: str, check_id: str) -> None:
        """Increment the consecutive alert count for a check."""
        from google.cloud import firestore

        doc_ref = self.db.collection('checks').document(check_id)
        await doc_ref.update({
            'consecutiveAlertCount': firestore.Increment(1)
        })

    async def suppress_check_alerts(self, team_id: str, check_id: str, suppressed_until: str) -> None:
        """Suppress alerts for a check until the specified time."""
        doc_ref = self.db.collection('checks').document(check_id)
        await doc_ref.update({'suppressedUntil': suppressed_until})

    async def mark_escalation_triggered(self, team_id: str, check_id: str, triggered_at: str) -> None:
        """Mark that escalation has been triggered for a check."""
        doc_ref = self.db.collection('checks').document(check_id)
        await doc_ref.update({'escalationTriggeredAt': triggered_at})

    async def reset_alert_state(self, team_id: str, check_id: str) -> None:
        """Reset alert state when check recovers."""
        from google.cloud import firestore

        doc_ref = self.db.collection('checks').document(check_id)
        await doc_ref.update({
            'consecutiveAlertCount': 0,
            'escalationTriggeredAt': firestore.DELETE_FIELD,
            'suppressedUntil': firestore.DELETE_FIELD,
        })

    # Ping operations
    async def create_ping(self, ping: Ping) -> None:
        """Create a ping event."""
        # Use timestamp as document ID for ordering
        ping_id = str(ping.timestamp)
        doc_ref = (self.db.collection('checks').document(ping.check_id)
                   .collection('pings').document(ping_id))

        # Calculate TTL (30 days from now)
        ttl_seconds = get_current_time_seconds() + (30 * 24 * 60 * 60)
        ttl_datetime = datetime.fromtimestamp(ttl_seconds, tz=timezone.utc)

        await doc_ref.set({
            'checkId': ping.check_id,
            'timestamp': ping.timestamp,
            'receivedAt': ping.received_at,
            'pingType': ping.ping_type,
            'data': ping.data or '',
            'ttl': ttl_datetime,  # Firestore TTL uses datetime
        })

    async def list_check_pings(self, check_id: str, limit: int = 50, since: int = None) -> List[Ping]:
        """List recent pings for a check."""
        pings_ref = (self.db.collection('checks').document(check_id)
                     .collection('pings'))

        # Order by timestamp descending (newest first)
        query = pings_ref.order_by('timestamp', direction='DESCENDING').limit(limit)

        if since:
            # Filter to pings after 'since' timestamp
            query = query.where('timestamp', '>=', since)

        pings = []
        async for doc in query.stream():
            data = doc.to_dict()
            pings.append(Ping(
                check_id=data['checkId'],
                timestamp=data['timestamp'],
                received_at=data['receivedAt'],
                ping_type=data.get('pingType', 'success'),
                data=data.get('data'),
            ))

        return pings

    # Late detection
    async def query_due_checks(self, current_time_seconds: int, limit: int = 100) -> List[Check]:
        """Query checks that are due for late detection."""
        checks_ref = self.db.collection('checks')

        # Query checks where alertAfterAt <= current_time
        query = (checks_ref
                 .where('alertAfterAt', '<=', current_time_seconds)
                 .limit(limit))

        checks = []
        async for doc in query.stream():
            data = doc.to_dict()
            check = self._dict_to_check(data)
            checks.append(check)

        return checks

    # Pending invitation operations
    async def create_pending_invitation(self, invitation: PendingInvitation) -> None:
        """Create a pending invitation for a user."""
        doc_ref = (self.db.collection('invitations').document(invitation.email)
                   .collection('teams').document(invitation.team_id))
        await doc_ref.set({
            'email': invitation.email,
            'teamId': invitation.team_id,
            'role': invitation.role.value,
            'invitedBy': invitation.invited_by,
            'invitedAt': invitation.invited_at,
        })

    async def get_pending_invitations_for_email(self, email: str) -> List[PendingInvitation]:
        """Get all pending invitations for an email."""
        teams_ref = (self.db.collection('invitations').document(email)
                     .collection('teams'))

        invitations = []
        async for doc in teams_ref.stream():
            data = doc.to_dict()
            invitations.append(PendingInvitation(
                email=data['email'],
                team_id=data['teamId'],
                role=Role(data['role']),
                invited_by=data['invitedBy'],
                invited_at=data['invitedAt'],
            ))

        return invitations

    async def delete_pending_invitation(self, email: str, team_id: str) -> None:
        """Delete a pending invitation."""
        doc_ref = (self.db.collection('invitations').document(email)
                   .collection('teams').document(team_id))
        await doc_ref.delete()

    # Alert channel operations
    async def create_alert_channel(self, channel: AlertChannel) -> None:
        """Create a new alert channel."""
        doc_ref = (self.db.collection('teams').document(channel.team_id)
                   .collection('channels').document(channel.channel_id))
        await doc_ref.set({
            'channelId': channel.channel_id,
            'teamId': channel.team_id,
            'name': channel.name,
            'displayName': channel.display_name,
            'type': channel.type.value,
            'configuration': channel.configuration,
            'shared': channel.shared,
            'createdAt': channel.created_at,
            'createdBy': channel.created_by,
        })

    async def get_alert_channel(self, team_id: str, channel_id: str) -> Optional[AlertChannel]:
        """Get an alert channel by ID."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('channels').document(channel_id))
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        return AlertChannel(
            channel_id=data['channelId'],
            team_id=data['teamId'],
            name=data['name'],
            display_name=data['displayName'],
            type=AlertChannelType(data['type']),
            configuration=data['configuration'],
            shared=data.get('shared', False),
            created_at=data['createdAt'],
            created_by=data['createdBy'],
        )

    async def list_alert_channels(self, team_id: str) -> List[AlertChannel]:
        """List all alert channels for a team."""
        channels_ref = (self.db.collection('teams').document(team_id)
                        .collection('channels'))

        channels = []
        async for doc in channels_ref.stream():
            data = doc.to_dict()
            channels.append(AlertChannel(
                channel_id=data['channelId'],
                team_id=data['teamId'],
                name=data['name'],
                display_name=data['displayName'],
                type=AlertChannelType(data['type']),
                configuration=data['configuration'],
                shared=data.get('shared', False),
                created_at=data['createdAt'],
                created_by=data['createdBy'],
            ))

        return channels

    async def update_alert_channel(self, channel: AlertChannel) -> None:
        """Update an alert channel."""
        doc_ref = (self.db.collection('teams').document(channel.team_id)
                   .collection('channels').document(channel.channel_id))
        await doc_ref.update({
            'displayName': channel.display_name,
            'configuration': channel.configuration,
            'shared': channel.shared,
        })

    async def delete_alert_channel(self, team_id: str, channel_id: str) -> None:
        """Delete an alert channel."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('channels').document(channel_id))
        await doc_ref.delete()

    # Helper methods
    @staticmethod
    def _dict_to_check(data: Dict[str, Any]) -> Check:
        """Convert Firestore document dict to Check entity."""
        return Check(
            check_id=data['checkId'],
            team_id=data['teamId'],
            name=data['name'],
            token=data['token'],
            period_seconds=int(data['periodSeconds']),
            grace_seconds=int(data['graceSeconds']),
            status=CheckStatus(data['status']),
            created_at=data['createdAt'],
            last_ping_at=data.get('lastPingAt'),
            next_due_at=str(int(data['nextDueAt'])) if data.get('nextDueAt') else None,
            alert_after_at=str(int(data['alertAfterAt'])) if data.get('alertAfterAt') else None,
            last_alert_at=data.get('lastAlertAt'),
            alert_channels=data.get('alertChannels', []),
            escalation_minutes=int(data['escalationMinutes']) if data.get('escalationMinutes') else None,
            escalation_alert_channels=data.get('escalationAlertChannels', []),
            consecutive_alert_count=int(data.get('consecutiveAlertCount', 0)),
            suppressed_until=data.get('suppressedUntil'),
            escalation_triggered_at=data.get('escalationTriggeredAt'),
        )
