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

    # Application
    project_name: str = "pulsechecks"
    environment: str = "production"
    debug: bool = False
    frontend_url: str = "https://pulsechecks.example.com"

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
