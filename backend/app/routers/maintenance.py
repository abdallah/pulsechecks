"""Maintenance window management endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Query

from ..dependencies import AuthUser, Database, check_team_access
from ..errors import NotFoundError
from ..models import CreateMaintenanceWindowRequest, MaintenanceWindowResponse, OkResponse, MaintenanceWindow, Permission
from ..utils import generate_id, get_iso_timestamp

router = APIRouter(prefix="/teams/{team_id}/maintenance", tags=["maintenance"])


def _serialize_maintenance_window(window: MaintenanceWindow) -> MaintenanceWindowResponse:
    return MaintenanceWindowResponse(
        windowId=window.window_id,
        teamId=window.team_id,
        checkId=window.check_id,
        startAt=window.start_at,
        endAt=window.end_at,
        label=window.label,
        createdBy=window.created_by,
        createdAt=window.created_at,
    )


@router.post("", response_model=MaintenanceWindowResponse)
async def create_maintenance_window(
    team_id: str,
    request: CreateMaintenanceWindowRequest,
    current_user: AuthUser,
    db: Database,
) -> MaintenanceWindowResponse:
    """Create a maintenance window for a team or a specific check."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)

    if request.check_id:
        check = await db.get_check(team_id, request.check_id)
        if not check:
            raise NotFoundError("Check not found")

    window = MaintenanceWindow(
        window_id=generate_id(),
        team_id=team_id,
        check_id=request.check_id,
        start_at=request.start_at,
        end_at=request.end_at,
        label=request.label,
        created_by=current_user.user_id,
        created_at=get_iso_timestamp(),
    )
    await db.create_maintenance_window(window)
    return _serialize_maintenance_window(window)


@router.get("", response_model=List[MaintenanceWindowResponse])
async def list_maintenance_windows(
    team_id: str,
    current_user: AuthUser,
    db: Database,
    check_id: Optional[str] = Query(default=None, alias="check_id"),
) -> List[MaintenanceWindowResponse]:
    """List maintenance windows for a team."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    windows = await db.list_maintenance_windows(team_id, check_id)
    return [_serialize_maintenance_window(window) for window in windows]


@router.delete("/{window_id}", response_model=OkResponse)
async def delete_maintenance_window(
    team_id: str,
    window_id: str,
    current_user: AuthUser,
    db: Database,
) -> OkResponse:
    """Delete a maintenance window."""
    await check_team_access(team_id, current_user, db, Permission.EDIT)
    await db.delete_maintenance_window(team_id, window_id)
    return OkResponse(message="Maintenance window deleted")