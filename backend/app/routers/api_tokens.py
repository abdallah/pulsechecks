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

router = APIRouter(prefix="/teams/{team_id}/api-tokens", tags=["api-tokens"])

COLLECTION = "api_tokens"


def _generate_token() -> str:
    """Generate a new API token: pc_ + 64 hex chars."""
    return "pc_" + os.urandom(32).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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
    return {"deleted": True, "token_id": token_id}
