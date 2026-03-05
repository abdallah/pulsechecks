"""Direct Mattermost integration for rich alert formatting."""
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from ..models import Check, CheckStatus
from ..utils import get_current_time_seconds, with_circuit_breaker, CircuitBreakerError
from ..config import get_settings
import logging

logger = logging.getLogger(__name__)


class MattermostClient:
    """Direct Mattermost API client for rich alert messages."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_late_alert(self, check: Check, team_name: str) -> bool:
        """Send a rich late alert to Mattermost."""
        message = self._format_late_alert(check, team_name)
        return await self._send_message(message)
    
    async def send_recovery_alert(self, check: Check, team_name: str) -> bool:
        """Send a rich recovery alert to Mattermost."""
        message = self._format_recovery_alert(check, team_name)
        return await self._send_message(message)
    
    async def send_escalated_alert(self, check: Check, team_name: str) -> bool:
        """Send a rich escalated alert to Mattermost."""
        message = self._format_escalated_alert(check, team_name)
        return await self._send_message(message)
    
    def _format_late_alert(self, check: Check, team_name: str) -> Dict[str, Any]:
        """Format a late alert with rich Mattermost formatting."""
        # Create clickable link in the message text instead of using action buttons
        check_url = f"{self._get_frontend_url()}/teams/{check.team_id}/checks/{check.check_id}"
        
        return {
            "username": "Pulsechecks",
            "icon_emoji": ":warning:",
            "attachments": [{
                "color": "danger",  # Red color coding for late status
                "title": f"🔴 Check Late: {check.name}",
                "title_link": check_url,  # Make the title clickable
                "text": f"Check **{check.name}** in team **{team_name}** is overdue and needs attention.\n\n[🔍 View Check Details]({check_url})",
                "fields": [
                    {
                        "title": "Team",
                        "value": team_name,
                        "short": True
                    },
                    {
                        "title": "Status", 
                        "value": "🔴 **LATE**",
                        "short": True
                    },
                    {
                        "title": "Expected Every",
                        "value": f"{check.period_seconds // 3600}h {(check.period_seconds % 3600) // 60}m",
                        "short": True
                    },
                    {
                        "title": "Grace Period", 
                        "value": f"{check.grace_seconds // 60}m",
                        "short": True
                    },
                    {
                        "title": "Last Ping",
                        "value": check.last_ping_at or "Never",
                        "short": False
                    }
                ],
                "footer": "Pulsechecks Alert System",
                "ts": get_current_time_seconds()
            }]
        }
    
    def _format_recovery_alert(self, check: Check, team_name: str) -> Dict[str, Any]:
        """Format a recovery alert with rich Mattermost formatting."""
        check_url = f"{self._get_frontend_url()}/teams/{check.team_id}/checks/{check.check_id}"
        
        return {
            "username": "Pulsechecks", 
            "icon_emoji": ":white_check_mark:",
            "attachments": [{
                "color": "good",  # Green color coding for recovery status
                "title": f"🟢 Check Recovered: {check.name}",
                "title_link": check_url,  # Make the title clickable
                "text": f"Check **{check.name}** in team **{team_name}** has recovered and is back online.\n\n[🔍 View Check Details]({check_url})",
                "fields": [
                    {
                        "title": "Team",
                        "value": team_name,
                        "short": True
                    },
                    {
                        "title": "Status",
                        "value": "🟢 **RECOVERED**",
                        "short": True
                    },
                    {
                        "title": "Last Ping",
                        "value": check.last_ping_at or "Just now",
                        "short": True
                    },
                    {
                        "title": "Next Expected",
                        "value": f"Within {check.period_seconds // 3600}h {(check.period_seconds % 3600) // 60}m",
                        "short": True
                    }
                ],
                "footer": "Pulsechecks Alert System",
                "ts": get_current_time_seconds()
            }]
        }
    
    @with_circuit_breaker(failure_threshold=3, recovery_timeout=30.0, expected_exception=httpx.RequestError)
    async def _send_message(self, message: Dict[str, Any]) -> bool:
        """Send message to Mattermost webhook with circuit breaker protection."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return True
        except CircuitBreakerError:
            logger.warning("Mattermost circuit breaker is open, skipping message")
            return False
        except httpx.RequestError as e:
            logger.error(f"Failed to send Mattermost message: {e}")
            return False  # Return False instead of raising
        except Exception as e:
            logger.error(f"Unexpected error sending Mattermost message: {e}")
            return False
    
    def _get_frontend_url(self) -> str:
        """Get frontend URL for action buttons."""
        settings = get_settings()
        return settings.frontend_url


def create_mattermost_client(webhook_url: str) -> MattermostClient:
    """Factory function to create Mattermost client."""
    return MattermostClient(webhook_url)


# Add escalated alert formatting method to MattermostClient
def _format_escalated_alert_method(self, check, team_name: str):
    """Format an escalated alert with rich Mattermost formatting."""
    check_url = f"{self._get_frontend_url()}/teams/{check.team_id}/checks/{check.check_id}"
    
    return {
        "username": "Pulsechecks",
        "icon_emoji": ":rotating_light:",
        "attachments": [{
            "color": "#ff0000",  # Bright red for escalated alerts
            "title": f"🚨 ESCALATED: {check.name}",
            "title_link": check_url,  # Make the title clickable
            "text": f"**ESCALATED ALERT** - Check **{check.name}** in team **{team_name}** requires immediate attention!\n\n[🔍 View Check Details]({check_url})",
            "fields": [
                {
                    "title": "Team",
                    "value": team_name,
                    "short": True
                },
                {
                    "title": "Status", 
                    "value": "🚨 **ESCALATED**",
                    "short": True
                },
                {
                    "title": "Escalated After",
                    "value": f"{check.escalation_minutes} minutes",
                    "short": True
                },
                {
                    "title": "Expected Every",
                    "value": f"{check.period_seconds // 3600}h {(check.period_seconds % 3600) // 60}m",
                    "short": True
                },
                {
                    "title": "Last Ping",
                    "value": check.last_ping_at or "Never",
                    "short": False
                }
            ],
            "footer": "Pulsechecks Alert System - ESCALATED",
            "ts": get_current_time_seconds()
        }]
    }

# Monkey patch the method onto the class
MattermostClient._format_escalated_alert = _format_escalated_alert_method
