"""Abstract database interface for multi-cloud support."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from ..models import (
    User, Team, TeamMember, Check, Ping, Role,
    PendingInvitation, AlertChannel, AlertDelivery, MaintenanceWindow, Report
)


class DatabaseInterface(ABC):
    """
    Abstract database interface that can be implemented by different providers.

    This interface defines all database operations required by Pulsechecks,
    allowing the application to work with different database backends
    (DynamoDB, Firestore, etc.) without changing business logic.
    """

    # User operations
    @abstractmethod
    async def create_user(self, user: User) -> None:
        """Create a new user profile."""
        pass

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user profile by ID."""
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user profile by email address."""
        pass

    @abstractmethod
    async def update_user_login(self, user_id: str, name: str) -> None:
        """Update user's last login time and name."""
        pass

    # Team operations
    @abstractmethod
    async def create_team(self, team: Team) -> None:
        """Create a new team."""
        pass

    @abstractmethod
    async def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        pass

    @abstractmethod
    async def update_team(self, team: Team) -> None:
        """Update team information."""
        pass

    @abstractmethod
    async def delete_team(self, team_id: str) -> None:
        """Delete a team and all associated data (cascade delete)."""
        pass

    @abstractmethod
    async def list_user_teams(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all teams for a user with their role.
        Returns list of dicts with 'team' and 'role' keys.
        """
        pass

    @abstractmethod
    async def update_team_mattermost_webhook(self, team_id: str, webhook_url: Optional[str]) -> None:
        """Update team Mattermost webhook URL (legacy)."""
        pass

    @abstractmethod
    async def update_team_mattermost_webhooks(self, team_id: str, webhooks: list[str]) -> None:
        """Update team Mattermost webhooks array."""
        pass

    # Team membership operations
    @abstractmethod
    async def add_team_member(self, member: TeamMember) -> None:
        """Add a member to a team."""
        pass

    @abstractmethod
    async def get_team_member(self, team_id: str, user_id: str) -> Optional[TeamMember]:
        """Get a team member."""
        pass

    @abstractmethod
    async def list_team_members(self, team_id: str) -> List[TeamMember]:
        """List all members of a team."""
        pass

    @abstractmethod
    async def remove_team_member(self, team_id: str, user_id: str) -> None:
        """Remove a member from a team."""
        pass

    @abstractmethod
    async def update_team_member_role(self, team_id: str, user_id: str, new_role: Role) -> None:
        """Update a team member's role."""
        pass

    # Check operations
    @abstractmethod
    async def create_check(self, check: Check) -> None:
        """Create a new health check."""
        pass

    @abstractmethod
    async def get_check(self, team_id: str, check_id: str) -> Optional[Check]:
        """Get check by ID."""
        pass

    @abstractmethod
    async def get_check_by_token(self, token: str) -> Optional[Check]:
        """Get check by ping token."""
        pass

    @abstractmethod
    async def list_team_checks(self, team_id: str) -> List[Check]:
        """List all checks for a team."""
        pass

    @abstractmethod
    async def update_check(self, team_id: str, check_id: str, updates: Dict[str, Any]) -> Check:
        """Update check attributes. Returns updated check."""
        pass

    @abstractmethod
    async def update_check_on_ping(
        self, team_id: str, check_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update check on ping with conditional write.
        Only updates if check is not paused.

        Returns:
            True if update succeeded, False if condition failed (paused)
        """
        pass

    @abstractmethod
    async def update_check_to_late(
        self, team_id: str, check_id: str, alert_at: str
    ) -> bool:
        """
        Conditionally update check to late status.
        Only updates if current status is not already late or paused.

        Returns:
            True if update succeeded (check went late), False if already late/paused
        """
        pass

    @abstractmethod
    async def delete_check(self, team_id: str, check_id: str) -> None:
        """Delete a check and all its pings."""
        pass

    @abstractmethod
    async def update_check_status(self, team_id: str, check_id: str, status: str) -> None:
        """Update check status."""
        pass

    @abstractmethod
    async def update_check_timing(
        self, team_id: str, check_id: str, next_due_at: int, alert_after_at: int
    ) -> None:
        """Update check timing fields."""
        pass

    @abstractmethod
    async def increment_consecutive_alerts(self, team_id: str, check_id: str) -> None:
        """Increment the consecutive alert count for a check."""
        pass

    @abstractmethod
    async def suppress_check_alerts(self, team_id: str, check_id: str, suppressed_until: str) -> None:
        """Suppress alerts for a check until the specified time."""
        pass

    @abstractmethod
    async def mark_escalation_triggered(self, team_id: str, check_id: str, triggered_at: str) -> None:
        """Mark that escalation has been triggered for a check."""
        pass

    @abstractmethod
    async def reset_alert_state(self, team_id: str, check_id: str) -> None:
        """Reset alert state when check recovers (clear consecutive count, escalation, suppression)."""
        pass

    # Ping operations
    @abstractmethod
    async def create_ping(self, ping: Ping) -> None:
        """Create a ping event."""
        pass

    @abstractmethod
    async def list_check_pings(self, check_id: str, limit: int = 50, since: int = None) -> List[Ping]:
        """List recent pings for a check."""
        pass

    @abstractmethod
    async def list_check_pings_between(
        self,
        check_id: str,
        start_at: str,
        end_at: str,
        limit: int = 10000,
    ) -> List[Ping]:
        """List pings for a check inside an inclusive ISO timestamp range."""
        pass

    @abstractmethod
    async def create_maintenance_window(self, window: MaintenanceWindow) -> None:
        """Create a maintenance window."""
        pass

    @abstractmethod
    async def list_maintenance_windows(self, team_id: str, check_id: str | None = None) -> List[MaintenanceWindow]:
        """List maintenance windows for a team, optionally filtered to a check plus team-wide windows."""
        pass

    @abstractmethod
    async def delete_maintenance_window(self, team_id: str, window_id: str) -> None:
        """Delete a maintenance window."""
        pass

    # Alert delivery queue / history operations

    @abstractmethod
    async def create_alert_delivery(self, delivery: AlertDelivery) -> None:
        """Persist a new alert delivery record."""
        pass

    @abstractmethod
    async def update_alert_delivery(self, delivery: AlertDelivery) -> None:
        """Update an alert delivery's status/attempt fields."""
        pass

    @abstractmethod
    async def query_due_alert_deliveries(self, current_time_seconds: int, limit: int = 100) -> List[AlertDelivery]:
        """Query pending deliveries whose next_attempt_at is due."""
        pass

    @abstractmethod
    async def list_alert_deliveries(self, team_id: str, check_id: str | None = None, limit: int = 50) -> List[AlertDelivery]:
        """List delivery history for a team (optionally one check), newest first."""
        pass

    @abstractmethod
    async def create_report(self, report: Report) -> None:
        """Persist a generated report record."""
        pass

    @abstractmethod
    async def get_report(self, team_id: str, report_id: str) -> Optional[Report]:
        """Get a report by ID."""
        pass

    @abstractmethod
    async def list_reports(self, team_id: str) -> List[Report]:
        """List reports for a team."""
        pass

    @abstractmethod
    async def delete_report(self, team_id: str, report_id: str) -> None:
        """Delete a report and its stored content."""
        pass

    # Late detection
    @abstractmethod
    async def query_due_checks(self, current_time_seconds: int, limit: int = 100) -> List[Check]:
        """Query checks that are due for late detection."""
        pass

    @abstractmethod
    async def list_all_http_checks(self) -> List[Check]:
        """List all active HTTP checks (type=http, status != paused)."""
        pass

    # Pending invitation operations
    @abstractmethod
    async def create_pending_invitation(self, invitation: PendingInvitation) -> None:
        """Create a pending invitation for a user."""
        pass

    @abstractmethod
    async def get_pending_invitations_for_email(self, email: str) -> List[PendingInvitation]:
        """Get all pending invitations for an email."""
        pass

    @abstractmethod
    async def list_pending_invitations_for_team(self, team_id: str) -> List[PendingInvitation]:
        """List all pending invitations for a team."""
        pass

    @abstractmethod
    async def delete_pending_invitation(self, email: str, team_id: str) -> None:
        """Delete a pending invitation."""
        pass

    # Alert channel operations
    @abstractmethod
    async def create_alert_channel(self, channel: AlertChannel) -> None:
        """Create a new alert channel."""
        pass

    @abstractmethod
    async def get_alert_channel(self, team_id: str, channel_id: str) -> Optional[AlertChannel]:
        """Get an alert channel by ID."""
        pass

    @abstractmethod
    async def list_alert_channels(self, team_id: str) -> List[AlertChannel]:
        """List all alert channels for a team."""
        pass

    @abstractmethod
    async def update_alert_channel(self, channel: AlertChannel) -> None:
        """Update an alert channel."""
        pass

    @abstractmethod
    async def delete_alert_channel(self, team_id: str, channel_id: str) -> None:
        """Delete an alert channel."""
        pass
