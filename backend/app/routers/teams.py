"""Team management endpoints."""
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from ..dependencies import AuthUser, Database, get_current_user, get_db, check_team_access, CurrentUser
from ..models import (
    CreateTeamRequest,
    TeamResponse,
    Role,
    Team,
    TeamMember,
    PendingInvitation,
    Permission,
)
from ..utils import generate_id, get_iso_timestamp
from ..logging_config import log_business_event

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    request: CreateTeamRequest,
    current_user: AuthUser,
    db: Database,
) -> TeamResponse:
    """Create a new team."""
    # Generate team ID
    team_id = generate_id()

    # Create team
    team = Team(
        team_id=team_id,
        name=request.name,
        created_at=get_iso_timestamp(),
        created_by=current_user.user_id,
    )
    await db.create_team(team)

    # Add creator as admin
    member = TeamMember(
        team_id=team_id,
        user_id=current_user.user_id,
        role=Role.ADMIN,
        joined_at=get_iso_timestamp(),
    )
    await db.add_team_member(member)

    return TeamResponse(
        teamId=team_id,
        name=request.name,
        role=Role.ADMIN,
        createdAt=team.created_at,
    )


@router.get("")
async def list_user_teams(
    current_user: AuthUser,
    db: Database,
):
    """List all teams for the current user."""
    teams_with_roles = await db.list_user_teams(current_user.user_id)

    return [
        {
            "teamId": item["team"].team_id,
            "name": item["team"].name,
            "role": item["role"],
            "createdAt": item["team"].created_at,
        }
        for item in teams_with_roles
    ]


