"""OIDC token validation for Cloud Run internal endpoints.

Validates JWT tokens issued by Google Cloud IAM for Cloud Scheduler calls to internal endpoints.
"""
import os
import json
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from starlette.requests import Request

import jwt
import httpx
from cachetools import TTLCache
from cryptography import x509
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, InvalidIssuerError

logger = logging.getLogger(__name__)

# TTL cache: max 1 entry, expires after 1 hour (3600 seconds)
_google_certs_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)


class OIDCValidationError(Exception):
    """Base exception for OIDC validation errors."""
    pass


class InvalidTokenSignatureError(OIDCValidationError):
    """Token signature is invalid or key is missing."""
    pass


class TokenExpiredError(OIDCValidationError):
    """Token has expired."""
    pass


class InvalidAudienceError(OIDCValidationError):
    """Token audience does not match expected value."""
    pass


class InvalidIssuerError(OIDCValidationError):
    """Token issuer is not Google Cloud."""
    pass


class InvalidServiceAccountError(OIDCValidationError):
    """Token service account email does not match expected value."""
    pass


def _load_public_key(cert_str: str):
    """Load a public key from a PEM public key or x509 certificate string."""
    cert_pem = cert_str if cert_str.startswith("-----BEGIN") else (
        f"-----BEGIN CERTIFICATE-----\n{cert_str}\n-----END CERTIFICATE-----\n"
    )
    pem_bytes = cert_pem.encode("utf-8")

    try:
        return load_pem_public_key(pem_bytes)
    except ValueError:
        certificate = x509.load_pem_x509_certificate(pem_bytes)
        return certificate.public_key()


def _get_google_certs() -> Dict[str, str]:
    """Fetch Google's public OIDC signing certificates.

    Cached with a 1-hour TTL via cachetools.TTLCache.
    """
    _CACHE_KEY = "certs"
    cached = _google_certs_cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                "https://www.googleapis.com/oauth2/v1/certs"
            )
            response.raise_for_status()
            certs = response.json()
            _google_certs_cache[_CACHE_KEY] = certs
            return certs
    except Exception as e:
        logger.error(f"Failed to fetch Google OIDC certificates: {e}")
        raise OIDCValidationError("Unable to fetch Google OIDC certificates")


def invalidate_google_certs_cache() -> None:
    """Invalidate the cached Google OIDC certificates (for testing/rotation)."""
    _google_certs_cache.clear()


def validate_oidc_token(
    token: str,
    expected_audience: str | list[str],
    expected_service_account: Optional[str] = None,
) -> Dict:
    """Validate an OIDC token issued by Google Cloud.

    Args:
        token: JWT token string (from Authorization header, without "Bearer " prefix)
        expected_audience: Expected token audience (usually the Cloud Run service URL)
        expected_service_account: Optional email of the expected service account

    Returns:
        Decoded token claims

    Raises:
        InvalidTokenSignatureError: Token signature is invalid
        TokenExpiredError: Token has expired
        InvalidAudienceError: Token audience doesn't match
        InvalidIssuerError: Token issuer is not Google Cloud
        InvalidServiceAccountError: Service account doesn't match
        OIDCValidationError: Other validation errors
    """

    try:
        if isinstance(expected_audience, str):
            audience_values = [expected_audience]
        else:
            audience_values = list(expected_audience)

        normalized_audiences = []
        for audience in audience_values:
            normalized = audience.rstrip("/")
            if normalized not in normalized_audiences:
                normalized_audiences.append(normalized)
            with_slash = f"{normalized}/"
            if with_slash not in normalized_audiences:
                normalized_audiences.append(with_slash)

        # Get Google's public certificates for accounts.google.com issued ID tokens
        certs = _get_google_certs()

        # Decode the JWT header to get the key ID
        unverified_header = jwt.get_unverified_header(token)
        key_id = unverified_header.get("kid")

        if not key_id or key_id not in certs:
            raise InvalidTokenSignatureError(f"Token key ID '{key_id}' not found in Google certificates")

        # Get the certificate and normalize it to a public key object
        cert_str = certs[key_id]
        public_key = _load_public_key(cert_str)

        # Decode and verify the token
        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=normalized_audiences,
                issuer="https://accounts.google.com",
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )
        except ExpiredSignatureError as e:
            raise TokenExpiredError(f"Token has expired: {e}")
        except jwt.InvalidAudienceError as e:
            if not expected_service_account:
                raise InvalidAudienceError(f"Token audience mismatch: {e}")

            try:
                claims = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    issuer="https://accounts.google.com",
                    options={
                        "verify_exp": True,
                        "verify_aud": False,
                        "verify_iss": True,
                    }
                )
                logger.warning(
                    "Accepting OIDC token with mismatched audience because service account validation is enabled"
                )
            except InvalidTokenError:
                raise InvalidAudienceError(f"Token audience mismatch: {e}")
        except jwt.InvalidIssuerError as e:
            raise InvalidIssuerError(f"Invalid token issuer: {e}")
        except InvalidTokenError as e:
            raise InvalidTokenSignatureError(f"Token signature verification failed: {e}")

        # Verify service account email if provided
        if expected_service_account:
            token_email = claims.get("email")
            if token_email != expected_service_account:
                raise InvalidServiceAccountError(
                    f"Token service account '{token_email}' does not match expected '{expected_service_account}'"
                )

        return claims

    except OIDCValidationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating OIDC token: {e}")
        raise OIDCValidationError(f"Token validation failed: {e}")


def get_cloud_run_url(request: Optional[Request] = None) -> str:
    """Get the Cloud Run service URL for OIDC audience validation.

    Resolution order:
    1. Explicit environment variables set by config/tests
    2. The incoming request base URL when handling a live request
    """
    url = os.getenv("K_SERVICE_URL") or os.getenv("CLOUD_RUN_URL")
    if url:
        return url.rstrip("/")

    if request is not None:
        return str(request.base_url).rstrip("/")

    raise ValueError("Cloud Run service URL could not be determined")


def get_expected_scheduler_sa() -> Optional[str]:
    """Get the expected Cloud Scheduler service account email from environment.

    This should be set via CLOUD_SCHEDULER_SA or similar configuration.
    If not set, service account validation is skipped.
    """
    return os.getenv("CLOUD_SCHEDULER_SA")
