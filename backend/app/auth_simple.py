"""Simple API key authentication for backend API access."""
import os
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

# Simple API key from environment
API_KEY = os.getenv("API_KEY", "pulsechecks-dev-key-123")

security = HTTPBearer()

class SimpleUser:
    """Simple user for API key auth."""
    def __init__(self, user_id: str = "api-user"):
        self.user_id = user_id
        self.email = "api@pulsechecks.local"

async def get_api_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> SimpleUser:
    """Validate API key and return simple user."""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return SimpleUser()

# Alias for compatibility
AuthUser = SimpleUser
get_current_user = get_api_user
