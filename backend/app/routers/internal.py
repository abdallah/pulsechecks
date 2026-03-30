"""Internal endpoints called by Cloud Scheduler (OIDC-protected)."""
import os
from fastapi import APIRouter, HTTPException, Request, status

from ..db.factory import create_db_client
from ..logging_config import get_logger
from ..handlers import _late_detector_impl
from ..scheduler import poll_http_checks

logger = get_logger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


async def _verify_oidc(request: Request):
    """Verify Cloud Scheduler OIDC token (skip in debug/local)."""
    if os.getenv("DEBUG", "").lower() in ("1", "true"):
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing OIDC token")
    # On Cloud Run, the platform validates the OIDC token before it reaches the app.
    # If we're here, the request already passed Cloud Run's IAM check.


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
