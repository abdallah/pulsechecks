"""API token management endpoints."""
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from ..dependencies import AuthUser, Database, check_team_access
from ..models import Permission
from ..utils import get_iso_timestamp
from ..utils.token_security import timing_safe_compare, validate_token_entropy, validate_token_format
from ..audit import record_audit

router = APIRouter(prefix="/teams/{team_id}/api-tokens", tags=["api-tokens"])

COLLECTION = "api_tokens"


def _generate_token() -> str:
    """Generate a new API token: pc_ + 64 hex chars."""
    return "pc_" + os.urandom(32).hex()


def _hash_token(token: str) -> str:
    """Hash token using SHA256. Always use with timing_safe_compare()."""
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_token_creation(token: str) -> tuple[bool, str]:
    """Validate token has proper format and entropy."""
    # Check format
    is_valid, reason = validate_token_format(token)
    if not is_valid:
        return False, reason
    
    # Check entropy (token from os.urandom is cryptographically secure)
    # Extract hex part and convert to bytes
    hex_part = token[3:]  # Remove 'pc_' prefix
    token_bytes = bytes.fromhex(hex_part)
    is_valid, reason = validate_token_entropy(token_bytes, min_bytes=32)
    
    return is_valid, reason


@router.post("", response_model=Dict[str, Any])
async def create_api_token(
    team_id: str,
    request: Dict[str, Any],
    current_user: AuthUser,
    db: Database,
) -> Dict[str, Any]:
    """Create a new API token. Returns plaintext token once."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    name = request.get("name", "").strip()
    if not name:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="name is required")

    token = _generate_token()
    
    # Validate token entropy and format
    is_valid, reason = _validate_token_creation(token)
    if not is_valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Token generation failed: {reason}")
    
    token_id = str(uuid.uuid4())
    now = get_iso_timestamp()

    doc: Dict[str, Any] = {
        "token_id": token_id,
        "team_id": team_id,
        "user_id": current_user.user_id,
        "name": name,
        "token_hash": _hash_token(token),
        "created_at": now,
        "last_used_at": None,
        "expires_at": request.get("expires_at"),
    }

    # Store in Firestore
    col = db.db.collection(COLLECTION)
    await col.document(token_id).set(doc)
    await record_audit(db, team_id, current_user, "token.created", "token", token_id, name)

    return {**doc, "token": token}


@router.get("", response_model=List[Dict[str, Any]])
async def list_api_tokens(
    team_id: str,
    current_user: AuthUser,
    db: Database,
) -> List[Dict[str, Any]]:
    """List API tokens for a team (never returns plaintext token)."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    col = db.db.collection(COLLECTION)
    docs = col.where("team_id", "==", team_id)
    results = []
    async for doc in docs.stream():
        data = doc.to_dict()
        results.append({
            "token_id": data["token_id"],
            "name": data["name"],
            "created_at": data["created_at"],
            "last_used_at": data.get("last_used_at"),
            "expires_at": data.get("expires_at"),
            "user_id": data["user_id"],
        })
    return results


@router.delete("/{token_id}", response_model=Dict[str, Any])
async def revoke_api_token(
    team_id: str,
    token_id: str,
    current_user: AuthUser,
    db: Database,
) -> Dict[str, Any]:
    """Revoke an API token."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    col = db.db.collection(COLLECTION)
    doc_ref = col.document(token_id)
    doc = await doc_ref.get()

    if not doc.exists or doc.to_dict().get("team_id") != team_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Token not found")

    await doc_ref.delete()
    await record_audit(db, team_id, current_user, "token.revoked", "token", token_id, doc.to_dict().get("name"))
    return {"deleted": True, "token_id": token_id}
