"""Enums for the application."""
from enum import Enum


class Permission(str, Enum):
    """Team-level permissions."""

    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


class Role(str, Enum):
    """User roles within a team."""

    ADMIN = "admin"
    MEMBER = "member"

    def has_permission(self, permission: Permission) -> bool:
        """Check if role has the required permission."""
        if self == Role.ADMIN:
            return True  # Admin has all permissions
        elif self == Role.MEMBER:
            return permission == Permission.VIEW  # Member only has view permission
        return False


class CheckStatus(str, Enum):
    """Check status values."""

    UP = "up"
    LATE = "late"
    PAUSED = "paused"
    PENDING = "pending"  # New check waiting for first ping


class PingType(str, Enum):
    """Ping type values."""

    SUCCESS = "success"  # Normal successful ping
    FAIL = "fail"        # Job failed
    START = "start"      # Job started


class AlertChannelType(str, Enum):
    """Alert channel types."""
    
    SNS = "sns"
    MATTERMOST = "mattermost"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"