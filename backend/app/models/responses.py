"""Response models for API serialization."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from .enums import Role, CheckStatus, CheckType


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
    period_seconds: Optional[int] = Field(None, alias="periodSeconds")
    schedule: Optional[str] = Field(None)
    grace_seconds: int = Field(..., alias="graceSeconds")
    last_ping_at: Optional[str] = Field(None, alias="lastPingAt")
    next_due_at: Optional[str] = Field(None, alias="nextDueAt")
    created_at: str = Field(..., alias="createdAt")
    alert_channels: list[str] = Field(default_factory=list, alias="alertChannels")
    type: str = Field(default="heartbeat")
    url: Optional[str] = Field(None)
    expected_status_code: int = Field(default=200, alias="expectedStatusCode")
    expected_string: Optional[str] = Field(None, alias="expectedString")
    failure_threshold: int = Field(default=1, alias="failureThreshold")
    tags: List[str] = Field(default_factory=list)


class CheckDetailResponse(CheckResponse):
    """Detailed check response with token."""

    token: str
    alert_after_at: Optional[str] = Field(None, alias="alertAfterAt")
    last_alert_at: Optional[str] = Field(None, alias="lastAlertAt")
    alert_channels: List[str] = Field(default_factory=list, alias="alertChannels")

    # Escalation configuration
    escalation_minutes: Optional[int] = Field(None, alias="escalationMinutes")
    escalation_alert_channels: List[str] = Field(default_factory=list, alias="escalationAlertChannels")
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
    code: Optional[str] = None
    data: Optional[str] = None
    response_time_ms: Optional[int] = Field(None, alias="responseTimeMs")


class CheckStatsPointResponse(BaseModel):
    """A single response time data point for charting."""
    model_config = ConfigDict(populate_by_name=True)

    timestamp: str
    response_time_ms: int = Field(..., alias="responseTimeMs")
    ping_type: str = Field(..., alias="pingType")


class CheckStatsResponse(BaseModel):
    """Aggregated check statistics for a time window."""
    model_config = ConfigDict(populate_by_name=True)

    period: str
    uptime_pct: float = Field(..., alias="uptimePct")
    total_pings: int = Field(..., alias="totalPings")
    success_count: int = Field(..., alias="successCount")
    fail_count: int = Field(..., alias="failCount")
    avg_response_ms: Optional[int] = Field(None, alias="avgResponseMs")
    p95_response_ms: Optional[int] = Field(None, alias="p95ResponseMs")
    max_response_ms: Optional[int] = Field(None, alias="maxResponseMs")
    min_response_ms: Optional[int] = Field(None, alias="minResponseMs")
    latest_response_ms: Optional[int] = Field(None, alias="latestResponseMs")
    response_time_series: List[CheckStatsPointResponse] = Field(default_factory=list, alias="responseTimeSeries")


class ErrorCodeCountResponse(BaseModel):
    """Count of failures for a specific error code."""
    model_config = ConfigDict(populate_by_name=True)

    code: str
    count: int


class CheckErrorIncidentResponse(BaseModel):
    """Grouped failure incident details for a check."""
    model_config = ConfigDict(populate_by_name=True)

    started_at: str = Field(..., alias="startedAt")
    ended_at: str = Field(..., alias="endedAt")
    duration_seconds: int = Field(..., alias="durationSeconds")
    failure_count: int = Field(..., alias="failureCount")
    dominant_code: str = Field(..., alias="dominantCode")


class CheckErrorSummaryResponse(BaseModel):
    """Aggregated failure summary for a check and time window."""
    model_config = ConfigDict(populate_by_name=True)

    period: str
    total_failures: int = Field(..., alias="totalFailures")
    most_common_code: Optional[str] = Field(None, alias="mostCommonCode")
    last_failure_at: Optional[str] = Field(None, alias="lastFailureAt")
    longest_incident: Optional[CheckErrorIncidentResponse] = Field(None, alias="longestIncident")
    failure_codes: List[ErrorCodeCountResponse] = Field(default_factory=list, alias="failureCodes")
    recent_failures: List[PingResponse] = Field(default_factory=list, alias="recentFailures")


class MaintenanceWindowResponse(BaseModel):
    """Maintenance window API response."""
    model_config = ConfigDict(populate_by_name=True)

    window_id: str = Field(..., alias="windowId")
    team_id: str = Field(..., alias="teamId")
    check_id: Optional[str] = Field(None, alias="checkId")
    start_at: str = Field(..., alias="startAt")
    end_at: str = Field(..., alias="endAt")
    label: Optional[str] = None
    created_by: str = Field(..., alias="createdBy")
    created_at: str = Field(..., alias="createdAt")


class CheckUptimeIncidentResponse(BaseModel):
    """A grouped uptime incident for a reporting window."""
    model_config = ConfigDict(populate_by_name=True)

    started_at: str = Field(..., alias="startedAt")
    ended_at: str = Field(..., alias="endedAt")
    duration_seconds: int = Field(..., alias="durationSeconds")
    failure_count: int = Field(..., alias="failureCount")
    dominant_code: str = Field(..., alias="dominantCode")


class CheckUptimeResponse(BaseModel):
    """Uptime summary for a custom time window."""
    model_config = ConfigDict(populate_by_name=True)

    from_at: str = Field(..., alias="from")
    to_at: str = Field(..., alias="to")
    exclude_maintenance: bool = Field(..., alias="excludeMaintenance")
    uptime_pct: float = Field(..., alias="uptimePct")
    total_observed_minutes: float = Field(..., alias="totalObservedMinutes")
    downtime_minutes: float = Field(..., alias="downtimeMinutes")
    excluded_maintenance_minutes: float = Field(..., alias="excludedMaintenanceMinutes")
    incidents: List[CheckUptimeIncidentResponse] = Field(default_factory=list)
    maintenance_windows: List[MaintenanceWindowResponse] = Field(default_factory=list, alias="maintenanceWindows")


class ReportResponse(BaseModel):
    """Generated report metadata response."""
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(..., alias="reportId")
    team_id: str = Field(..., alias="teamId")
    check_id: Optional[str] = Field(None, alias="checkId")
    report_type: str = Field(..., alias="reportType")
    format: str
    from_date: str = Field(..., alias="from")
    to_date: str = Field(..., alias="to")
    status: str
    download_url: Optional[str] = Field(None, alias="downloadUrl")
    created_at: str = Field(..., alias="createdAt")
    created_by: str = Field(..., alias="createdBy")
    expires_at: str = Field(..., alias="expiresAt")
    file_name: Optional[str] = Field(None, alias="fileName")
    content_type: Optional[str] = Field(None, alias="contentType")


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
