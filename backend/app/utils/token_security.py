"""Security utilities for API token validation and protection against timing attacks."""
import hashlib
import hmac
import os
import time
from typing import Tuple


def timing_safe_compare(provided: str, expected: str) -> bool:
    """
    Timing-safe token comparison using hmac.compare_digest.
    
    Prevents timing attacks by comparing tokens in constant time,
    regardless of where the first differing byte occurs.
    
    Args:
        provided: Token provided by client
        expected: Expected token hash stored in database
        
    Returns:
        True if tokens match, False otherwise
    """
    return hmac.compare_digest(provided, expected)


def validate_token_entropy(token_bytes: bytes, min_bytes: int = 32) -> Tuple[bool, str]:
    """
    Validate that token has sufficient entropy.
    
    Weak tokens (low entropy) are vulnerable to enumeration attacks.
    We require at least 32 bytes (256 bits) of cryptographically secure randomness.
    
    Args:
        token_bytes: Raw token bytes
        min_bytes: Minimum required bytes (default 32 = 256 bits)
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if len(token_bytes) < min_bytes:
        return False, f"Token must be at least {min_bytes} bytes of random data (got {len(token_bytes)})"
    
    # Entropy check: high-quality random should have near-maximum Shannon entropy
    # For simplicity, we just check length; Python's os.urandom() is cryptographically secure
    # In production, you could add statistical entropy tests here if needed
    
    return True, "Token has sufficient entropy"


def rate_limit_token_creation(
    user_id: str,
    creation_times: dict,
    max_tokens_per_minute: int = 10,
    max_tokens_per_hour: int = 100,
) -> Tuple[bool, str]:
    """
    Rate limit API token creation to prevent enumeration attacks.
    
    Args:
        user_id: User creating the token
        creation_times: Dict mapping user_id to list of creation timestamps
        max_tokens_per_minute: Maximum tokens allowed per minute
        max_tokens_per_hour: Maximum tokens allowed per hour
        
    Returns:
        Tuple of (is_allowed, reason)
    """
    current_time = time.time()
    
    # Initialize user's creation times if not exists
    if user_id not in creation_times:
        creation_times[user_id] = []
    
    times = creation_times[user_id]
    
    # Remove timestamps older than 1 hour
    times[:] = [t for t in times if current_time - t < 3600]
    
    # Check hourly limit
    if len(times) >= max_tokens_per_hour:
        return False, f"Rate limited: maximum {max_tokens_per_hour} tokens per hour"
    
    # Check per-minute limit (last 60 seconds)
    recent_times = [t for t in times if current_time - t < 60]
    if len(recent_times) >= max_tokens_per_minute:
        return False, f"Rate limited: maximum {max_tokens_per_minute} tokens per minute"
    
    # Record this creation
    times.append(current_time)
    
    return True, "Token creation allowed"


def validate_token_format(token: str) -> Tuple[bool, str]:
    """
    Validate token format (pc_ prefix + hex characters).
    
    Args:
        token: Token string to validate
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not token.startswith("pc_"):
        return False, "Token must start with 'pc_' prefix"
    
    if len(token) != 67:  # pc_ (3) + 64 hex chars
        return False, f"Token must be exactly 67 characters (got {len(token)})"
    
    # Check that everything after prefix is valid hex
    hex_part = token[3:]
    try:
        int(hex_part, 16)
        return True, "Token format is valid"
    except ValueError:
        return False, "Token must contain only valid hexadecimal characters after 'pc_' prefix"
