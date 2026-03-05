"""Pytest configuration and shared fixtures."""
import pytest
import os


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for tests."""
    monkeypatch.setenv("DYNAMODB_TABLE", "Pulsechecks-Test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_TEST123456")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "test-client-id-12345")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "example.com")
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "false")


@pytest.fixture
def sample_user_data():
    """Sample user data for tests."""
    return {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
        "created_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_team_data():
    """Sample team data for tests."""
    return {
        "team_id": "test-team-123",
        "name": "Test Team",
        "created_at": "2025-01-01T00:00:00Z",
        "created_by": "test-user-123",
    }


@pytest.fixture
def sample_check_data():
    """Sample check data for tests."""
    return {
        "check_id": "test-check-123",
        "team_id": "test-team-123",
        "name": "Test Check",
        "token": "test-token-abc123",
        "period_seconds": 3600,
        "grace_seconds": 600,
        "status": "up",
        "created_at": "2025-01-01T00:00:00Z",
    }
