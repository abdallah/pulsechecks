"""Internal entity models for database operations."""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .enums import Role, CheckStatus, AlertChannelType


class User(BaseModel):
    """User entity."""

    user_id: str
    email: str
    name: str
    created_at: str
    last_login_at: Optional[str] = None


class Team(BaseModel):
    """Team entity."""

    team_id: str
    name: str
    created_at: str
    created_by: str
    mattermost_webhook_url: Optional[str] = None  # Legacy field for backward compatibility
    mattermost_webhooks: list[str] = []  # New field for multiple webhooks


class TeamMember(BaseModel):
    """Team membership entity."""

    team_id: str
    user_id: str
    role: Role
    joined_at: str


class MattermostChannel(BaseModel):
    """Mattermost channel configuration entity."""
    
    channel_id: str
    team_id: str
    name: str
    display_name: str
    webhook_url: str
    shared: bool = False
    created_at: str
    created_by: str


class AlertChannel(BaseModel):
    """Alert channel configuration entity."""
    
    channel_id: str
    team_id: str
    name: str
    display_name: str
    type: AlertChannelType
    configuration: Dict[str, Any]  # Type-specific config
    shared: bool = False
    created_at: str
    created_by: str


class Check(BaseModel):
    """Check entity."""

    check_id: str
    team_id: str
    name: str
    token: str
    period_seconds: int
    grace_seconds: int
    status: CheckStatus = CheckStatus.UP
    created_at: str
    last_ping_at: Optional[str] = None
    next_due_at: Optional[str] = None
    alert_after_at: Optional[str] = None
    last_alert_at: Optional[str] = None
    alert_channels: list[str] = []  # List of alert channel IDs
    mattermost_channels: list[str] = []  # List of Mattermost channel IDs (legacy)
    
    # Escalation configuration
    escalation_minutes: Optional[int] = None  # Minutes before escalating
    escalation_alert_channels: list[str] = []  # Alert channels for escalated alerts
    escalation_mattermost_channels: list[str] = []  # Mattermost channels for escalated alerts (legacy)
    escalation_triggered_at: Optional[str] = None  # When escalation was last triggered
    
    # Suppression configuration  
    suppress_after_count: Optional[int] = None  # Suppress after N consecutive alerts
    suppress_duration_minutes: Optional[int] = None  # Suppress for N minutes
    consecutive_alert_count: int = 0  # Current consecutive alert count
    suppressed_until: Optional[str] = None  # Suppressed until this timestamp


class Ping(BaseModel):
    """Ping entity."""

    check_id: str
    timestamp: str
    received_at: str
    ping_type: str = "success"  # success, fail, or start
    data: Optional[str] = None


class PendingInvitation(BaseModel):
    """Pending team invitation for users who haven't logged in yet."""

    email: str
    team_id: str
    role: Role
    invited_by: str
    invited_at: str
