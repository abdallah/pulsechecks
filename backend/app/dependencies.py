"""FastAPI dependencies for auth and database access."""
import hashlib
import inspect
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


def _parse_api_token_expires_at(expires_at: object) -> datetime | None:
    """Parse an API token expiry timestamp, returning None for missing values.

    Any malformed non-empty value is treated as invalid so auth fails closed.
    """
    if expires_at in (None, ""):
        return None

    if isinstance(expires_at, datetime):
        dt = expires_at
    elif isinstance(expires_at, str):
        try:
            dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise UnauthorizedError("Invalid API token") from exc
    else:
        raise UnauthorizedError("Invalid API token")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_api_token_collection(db: DatabaseInterface):
    """Return the API token collection from whichever database wrapper is provided."""
    db_wrapper = getattr(db, "db", None)
    if db_wrapper is not None:
        collection = getattr(db_wrapper, "collection", None)
        if callable(collection):
            return collection("api_tokens")

    collection = getattr(db, "collection", None)
    if callable(collection):
        return collection("api_tokens")

    raise UnauthorizedError("Invalid API token")


async def _maybe_await(value):
    if inspect.isawaitable(value) and not inspect.isasyncgen(value):
        return await value
    return value


async def _resolve_api_token(token: str, db: DatabaseInterface) -> CurrentUser:
    """Look up a pc_ prefixed API token in Firestore and return the associated user."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        col = _get_api_token_collection(db)
        docs = col.where("token_hash", "==", token_hash)
        stream = await _maybe_await(docs.stream())
        async for doc in stream:
            data = doc.to_dict()
            if not isinstance(data, dict):
                raise UnauthorizedError("Invalid API token")

            expires_at = _parse_api_token_expires_at(data.get("expires_at"))
            if expires_at is not None and expires_at <= datetime.now(timezone.utc):
                raise UnauthorizedError("Invalid API token")

            try:
                token_id = data["token_id"]
                await col.document(token_id).update(
                    {"last_used_at": datetime.now(timezone.utc).isoformat()}
                )
            except Exception:
                # Usage tracking is best-effort; auth should still succeed.
                pass

            return CurrentUser(
                user_id=data["user_id"],
                email="",
                name=data.get("name", ""),
            )
    except UnauthorizedError:
        raise
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
        try:
            db = create_db_client()
            return await _resolve_api_token(raw, db)
        except UnauthorizedError:
            raise
        except Exception:
            raise UnauthorizedError("Invalid API token")

    try:
        # Verify JWT token
        claims = await verify_jwt_token(raw)
        # Extract user info
        user_id, email, name, email_verified = extract_user_info(claims)

        # Enforce email verification
        if not email_verified:
            raise UnauthorizedError("Email address not verified")

        # Check domain allowlist
        if not check_domain_allowed(email):
            raise ForbiddenError("Email domain not allowed")

        return CurrentUser(user_id=user_id, email=email, name=name)

    except InvalidTokenError as e:
        raise UnauthorizedError(f"Invalid token: {str(e)}")
    except ValueError as e:
        raise UnauthorizedError(f"Token validation error: {str(e)}")
    except (UnauthorizedError, ForbiddenError):
        raise
    except Exception:
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