@router.get("/{team_id}")
async def get_team(
    team_id: str,
    current_user: AuthUser,
    db: Database,
):
    """Get team details."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {
        "teamId": team.team_id,
        "name": team.name,
        "createdAt": team.created_at,
        "createdBy": team.created_by,
    }


@router.patch("/{team_id}")
async def update_team(
    team_id: str,
    request: dict,  # {"name": "New Team Name"}
    current_user: AuthUser,
    db: Database,
):
    """Update team details (admin only)."""
    await check_team_access(team_id, current_user, db, Permission.ADMIN)
    
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Update team name if provided
    new_name = request.get("name", "").strip()
    if new_name:
        if len(new_name) > 100:
            raise HTTPException(status_code=400, detail="Team name too long (max 100 characters)")
        
        old_name = team.name
        team.name = new_name
        await db.update_team(team)
        
        log_business_event('team_updated', 
            team_id=team_id, 
            user_id=current_user.user_id,
            old_name=old_name,
            new_name=new_name
        )
    
    return {"ok": True, "message": "Team updated successfully", "name": team.name}


@router.get("/{team_id}/members")
async def list_team_members(
    team_id: str,
    current_user: AuthUser,
    db: Database,
):
    """List all members of a team."""
    # Check if user is a member of the team
    member = await db.get_team_member(team_id, current_user.user_id)
    if not member:
        raise HTTPException(status_code=403, detail="Access denied")
    
    members = await db.list_team_members(team_id)
    
    # Get user details for each member
    result = []
    for member in members:
        user = await db.get_user(member.user_id)
        result.append({
            "userId": member.user_id,
            "email": user.email if user else "unknown",
            "name": user.name if user else "Unknown User",
            "role": member.role.value,
            "joinedAt": member.joined_at,
            "status": "active"
        })
    
    pending_invitations = await db.list_pending_invitations_for_team(team_id)
    for invitation in pending_invitations:
        result.append({
            "userId": None,
            "email": invitation.email,
            "name": "Pending User",
            "role": invitation.role.value,
            "joinedAt": invitation.invited_at,
            "status": "pending"
        })
    
    return result


@router.post("/{team_id}/members")
async def add_team_member(
    team_id: str,
    request: dict,  # {"email": "user@example.com", "role": "member"}
    current_user: AuthUser,
    db: Database,
):
    """Add a member to a team by email."""
    # Check if user is admin of the team
    member = await db.get_team_member(team_id, current_user.user_id)
    if not member or member.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    email = request.get("email")
    role_str = request.get("role", "member")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Find user by email
    user = await db.get_user_by_email(email)
    
    if user:
        # User exists - add them directly
        # Check if user is already a member
        existing_member = await db.get_team_member(team_id, user.user_id)
        if existing_member:
            raise HTTPException(status_code=400, detail="User is already a team member")
        
        # Add member
        try:
            role = Role(role_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        new_member = TeamMember(
            team_id=team_id,
            user_id=user.user_id,
            role=role,
            joined_at=get_iso_timestamp(),
        )
        await db.add_team_member(new_member)
        
        return {
            "userId": user.user_id,
            "email": user.email,
            "name": user.name,
            "role": role.value,
            "joinedAt": new_member.joined_at,
            "status": "active"
        }
    else:
        # User doesn't exist - create pending invitation
        try:
            role = Role(role_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        # Check if invitation already exists
        existing_invitations = await db.get_pending_invitations_for_email(email)
        for inv in existing_invitations:
            if inv.team_id == team_id:
                raise HTTPException(status_code=400, detail="User already has a pending invitation to this team")
        
        # Create pending invitation
        invitation = PendingInvitation(
            email=email,
            team_id=team_id,
            role=role,
            invited_by=current_user.user_id,
            invited_at=get_iso_timestamp(),
        )
        await db.create_pending_invitation(invitation)
        
        return {
            "userId": None,
            "email": email,
            "name": "Pending User",
            "role": role.value,
            "joinedAt": invitation.invited_at,
            "status": "pending"
        }


@router.delete("/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: str,
    user_id: str,
    current_user: AuthUser,
    db: Database,
):
    """Remove a member from a team."""
    # Check if user is admin of the team
    member = await db.get_team_member(team_id, current_user.user_id)
    if not member or member.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Can't remove yourself if you're the only admin
    if user_id == current_user.user_id:
        members = await db.list_team_members(team_id)
        admin_count = sum(1 for m in members if m.role == Role.ADMIN)
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin")
    
    # Remove member
    await db.remove_team_member(team_id, user_id)
    
    return {"message": "Member removed successfully"}


@router.patch("/{team_id}/members/{user_id}")
async def update_team_member_role(
    team_id: str,
    user_id: str,
    request: dict,  # {"role": "admin"}
    current_user: AuthUser,
    db: Database,
):
    """Update a team member's role."""
    # Check if user is admin of the team
    member = await db.get_team_member(team_id, current_user.user_id)
    if not member or member.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_role_str = request.get("role")
    if not new_role_str:
        raise HTTPException(status_code=400, detail="Role is required")
    
    try:
        new_role = Role(new_role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Can't demote yourself if you're the only admin
    if user_id == current_user.user_id and new_role != Role.ADMIN:
        members = await db.list_team_members(team_id)
        admin_count = sum(1 for m in members if m.role == Role.ADMIN)
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last admin")
    
    # Update member role
    await db.update_team_member_role(team_id, user_id, new_role)
    
    return {"message": "Member role updated successfully"}


@router.delete("/{team_id}/invitations/{email}")
async def delete_team_invitation(
    team_id: str,
    email: str,
    current_user: AuthUser,
    db: Database,
):
    """Delete a pending team invitation."""
    # Check if user is admin of the team
    member = await db.get_team_member(team_id, current_user.user_id)
    if not member or member.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Delete the invitation
    await db.delete_pending_invitation(email, team_id)
    
    return {"message": "Invitation deleted successfully"}


@router.patch("/{team_id}/mattermost")
async def update_team_mattermost_webhook(
    team_id: str,
    request: dict,
    current_user: AuthUser,
    db: Database,
):
    """Update team Mattermost webhook URL (admin only)."""
    # Check team access with admin permission
    await check_team_access(team_id, current_user, db, Permission.ADMIN)
    
    webhook_url = request.get("webhook_url")
    
    # Validate webhook URL format
    if webhook_url and not webhook_url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=422,
            detail="Invalid webhook URL format"
        )
    
    # Update team with Mattermost webhook URL
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Update team (this would need to be implemented in DynamoDB client)
    # For now, we'll assume the update method exists
    await db.update_team_mattermost_webhook(team_id, webhook_url)
    
    log_business_event('team_mattermost_updated', 
        team_id=team_id, 
        user_id=current_user.user_id,
        webhook_configured=bool(webhook_url)
    )
    
    return {"ok": True, "message": "Mattermost webhook updated"}


