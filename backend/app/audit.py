"""Audit log helper — records who did what, without ever breaking the request."""
from typing import Optional

from .models import AuditEvent
from .utils import generate_id, get_iso_timestamp
from .logging_config import get_logger

logger = get_logger(__name__)


async def record_audit(
    db,
    team_id: str,
    actor,
    action: str,
    target_type: str,
    target_id: str,
    target_name: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Persist an audit event. Best effort: failures are logged, never raised,
    so an audit-store hiccup can't fail the underlying admin action."""
    try:
        await db.create_audit_event(AuditEvent(
            event_id=generate_id(),
            team_id=team_id,
            actor_id=getattr(actor, "user_id", "unknown"),
            actor_email=getattr(actor, "email", "unknown"),
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            detail=detail,
            created_at=get_iso_timestamp(),
        ))
    except Exception as e:
        logger.error(f"Failed to record audit event {action} for team {team_id}: {e}")
