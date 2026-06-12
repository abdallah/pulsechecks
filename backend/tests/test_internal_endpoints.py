"""Integration tests for internal endpoints with OIDC validation."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import jwt

from app.routers.internal import router
from app.oidc_validator import (
    TokenExpiredError,
    InvalidTokenSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidServiceAccountError,
    OIDCValidationError,
)


# Generate test RSA key pair
def _generate_test_key_pair():
    """Generate RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return private_pem, public_pem


def _extract_cert_from_pem(pem_str: str) -> str:
    """Extract certificate from PEM format."""
    lines = pem_str.split('\n')
    cert_lines = [line for line in lines
                  if line and not line.startswith('-----')]
    return ''.join(cert_lines)


def _create_test_token(
    private_key_pem: str,
    audience: str = "https://myservice-123456.a.run.app",
    issuer: str = "https://accounts.google.com",
    service_account: str = "my-scheduler@my-project.iam.gserviceaccount.com",
    expired: bool = False,
    wrong_audience: str = None,
    wrong_issuer: str = None,
    wrong_email: str = None,
    key_id: str = "test-key-id-1",
) -> str:
    """Create a test JWT token."""
    now = datetime.now(timezone.utc)

    if expired:
        exp_time = now - timedelta(hours=1)
    else:
        exp_time = now + timedelta(hours=1)

    payload = {
        "iss": wrong_issuer or issuer,
        "aud": wrong_audience or audience,
        "email": wrong_email or service_account,
        "email_verified": True,
        "iat": int(now.timestamp()),
        "exp": int(exp_time.timestamp()),
        "sub": "1234567890",
    }

    headers = {
        "kid": key_id,
        "alg": "RS256",
    }

    token = jwt.encode(payload, private_key_pem, algorithm="RS256", headers=headers)
    return token