@router.get("/{team_id}/mattermost")
async def get_team_mattermost_webhook(
    team_id: str,
    current_user: AuthUser,
    db: Database,
):
    """Get team Mattermost webhook URL (admin only)."""
    # Check team access with admin permission
    await check_team_access(team_id, current_user, db, Permission.ADMIN)
    
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {
        "webhook_url": team.mattermost_webhook_url,
        "configured": bool(team.mattermost_webhook_url)
    }


@router.get("/{team_id}/mattermost/webhooks")
async def get_team_mattermost_webhooks(
    team_id: str,
    current_user: AuthUser,
    db: Database,
):
    """Get team Mattermost webhooks."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Return both new and legacy webhooks
    webhooks = team.mattermost_webhooks or []
    if team.mattermost_webhook_url and team.mattermost_webhook_url not in webhooks:
        webhooks.append(team.mattermost_webhook_url)
    
    return {"webhooks": webhooks}


@router.post("/{team_id}/mattermost/webhooks")
async def add_team_mattermost_webhook(
    team_id: str,
    request: dict,  # {"webhook_url": "https://..."}
    current_user: AuthUser,
    db: Database,
):
    """Add a Mattermost webhook to team."""
    await check_team_access(team_id, current_user, db, Permission.ADMIN)
    
    webhook_url = request.get("webhook_url")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required")
    
    if not webhook_url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=422,
            detail="Webhook URL must start with http:// or https://"
        )
    
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    webhooks = team.mattermost_webhooks or []
    if webhook_url not in webhooks:
        webhooks.append(webhook_url)
        await db.update_team_mattermost_webhooks(team_id, webhooks)
    
    return {"ok": True, "message": "Webhook added", "webhooks": webhooks}


@router.delete("/{team_id}/mattermost/webhooks")
async def remove_team_mattermost_webhook(
    team_id: str,
    request: dict,  # {"webhook_url": "https://..."}
    current_user: AuthUser,
    db: Database,
):
    """Remove a Mattermost webhook from team."""
    await check_team_access(team_id, current_user, db, Permission.ADMIN)
    
    webhook_url = request.get("webhook_url")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required")
    
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    webhooks = team.mattermost_webhooks or []
    if webhook_url in webhooks:
        webhooks.remove(webhook_url)
        await db.update_team_mattermost_webhooks(team_id, webhooks)
    
    return {"ok": True, "message": "Webhook removed", "webhooks": webhooks}


@router.delete("/{team_id}")
async def delete_team(
    team_id: str,
    request: dict,  # {"team_name": "exact team name"}
    current_user: AuthUser,
    db: Database,
):
    """Delete a team and all associated data (admin only)."""
    # Check if user is admin of the team
    member = await db.get_team_member(team_id, current_user.user_id)
    if not member or member.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get team to verify name
    team = await db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Require exact team name confirmation
    provided_name = request.get("team_name", "").strip()
    if provided_name != team.name:
        raise HTTPException(
            status_code=400, 
            detail="Team name confirmation does not match. Please type the exact team name."
        )
    
    # Perform cascade delete
    await db.delete_team(team_id)
    
    return {"message": f"Team '{team.name}' and all associated data deleted successfully"}
