"""Application configuration using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Cloud provider selection
    cloud_provider: str = "aws"  # "aws" or "gcp"

    # AWS
    aws_region: str = "us-east-1"
    dynamodb_table: str = "Pulsechecks"

    # Cognito
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    # GCP
    gcp_project: str = ""
    gcp_region: str = "us-central1"
    firestore_database: str = "(default)"

    # Firebase (GCP auth)
    firebase_project_id: str = ""

    # Auth
    allowed_email_domains: str = ""
    # Override the auth provider independently of cloud_provider
    # ("firebase" | "cognito"; empty = derive from cloud_provider).
    # Used to run Firebase Auth on the AWS warm standby so both clouds
    # share one identity space (user_ids survive failover).
    auth_provider: str = ""

    # Application
    project_name: str = "pulsechecks"
    environment: str = "production"
    debug: bool = False
    ping_retention_days: int = 90

    # How many trailing X-Forwarded-For entries were appended by
    # infrastructure we trust. 0 = ignore XFF (use the socket peer, correct
    # on Lambda where API Gateway supplies the real source IP); 1 = Cloud Run
    # reached directly (Cloud Run appends the caller's IP); 2 = Cloud Run
    # behind the global HTTPS LB (GFE appends client-ip, lb-ip). Anything
    # earlier in the header is client-supplied and must not be trusted.
    trusted_proxy_hops: int = 0

    # Warm-standby mode: detect and mirror state, but do NOT deliver
    # alerts for sync-managed checks (the primary is alerting for them).
    # Native checks (e.g. sentinel watchers of the other cloud) still
    # alert normally. Promotion = flip this to false.
    standby_mode: bool = False

    # Cross-cloud definition sync (standby pulls from primary)
    sync_token: str = ""          # shared secret; empty disables export/import
    primary_export_url: str = ""  # e.g. https://api.example.com/internal/export-definitions

    # Dead-man's-switch: external heartbeat URL pinged after every
    # successful late-detection run. Point this at an independent
    # monitor (e.g. a healthchecks.io check) so you find out when
    # PulseChecks' own detection loop stops running.
    heartbeat_url: str = ""
    frontend_url: str = "https://pulsechecks.example.com"

    # SMTP (email alert channels — cloud-agnostic; use SES SMTP on AWS,
    # any provider (SendGrid, Mailgun, Workspace relay) on GCP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # e.g. "PulseChecks <alerts@example.com>"
    smtp_use_tls: bool = True

    # PostHog
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