@pytest.fixture
def app():
    """Create test FastAPI application with internal router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_keys():
    """Generate test RSA keys."""
    return _generate_test_key_pair()


@pytest.fixture
def mock_cloud_run_env(monkeypatch):
    """Mock Cloud Run environment variables."""
    monkeypatch.setenv("K_SERVICE_URL", "https://myservice-123456.a.run.app")
    monkeypatch.setenv("CLOUD_SCHEDULER_SA", "my-scheduler@my-project.iam.gserviceaccount.com")
    monkeypatch.setenv("DEBUG", "false")


class TestInternalLateDetectionEndpoint:
    """Test /internal/late-detection endpoint."""

    def test_valid_token_success(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with valid token."""
        private_key_pem, public_pem = test_keys
        cert_b64 = _extract_cert_from_pem(public_pem)

        token = _create_test_token(private_key_pem)
        mock_certs = {"test-key-id-1": cert_b64}

        # Mock Google certs and the late detector implementation
        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.return_value = {"email": "test@example.com"}

            with patch('app.routers.internal._late_detector_impl', new_callable=AsyncMock) as mock_detector:
                mock_detector.return_value = {"status": "ok", "checks_processed": 5}

                response = client.post(
                    "/internal/late-detection",
                    headers={"Authorization": f"Bearer {token}"}
                )

        assert response.status_code == 200
        assert "status" in response.json()

    def test_missing_authorization_header(self, client, mock_cloud_run_env):
        """Test late-detection endpoint with missing Authorization header."""
        response = client.post("/internal/late-detection")

        assert response.status_code == 401
        assert "Authorization" in response.json()["detail"]

    def test_invalid_authorization_header_format(self, client, mock_cloud_run_env):
        """Test late-detection endpoint with invalid Authorization header format."""
        response = client.post(
            "/internal/late-detection",
            headers={"Authorization": "InvalidFormat token123"}
        )

        assert response.status_code == 401
        assert "Authorization" in response.json()["detail"]

    def test_expired_token(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with expired token."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem, expired=True)

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = TokenExpiredError("Token has expired")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_invalid_token_signature(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with invalid token signature."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem)

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidTokenSignatureError("Token signature verification failed")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401
        assert "signature" in response.json()["detail"].lower()

    def test_wrong_audience(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with token for wrong audience."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem, wrong_audience="https://wrong-service.run.app")

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidAudienceError("Token audience mismatch")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401
        assert "audience" in response.json()["detail"].lower()

    def test_wrong_issuer(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with token from wrong issuer."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem, wrong_issuer="https://wrong-issuer.com")

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidIssuerError("Invalid token issuer")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401
        assert "issuer" in response.json()["detail"].lower()

    def test_wrong_service_account(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with wrong service account."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(
            private_key_pem,
            wrong_email="wrong-sa@project.iam.gserviceaccount.com"
        )

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidServiceAccountError("Service account not authorized")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    def test_generic_validation_error(self, client, test_keys, mock_cloud_run_env):
        """Test late-detection endpoint with generic validation error."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem)

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = OIDCValidationError("Unexpected validation error")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401

    def test_debug_mode_skips_validation(self, client, test_keys, monkeypatch):
        """Test that debug mode still requires auth."""
        monkeypatch.setenv("DEBUG", "true")

        with patch('app.routers.internal._late_detector_impl', new_callable=AsyncMock) as mock_detector:
            mock_detector.return_value = {"status": "ok"}

            response = client.post(
                "/internal/late-detection",
                headers={}  # No Authorization header provided
            )

        assert response.status_code == 401

    def test_debug_mode_with_1_value(self, client, test_keys, monkeypatch):
        """Test debug mode with DEBUG=1."""
        monkeypatch.setenv("DEBUG", "1")

        with patch('app.routers.internal._late_detector_impl', new_callable=AsyncMock) as mock_detector:
            mock_detector.return_value = {"status": "ok"}

            response = client.post(
                "/internal/late-detection",
                headers={}
            )

        assert response.status_code == 401


class TestInternalHttpPollEndpoint:
    """Test /internal/http-poll endpoint."""

    def test_valid_token_success(self, client, test_keys, mock_cloud_run_env):
        """Test http-poll endpoint with valid token."""
        private_key_pem, public_pem = test_keys
        cert_b64 = _extract_cert_from_pem(public_pem)

        token = _create_test_token(private_key_pem)
        mock_certs = {"test-key-id-1": cert_b64}

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.return_value = {"email": "test@example.com"}

            with patch('app.routers.internal.poll_http_checks', new_callable=AsyncMock) as mock_poll:
                mock_poll.return_value = None

                response = client.post(
                    "/internal/http-poll",
                    headers={"Authorization": f"Bearer {token}"}
                )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_missing_authorization_header(self, client, mock_cloud_run_env):
        """Test http-poll endpoint with missing Authorization header."""
        response = client.post("/internal/http-poll")

        assert response.status_code == 401
        assert "Authorization" in response.json()["detail"]

    def test_expired_token(self, client, test_keys, mock_cloud_run_env):
        """Test http-poll endpoint with expired token."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem, expired=True)

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = TokenExpiredError("Token has expired")

            response = client.post(
                "/internal/http-poll",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401

    def test_invalid_token_signature(self, client, test_keys, mock_cloud_run_env):
        """Test http-poll endpoint with invalid token signature."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem)

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidTokenSignatureError("Token signature verification failed")

            response = client.post(
                "/internal/http-poll",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401

    def test_wrong_audience(self, client, test_keys, mock_cloud_run_env):
        """Test http-poll endpoint with token for wrong audience."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem, wrong_audience="https://wrong-service.run.app")

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidAudienceError("Token audience mismatch")

            response = client.post(
                "/internal/http-poll",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401

    def test_wrong_issuer(self, client, test_keys, mock_cloud_run_env):
        """Test http-poll endpoint with token from wrong issuer."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(private_key_pem, wrong_issuer="https://wrong-issuer.com")

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidIssuerError("Invalid token issuer")

            response = client.post(
                "/internal/http-poll",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401

    def test_wrong_service_account(self, client, test_keys, mock_cloud_run_env):
        """Test http-poll endpoint with wrong service account."""
        private_key_pem, public_pem = test_keys

        token = _create_test_token(
            private_key_pem,
            wrong_email="wrong-sa@project.iam.gserviceaccount.com"
        )

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.side_effect = InvalidServiceAccountError("Service account not authorized")

            response = client.post(
                "/internal/http-poll",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 403

    def test_debug_mode_skips_validation(self, client, test_keys, monkeypatch):
        """Test that debug mode still requires auth for http-poll."""
        monkeypatch.setenv("DEBUG", "true")

        with patch('app.routers.internal.poll_http_checks', new_callable=AsyncMock) as mock_poll:
            mock_poll.return_value = None

            response = client.post(
                "/internal/http-poll",
                headers={}  # No Authorization header provided
            )

        assert response.status_code == 401


class TestInternalEndpointErrorHandling:
    """Test error handling for internal endpoints."""

    def test_request_url_fallback_when_env_missing(self, client, test_keys, monkeypatch):
        """Test that internal endpoints can derive audience from the request URL."""
        monkeypatch.delenv("K_SERVICE_URL", raising=False)
        monkeypatch.delenv("CLOUD_RUN_URL", raising=False)
        monkeypatch.setenv("DEBUG", "false")

        private_key_pem, public_pem = test_keys
        token = _create_test_token(private_key_pem)

        with patch('app.routers.internal.validate_oidc_token') as mock_validate:
            mock_validate.return_value = {"email": "test@example.com"}

            with patch('app.routers.internal._late_detector_impl', new_callable=AsyncMock) as mock_detector:
                mock_detector.return_value = {"ok": True}

                response = client.post(
                    "/internal/late-detection",
                    headers={"Authorization": f"Bearer {token}"}
                )

        assert response.status_code == 200
        mock_validate.assert_called_once()
        assert mock_validate.call_args.kwargs["expected_audience"] == [
            "http://testserver",
            "http://testserver/internal/late-detection",
        ]

    def test_missing_cloud_run_url_config(self, client, test_keys, monkeypatch):
        """Test error when K_SERVICE_URL is not configured."""
        monkeypatch.delenv("K_SERVICE_URL", raising=False)
        monkeypatch.setenv("DEBUG", "false")

        private_key_pem, public_pem = test_keys
        token = _create_test_token(private_key_pem)

        with patch('app.routers.internal.get_cloud_run_url') as mock_get_url:
            mock_get_url.side_effect = ValueError("K_SERVICE_URL not set")

            response = client.post(
                "/internal/late-detection",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 500
        assert "configuration" in response.json()["detail"].lower()

    def test_bearer_prefix_case_insensitive(self, client, test_keys, mock_cloud_run_env):
        """Test Bearer token prefix handling."""
        private_key_pem, public_pem = test_keys
        token = _create_test_token(private_key_pem)

        # Test with lowercase 'bearer' - should fail (case sensitive)
        response = client.post(
            "/internal/late-detection",
            headers={"Authorization": f"bearer {token}"}
        )

        assert response.status_code == 401

    def test_empty_bearer_token(self, client, mock_cloud_run_env):
        """Test with empty Bearer token."""
        response = client.post(
            "/internal/late-detection",
            headers={"Authorization": "Bearer "}
        )

        # Should fail token validation, not format validation
        assert response.status_code == 401
