"""Firestore database client for GCP."""
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from ..config import get_settings
from ..models import (
    User, Team, TeamMember, Check, Ping, Role, CheckStatus,
    PendingInvitation, AlertChannel, AlertChannelType, MaintenanceWindow, Report
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
            'slug': team.slug,
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
            slug=data.get('slug'),
            created_at=data['createdAt'],
            created_by=data['createdBy'],
            mattermost_webhook_url=data.get('mattermostWebhookUrl'),
            mattermost_webhooks=data.get('mattermostWebhooks', []),
        )

    async def get_team_by_slug(self, team_slug: str) -> Optional[Team]:
        """Get team by slug."""
        query = self.db.collection('teams').where('slug', '==', team_slug).limit(1)
        docs = await query.get()
        for doc in docs:
            data = doc.to_dict()
            return Team(
                team_id=data['teamId'],
                name=data['name'],
                slug=data.get('slug'),
                created_at=data['createdAt'],
                created_by=data['createdBy'],
                mattermost_webhook_url=data.get('mattermostWebhookUrl'),
                mattermost_webhooks=data.get('mattermostWebhooks', []),
            )
        return None

    async def get_check_by_team_slug_and_check_slug(self, team_slug: str, check_slug: str) -> Optional['Check']:
        """Get check by team slug and check slug — used for human-friendly ping URLs."""
        team = await self.get_team_by_slug(team_slug)
        if not team:
            return None
        return await self.get_check_by_slug(team.team_id, check_slug)

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
            'slug': check.slug,
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
            'type': check.type if isinstance(check.type, str) else check.type.value,
            'schedule': check.schedule,
            'url': check.url,
            'expectedStatusCode': check.expected_status_code,
            'failureThreshold': check.failure_threshold,
        }

        # Remove None values (but keep slug and other important fields)
        data = {k: v for k, v in data.items() if v is not None or k in ['slug']}

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

    async def get_check_by_slug(self, team_id: str, slug: str) -> Optional[Check]:
        """Get check by slug (friendly name) for a specific team."""
        checks_ref = self.db.collection('checks')
        query = checks_ref.where('teamId', '==', team_id).where('slug', '==', slug).limit(1)
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
            'code': ping.code,
            'data': ping.data or '',
            'responseTimeMs': ping.response_time_ms,
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
                code=data.get('code'),
                data=data.get('data'),
                response_time_ms=data.get('responseTimeMs'),
            ))

        return pings

    async def list_check_pings_between(
        self,
        check_id: str,
        start_at: str,
        end_at: str,
        limit: int = 10000,
    ) -> List[Ping]:
        """List pings for a check inside an inclusive ISO timestamp range."""
        pings_ref = (self.db.collection('checks').document(check_id)
                     .collection('pings'))

        query = (pings_ref
                 .where('timestamp', '>=', start_at)
                 .where('timestamp', '<=', end_at)
                 .order_by('timestamp')
                 .limit(limit))

        pings = []
        async for doc in query.stream():
            data = doc.to_dict()
            pings.append(Ping(
                check_id=data['checkId'],
                timestamp=data['timestamp'],
                received_at=data['receivedAt'],
                ping_type=data.get('pingType', 'success'),
                code=data.get('code'),
                data=data.get('data'),
                response_time_ms=data.get('responseTimeMs'),
            ))

        return pings

    async def create_maintenance_window(self, window: MaintenanceWindow) -> None:
        """Create a maintenance window."""
        doc_ref = (self.db.collection('teams').document(window.team_id)
                   .collection('maintenance').document(window.window_id))
        await doc_ref.set({
            'windowId': window.window_id,
            'teamId': window.team_id,
            'checkId': window.check_id,
            'startAt': window.start_at,
            'endAt': window.end_at,
            'label': window.label,
            'createdBy': window.created_by,
            'createdAt': window.created_at,
        })

    async def list_maintenance_windows(self, team_id: str, check_id: str | None = None) -> List[MaintenanceWindow]:
        """List maintenance windows for a team."""
        windows_ref = (self.db.collection('teams').document(team_id)
                       .collection('maintenance'))

        windows = []
        async for doc in windows_ref.stream():
            data = doc.to_dict()
            if check_id and data.get('checkId') not in (None, check_id):
                continue
            windows.append(MaintenanceWindow(
                window_id=data['windowId'],
                team_id=data['teamId'],
                check_id=data.get('checkId'),
                start_at=data['startAt'],
                end_at=data['endAt'],
                label=data.get('label'),
                created_by=data['createdBy'],
                created_at=data['createdAt'],
            ))

        return sorted(windows, key=lambda window: (window.start_at, window.window_id))

    async def delete_maintenance_window(self, team_id: str, window_id: str) -> None:
        """Delete a maintenance window."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('maintenance').document(window_id))
        await doc_ref.delete()

    async def create_report(self, report: Report) -> None:
        """Persist a generated report record."""
        doc_ref = (self.db.collection('teams').document(report.team_id)
                   .collection('reports').document(report.report_id))
        await doc_ref.set({
            'reportId': report.report_id,
            'teamId': report.team_id,
            'checkId': report.check_id,
            'reportType': report.report_type,
            'format': report.format,
            'from': report.from_date,
            'to': report.to_date,
            'status': report.status,
            'downloadUrl': report.download_url,
            'createdAt': report.created_at,
            'createdBy': report.created_by,
            'expiresAt': report.expires_at,
            'fileName': report.file_name,
            'contentType': report.content_type,
            'content': report.content,
        })

    async def get_report(self, team_id: str, report_id: str) -> Optional[Report]:
        """Get a report by ID."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('reports').document(report_id))
        doc = await doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Report(
            report_id=data['reportId'],
            team_id=data['teamId'],
            check_id=data.get('checkId'),
            report_type=data['reportType'],
            format=data['format'],
            from_date=data['from'],
            to_date=data['to'],
            status=data['status'],
            download_url=data.get('downloadUrl'),
            created_at=data['createdAt'],
            created_by=data['createdBy'],
            expires_at=data['expiresAt'],
            file_name=data.get('fileName'),
            content_type=data.get('contentType'),
            content=data.get('content'),
        )

    async def list_reports(self, team_id: str) -> List[Report]:
        """List reports for a team."""
        reports_ref = (self.db.collection('teams').document(team_id)
                       .collection('reports'))
        reports = []
        async for doc in reports_ref.stream():
            data = doc.to_dict()
            reports.append(Report(
                report_id=data['reportId'],
                team_id=data['teamId'],
                check_id=data.get('checkId'),
                report_type=data['reportType'],
                format=data['format'],
                from_date=data['from'],
                to_date=data['to'],
                status=data['status'],
                download_url=data.get('downloadUrl'),
                created_at=data['createdAt'],
                created_by=data['createdBy'],
                expires_at=data['expiresAt'],
                file_name=data.get('fileName'),
                content_type=data.get('contentType'),
                content=data.get('content'),
            ))
        return sorted(reports, key=lambda report: (report.created_at, report.report_id), reverse=True)

    async def delete_report(self, team_id: str, report_id: str) -> None:
        """Delete a report."""
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('reports').document(report_id))
        await doc_ref.delete()

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

    async def list_all_http_checks(self) -> List[Check]:
        """List all active HTTP checks (type=http, status != paused)."""
        checks_ref = self.db.collection('checks')
        query = checks_ref.where('type', '==', 'http')
        checks = []
        async for doc in query.stream():
            data = doc.to_dict()
            check = self._dict_to_check(data)
            if check.status != CheckStatus.PAUSED.value:
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

    async def list_pending_invitations_for_team(self, team_id: str) -> List[PendingInvitation]:
        """List all pending invitations for a team using collection group query."""
        invitations = []
        # Use collection group query on all 'teams' subcollections filtered by teamId
        query = self.db.collection_group('teams').where('teamId', '==', team_id)

        async for doc in query.stream():
            data = doc.to_dict()
            if not data:
                continue
            invitations.append(PendingInvitation(
                email=data.get('email', ''),
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
        """Delete an alert channel and remove it from all checks that reference it."""
        from google.cloud import firestore

        # Delete the channel document
        doc_ref = (self.db.collection('teams').document(team_id)
                   .collection('channels').document(channel_id))
        await doc_ref.delete()

        # Cascade: remove channel_id from all checks in the team that reference it
        checks_ref = (self.db.collection('teams').document(team_id)
                      .collection('checks'))
        checks_stream = checks_ref.stream()
        async for check_doc in checks_stream:
            data = check_doc.to_dict()
            alert_channels = data.get('alertChannels', [])
            escalation_channels = data.get('escalationAlertChannels', [])
            if channel_id in alert_channels or channel_id in escalation_channels:
                update = {}
                if channel_id in alert_channels:
                    update['alertChannels'] = firestore.ArrayRemove([channel_id])
                if channel_id in escalation_channels:
                    update['escalationAlertChannels'] = firestore.ArrayRemove([channel_id])
                await check_doc.reference.update(update)

    # Helper methods
    @staticmethod
    def _dict_to_check(data: Dict[str, Any]) -> Check:
        """Convert Firestore document dict to Check entity."""
        return Check(
            check_id=data['checkId'],
            team_id=data['teamId'],
            name=data['name'],
            token=data['token'],
            slug=data.get('slug'),
            period_seconds=int(data['periodSeconds']) if data.get('periodSeconds') is not None else 0,
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
            type=data.get('type', 'heartbeat'),
            schedule=data.get('schedule'),
            url=data.get('url'),
            expected_status_code=int(data.get('expectedStatusCode', 200)),
            failure_threshold=int(data.get('failureThreshold', 1)),
        )
