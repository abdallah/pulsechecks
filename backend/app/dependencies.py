"""FastAPI dependencies for auth and database access."""
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError

from .db import create_db_client, DatabaseInterface
from .models import Role, Permission
from .auth import verify_jwt_token, extract_user_info, check_domain_allowed
from .errors import UnauthorizedError, ForbiddenError, NotFoundError

security = HTTPBearer()

class CurrentUser:
    """Current authenticated user information."""
    def __init__(self, user_id: str, email: str, name: str):
        self.user_id = user_id
        self.email = email
        self.name = name


async def _resolve_api_token(token: str, db: DatabaseInterface) -> CurrentUser:
    """Look up a pc_ prefixed API token in Firestore and return the associated user."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        col = db.db.collection("api_tokens")
        docs = col.where("token_hash", "==", token_hash)
        async for doc in docs.stream():
            data = doc.to_dict()
            # Async fire-and-forget update of last_used_at
            asyncio.ensure_future(
                col.document(data["token_id"]).update(
                    {"last_used_at": datetime.now(timezone.utc).isoformat()}
                )
            )
            return CurrentUser(
                user_id=data["user_id"],
                email="",
                name=data.get("name", ""),
            )
    except Exception:
        pass
    raise UnauthorizedError("Invalid API token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    """Validate token and return authenticated user.

    Supports two token types:
    - pc_<hex>  — PulseChecks API token (looked up by SHA-256 hash in Firestore)
    - anything else — Firebase/Cognito JWT
    """
    raw = credentials.credentials

    if raw.startswith("pc_"):
        db = create_db_client()
        return await _resolve_api_token(raw, db)

    try:
        print(f"DEBUG: Received token: {raw[:50]}...")
        
        # Verify JWT token
        claims = await verify_jwt_token(raw)
        print(f"DEBUG: JWT claims: {claims}")
        
        # Extract user info
        user_id, email, name, email_verified = extract_user_info(claims)
        print(f"DEBUG: Extracted user info - ID: {user_id}, Email: {email}, Name: {name}")
        
        # Check domain allowlist
        if not check_domain_allowed(email):
            raise ForbiddenError("Email domain not allowed")
        
        return CurrentUser(user_id=user_id, email=email, name=name)
        
    except InvalidTokenError as e:
        print(f"DEBUG: InvalidTokenError: {str(e)}")
        raise UnauthorizedError(f"Invalid token: {str(e)}")
    except ValueError as e:
        print(f"DEBUG: ValueError: {str(e)}")
        raise UnauthorizedError(f"Token validation error: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Unexpected error: {str(e)}")
        raise UnauthorizedError("Authentication failed")

def get_db() -> DatabaseInterface:
    """Get database client instance (cloud-agnostic)."""
    return create_db_client()

async def check_team_access(
    team_id: str,
    current_user: CurrentUser,
    db: DatabaseInterface,
    required_permission: Permission = Permission.VIEW,
) -> Role:
    """
    Check if user has access to team with required permission.
    """
    # Get user's membership in the team
    membership = await db.get_team_member(team_id, current_user.user_id)
    
    if not membership:
        raise ForbiddenError("Access denied to team")
    
    # Check if user's role has required permission
    user_role = membership.role
    if not user_role.has_permission(required_permission):
        raise ForbiddenError("Insufficient permissions")
    
    return user_role

# Type aliases for convenience
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
Database = Annotated[DatabaseInterface, Depends(get_db)]
