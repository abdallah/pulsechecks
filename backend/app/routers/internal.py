"""Internal endpoints called by Cloud Scheduler (OIDC-protected)."""
import os
from fastapi import APIRouter, HTTPException, Request, status

from ..db.factory import create_db_client
from ..logging_config import get_logger
from ..handlers import _late_detector_impl
from ..scheduler import poll_http_checks
from ..oidc_validator import (
    validate_oidc_token,
    get_cloud_run_url,
    get_expected_scheduler_sa,
    OIDCValidationError,
    InvalidTokenSignatureError,
    TokenExpiredError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidServiceAccountError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


async def _verify_oidc(request: Request):
    """Verify Cloud Scheduler OIDC token.

    Validates:
    - Token signature (using Google's public certificates)
    - Token expiry
    - Token audience (must match Cloud Run service URL)
    - Service account email (if CLOUD_SCHEDULER_SA is configured)

    Raises HTTPException with appropriate 401/403 status codes.
    """
    # Internal endpoints must fail closed; DEBUG should never bypass auth.
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header on internal endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected 'Bearer <token>'"
        )

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        # Get expected audience (Cloud Run service URL)
        try:
            service_url = get_cloud_run_url(request)
            expected_audience = [service_url, str(request.url).rstrip("/")]
        except ValueError as e:
            logger.error("Cannot determine Cloud Run URL: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error"
            )

        # Get expected service account (optional)
        expected_service_account = get_expected_scheduler_sa()

        # Validate the OIDC token
        claims = validate_oidc_token(
            token,
            expected_audience=expected_audience,
            expected_service_account=expected_service_account,
        )

        logger.info("OIDC token validated successfully for internal scheduler call")

    except InvalidTokenSignatureError as e:
        logger.warning("Invalid token signature on internal endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature"
        )
    except TokenExpiredError as e:
        logger.warning("Expired token on internal endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except InvalidAudienceError as e:
        logger.warning("Invalid token audience on internal endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience does not match service"
        )
    except InvalidIssuerError as e:
        logger.warning("Invalid token issuer on internal endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer is not Google Cloud"
        )
    except InvalidServiceAccountError as e:
        logger.warning("Service account mismatch on internal endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service account not authorized"
        )
    except OIDCValidationError as e:
        logger.error("OIDC validation error on internal endpoint: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed"
        )


@router.post("/late-detection")
async def late_detection(request: Request):
    """Late detection endpoint called by Cloud Scheduler every 2 minutes."""
    await _verify_oidc(request)
    result = await _late_detector_impl({}, None)
    return result


@router.post("/http-poll")
async def http_poll(request: Request):
    """HTTP polling endpoint called by Cloud Scheduler every minute."""
    await _verify_oidc(request)
    await poll_http_checks()
    return {"ok": True}
