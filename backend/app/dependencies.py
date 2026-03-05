"""FastAPI dependencies for auth and database access."""
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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    """Validate JWT token and return authenticated user."""
    try:
        print(f"DEBUG: Received token: {credentials.credentials[:50]}...")
        
        # Verify JWT token
        claims = await verify_jwt_token(credentials.credentials)
        print(f"DEBUG: JWT claims: {claims}")
        
        # Extract user info
        user_id, email, name, email_verified = extract_user_info(claims)
        print(f"DEBUG: Extracted user info - ID: {user_id}, Email: {email}, Name: {name}")
        
        # Check domain allowlist - temporarily disabled for debugging
        # if not check_domain_allowed(email):
        #     raise ForbiddenError("Email domain not allowed")
        
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
