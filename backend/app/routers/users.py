"""User endpoints."""
import sys
try:
    from importlib.metadata import version, distributions
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import version, distributions
from fastapi import APIRouter, HTTPException, status

from ..dependencies import AuthUser, Database
from ..models import UserResponse, User, TeamMember, Role
from ..utils import get_iso_timestamp

router = APIRouter(prefix="/me", tags=["users"])


@router.get("/debug/versions")
async def get_runtime_versions():
    """Debug endpoint to check installed package versions."""
    try:
        versions = {}
        packages = ['aioboto3', 'aiobotocore', 'boto3', 'botocore']
        
        for package in packages:
            try:
                pkg_version = version(package)
                versions[package] = pkg_version
            except Exception:
                versions[package] = "not installed"
        
        versions['python'] = sys.version
        return {"versions": versions}
    except Exception as e:
        return {"error": str(e)}


@router.get("", response_model=UserResponse)
async def get_current_user_profile(
    current_user: AuthUser,
    db: Database,
) -> UserResponse:
    """Get current user profile."""
    user = await db.get_user(current_user.user_id)

    if not user:
        # Create user profile on first access
        from datetime import datetime, timezone
        from ..models.entities import User
        
        now = datetime.now(timezone.utc).isoformat()
        user = User(
            user_id=current_user.user_id,
            email=current_user.email,
            name=current_user.name,
            created_at=now,
            last_login_at=now,
        )
        await db.create_user(user)
        
        # Process any pending invitations for this email
        pending_invitations = await db.get_pending_invitations_for_email(current_user.email)
        for invitation in pending_invitations:
            # Add user to the team
            member = TeamMember(
                team_id=invitation.team_id,
                user_id=current_user.user_id,
                role=invitation.role,
                joined_at=get_iso_timestamp(),
            )
            await db.add_team_member(member)
            
            # Remove the pending invitation
            await db.delete_pending_invitation(invitation.email, invitation.team_id)

    return UserResponse(
        userId=user.user_id,
        email=user.email,
        name=user.name,
        createdAt=user.created_at,
        lastLoginAt=user.last_login_at,
    )
