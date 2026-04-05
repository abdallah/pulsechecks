"""Input validation utilities for preventing injection attacks."""
import re
import ipaddress
from typing import Tuple
from urllib.parse import urlparse


def validate_name_field(name: str, max_length: int = 100) -> Tuple[bool, str]:
    """
    Validate name fields (checks, teams, channels).
    
    Pattern: alphanumeric, hyphens, underscores, spaces only.
    This prevents SQL injection, XSS, and command injection through name fields.
    
    Args:
        name: Field value to validate
        max_length: Maximum allowed length (default 100)
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not name or not isinstance(name, str):
        return False, "Name must be a non-empty string"
    
    # Check length
    if len(name) > max_length:
        return False, f"Name must be at most {max_length} characters (got {len(name)})"
    
    # Pattern: letters, numbers, hyphens, underscores, spaces
    # This blocks SQL keywords, quotes, angle brackets, slashes, etc.
    if not re.match(r'^[a-zA-Z0-9_\-\s]+$', name):
        return False, "Name can only contain letters, numbers, hyphens, underscores, and spaces"
    
    # Prevent leading/trailing whitespace
    if name != name.strip():
        return False, "Name cannot have leading or trailing whitespace"
    
    return True, "Name is valid"


def validate_cron_expression(expression: str) -> Tuple[bool, str]:
    """
    Validate cron expression to prevent injection attacks.
    
    Uses croniter to validate syntax. This prevents cron command injection
    or exploitation of shell metacharacters in cron fields.
    
    Args:
        expression: Cron expression string
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not expression or not isinstance(expression, str):
        return False, "Cron expression must be a non-empty string"
    
    # Length check to prevent DOS
    if len(expression) > 100:
        return False, "Cron expression must be at most 100 characters"
    
    # Check for shell metacharacters that could enable injection
    dangerous_chars = ['$', '`', '\\', ';', '&', '|', '>', '<', '(', ')', '{', '}']
    for char in dangerous_chars:
        if char in expression:
            return False, f"Cron expression contains forbidden character: '{char}'"
    
    # Validate syntax using croniter
    try:
        from croniter import croniter
        if not croniter.is_valid(expression):
            return False, "Invalid cron expression syntax"
        return True, "Cron expression is valid"
    except Exception as e:
        return False, f"Cron expression validation failed: {str(e)}"


def validate_url(url: str, allow_private_ips: bool = False) -> Tuple[bool, str]:
    """
    Validate URL to prevent SSRF attacks.
    
    Blocks:
    - Private IP addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, etc.)
    - Metadata service endpoints (169.254.169.254, etc.)
    - Dangerous schemes (file://, data://, etc.)
    - Localhost addresses when SSRF protection is needed
    
    Args:
        url: URL to validate
        allow_private_ips: If True, allow private IP addresses (default False for SSRF protection)
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    # Length check
    if len(url) > 2048:
        return False, "URL must be at most 2048 characters"
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"
    
    # Check scheme
    scheme = parsed.scheme.lower()
    dangerous_schemes = ['file', 'data', 'javascript', 'vbscript', 'about']
    if scheme in dangerous_schemes:
        return False, f"URL scheme '{scheme}' is not allowed"
    
    if scheme not in ['http', 'https']:
        return False, f"URL must use http:// or https:// (got {scheme}://)"
    
    # Get hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid hostname"
    
    # Block localhost/127.0.0.1 to prevent SSRF against local services
    localhost_patterns = ['localhost', '127.0.0.1', '::1', '0.0.0.0']
    if hostname in localhost_patterns:
        return False, f"Localhost addresses are not allowed: {hostname}"
    
    # If SSRF protection is enabled, block private IPs and metadata endpoints
    if not allow_private_ips:
        # AWS metadata service
        if hostname == '169.254.169.254':
            return False, "AWS metadata service endpoint is not allowed"
        
        # Google metadata service
        if hostname == 'metadata.google.internal' or hostname == 'metadata.goog':
            return False, "Google metadata service endpoint is not allowed"
        
        # Azure metadata service
        if hostname == '169.254.169.254':
            return False, "Azure metadata service endpoint is not allowed"
        
        # Check for private IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                return False, f"Private IP address not allowed: {hostname}"
        except ValueError:
            # Not an IP address (valid domain name), continue
            pass
    
    return True, "URL is valid"


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not email or not isinstance(email, str):
        return False, "Email must be a non-empty string"
    
    # Length check
    if len(email) > 254:  # RFC 5321
        return False, "Email must be at most 254 characters"
    
    # Simple regex pattern for email validation
    # This is not exhaustive but covers most common cases
    email_pattern = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~\-]+@[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    
    if not re.match(email_pattern, email):
        return False, "Invalid email address format"
    
    return True, "Email is valid"


def sanitize_string(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user input string by removing control characters and null bytes.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(text, str):
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove null bytes and control characters except newlines/tabs
    sanitized = ''.join(
        char for char in text
        if char.isprintable() or char in '\n\t'
    )
    
    return sanitized
