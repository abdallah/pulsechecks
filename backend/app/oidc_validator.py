"""OIDC token validation for Cloud Run internal endpoints.

Validates JWT tokens issued by Google Cloud IAM for Cloud Scheduler calls to internal endpoints.
"""
import os
import json
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from functools import lru_cache

import jwt
import httpx
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, InvalidIssuerError

logger = logging.getLogger(__name__)


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


@lru_cache(maxsize=1)
def _get_google_certs() -> Dict[str, str]:
    """Fetch Google's public OIDC signing certificates.
    
    These are cached for 1 hour by default.
    """
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
            )
            response.raise_for_status()
            certs = response.json()
            return certs
    except Exception as e:
        logger.error(f"Failed to fetch Google OIDC certificates: {e}")
        raise OIDCValidationError("Unable to fetch Google OIDC certificates")


def validate_oidc_token(
    token: str,
    expected_audience: str,
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
        # Get Google's public certificates
        certs = _get_google_certs()
        
        # Decode the JWT header to get the key ID
        unverified_header = jwt.get_unverified_header(token)
        key_id = unverified_header.get("kid")
        
        if not key_id or key_id not in certs:
            raise InvalidTokenSignatureError(f"Token key ID '{key_id}' not found in Google certificates")
        
        # Get the certificate and convert to PEM format if needed
        cert_str = certs[key_id]
        # Check if it's already in PEM format
        if cert_str.startswith("-----BEGIN"):
            cert_pem = cert_str
        else:
            # It's base64 encoded, wrap it in PEM headers
            cert_pem = f"-----BEGIN CERTIFICATE-----\n{cert_str}\n-----END CERTIFICATE-----\n"
        
        # Decode and verify the token
        try:
            claims = jwt.decode(
                token,
                cert_pem,
                algorithms=["RS256"],
                audience=expected_audience,
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


def get_cloud_run_url() -> str:
    """Get the Cloud Run service URL from environment.
    
    In Cloud Run, the K_SERVICE_URL environment variable is set by the platform.
    """
    url = os.getenv("K_SERVICE_URL")
    if not url:
        raise ValueError("K_SERVICE_URL not set - not running on Cloud Run")
    return url


def get_expected_scheduler_sa() -> Optional[str]:
    """Get the expected Cloud Scheduler service account email from environment.
    
    This should be set via CLOUD_SCHEDULER_SA or similar configuration.
    If not set, service account validation is skipped.
    """
    return os.getenv("CLOUD_SCHEDULER_SA")
