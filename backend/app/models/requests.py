"""Request models for API validation."""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import re


class CreateTeamRequest(BaseModel):
    """Request to create a new team."""

    name: str = Field(..., min_length=1, max_length=100, description="Team name")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace")
        # Check for valid characters (alphanumeric, spaces, hyphens, underscores)
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v.strip()):
            raise ValueError("name can only contain letters, numbers, spaces, hyphens, and underscores")
        return v.strip()


class CreateCheckRequest(BaseModel):
    """Request to create a new check."""

    name: str = Field(..., min_length=1, max_length=200, description="Check name")
    period_seconds: int = Field(
        ..., ge=60, le=31536000, description="Check period in seconds (1min - 1year)",
        alias="periodSeconds"
    )
    grace_seconds: int = Field(
        ..., ge=0, le=86400, description="Grace period in seconds (0 - 24h)",
        alias="graceSeconds"
    )
    alert_channels: list[str] = Field(default_factory=list, description="List of alert channel IDs to notify")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace")
        return v.strip()

    @field_validator("alert_channels")
    @classmethod
    def validate_alert_channels(cls, v: list[str]) -> list[str]:
        if len(v) > 10:
            raise ValueError("Maximum 10 alert channels allowed")
        return v

    @model_validator(mode='after')
    def validate_grace_period(self):
        """Ensure grace period is reasonable relative to check period."""
        if self.grace_seconds > self.period_seconds:
            raise ValueError("grace_seconds cannot exceed period_seconds")
        return self


class UpdateCheckRequest(BaseModel):
    """Request to update a check."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    period_seconds: Optional[int] = Field(None, ge=60, le=31536000, alias="periodSeconds")
    grace_seconds: Optional[int] = Field(None, ge=0, le=86400, alias="graceSeconds")
    alert_channels: Optional[list[str]] = Field(None, alias="alertChannels", description="List of alert channel IDs to notify")
    
    # Escalation configuration
    escalation_minutes: Optional[int] = Field(None, ge=1, le=1440, alias="escalationMinutes", description="Minutes before escalating")
    
    # Suppression configuration
    suppress_after_count: Optional[int] = Field(None, ge=1, le=100, alias="suppressAfterCount", description="Suppress after N consecutive alerts")
    suppress_duration_minutes: Optional[int] = Field(None, ge=1, le=10080, alias="suppressDurationMinutes", description="Suppress for N minutes")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("name cannot be empty or whitespace")
        return v.strip() if v else None

    @field_validator("alert_channels")
    @classmethod
    def validate_alert_channels(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 alert channels allowed")
        return v

    @model_validator(mode='after')
    def validate_grace_period(self):
        """Ensure grace period is reasonable relative to check period."""
        if self.grace_seconds is not None and self.period_seconds is not None:
            if self.grace_seconds > self.period_seconds:
                raise ValueError("grace_seconds cannot exceed period_seconds")
        return self


class PingRequest(BaseModel):
    """Optional request body for ping endpoint."""

    data: Optional[str] = Field(None, max_length=10000, description="Optional ping data")

    @field_validator("data")
    @classmethod
    def sanitize_data(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize ping data to prevent injection attacks."""
        if v is not None:
            # Remove null bytes and control characters except newlines/tabs
            v = ''.join(char for char in v if char.isprintable() or char in '\n\t')
        return v


class CreateAlertTopicRequest(BaseModel):
    """Request to create an SNS alert topic."""

    name: str = Field(..., min_length=1, max_length=100, description="Topic name")
    display_name: Optional[str] = Field(None, max_length=100, description="Human-readable topic name")
    shared: bool = Field(False, description="Whether this topic can be shared across teams")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace")
        # SNS topic names must be alphanumeric with hyphens and underscores
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v.strip()):
            raise ValueError("name can only contain letters, numbers, hyphens, and underscores")
        return v.strip()


class SubscribeAlertTopicRequest(BaseModel):
    """Request to subscribe to an alert topic."""

    protocol: str = Field(..., description="Subscription protocol (email, sms, https)")
    endpoint: str = Field(..., min_length=1, max_length=500, description="Subscription endpoint")

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        allowed_protocols = ["email", "sms", "https"]
        if v.lower() not in allowed_protocols:
            raise ValueError(f"protocol must be one of: {', '.join(allowed_protocols)}")
        return v.lower()

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str, info) -> str:
        """Validate endpoint based on protocol."""
        protocol = info.data.get("protocol", "").lower()
        
        if protocol == "email":
            # Basic email validation
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError("Invalid email address format")
        elif protocol == "https":
            # Basic HTTPS URL validation
            if not re.match(r'^https://[a-zA-Z0-9.-]+', v):
                raise ValueError("Invalid HTTPS URL format")
        elif protocol == "sms":
            # Basic phone number validation (E.164 format)
            if not re.match(r'^\+[1-9]\d{1,14}$', v):
                raise ValueError("Invalid phone number format (use E.164 format: +1234567890)")
        
        return v
