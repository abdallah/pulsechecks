"""Response models for API serialization."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from .enums import Role, CheckStatus


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: Optional[str] = None


class UserResponse(BaseModel):
    """User profile response."""
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId")
    email: str
    name: str
    created_at: str = Field(..., alias="createdAt")
    last_login_at: Optional[str] = Field(None, alias="lastLoginAt")


class TeamResponse(BaseModel):
    """Team response."""
    model_config = ConfigDict(populate_by_name=True, use_alias=True)

    team_id: str = Field(..., alias="teamId")
    name: str
    role: Role
    created_at: str = Field(..., alias="createdAt")


class CheckResponse(BaseModel):
    """Check list item response."""
    model_config = ConfigDict(populate_by_name=True)

    check_id: str = Field(..., alias="checkId")
    team_id: str = Field(..., alias="teamId")
    name: str
    status: CheckStatus
    period_seconds: int = Field(..., alias="periodSeconds")
    grace_seconds: int = Field(..., alias="graceSeconds")
    last_ping_at: Optional[str] = Field(None, alias="lastPingAt")
    next_due_at: Optional[str] = Field(None, alias="nextDueAt")
    created_at: str = Field(..., alias="createdAt")
    alert_channels: list[str] = Field(default_factory=list, alias="alertChannels")


class CheckDetailResponse(CheckResponse):
    """Detailed check response with token."""

    token: str
    alert_after_at: Optional[str] = Field(None, alias="alertAfterAt")
    last_alert_at: Optional[str] = Field(None, alias="lastAlertAt")
    alert_channels: List[str] = Field(default_factory=list, alias="alertChannels")
    
    # Escalation configuration
    escalation_minutes: Optional[int] = Field(None, alias="escalationMinutes")
    escalation_triggered_at: Optional[str] = Field(None, alias="escalationTriggeredAt")
    
    # Suppression configuration
    suppress_after_count: Optional[int] = Field(None, alias="suppressAfterCount")
    suppress_duration_minutes: Optional[int] = Field(None, alias="suppressDurationMinutes")
    consecutive_alert_count: int = Field(default=0, alias="consecutiveAlertCount")
    suppressed_until: Optional[str] = Field(None, alias="suppressedUntil")


class PingResponse(BaseModel):
    """Ping history item response."""
    model_config = ConfigDict(populate_by_name=True)

    check_id: str = Field(..., alias="checkId")
    timestamp: str
    received_at: str = Field(..., alias="receivedAt")
    ping_type: str = Field(default="success", alias="pingType")
    data: Optional[str] = None


class OkResponse(BaseModel):
    """Simple OK response."""

    ok: bool = True
    message: Optional[str] = None


class AlertTopicResponse(BaseModel):
    """SNS alert topic response."""
    model_config = ConfigDict(populate_by_name=True)

    topic_arn: str = Field(..., alias="topicArn")
    topic_name: str = Field(..., alias="topicName")
    display_name: Optional[str] = Field(None, alias="displayName")
    shared: bool = Field(False, description="Whether this topic is shared across teams")
