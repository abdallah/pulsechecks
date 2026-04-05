"""SSRF (Server-Side Request Forgery) protection utilities.

Prevents attacks that target metadata endpoints and internal services.
Blocks requests to:
- RFC 1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Loopback addresses (127.0.0.1, ::1)
- Link-local addresses (169.254.0.0/16)
- Cloud metadata endpoints (169.254.169.254, metadata.google.internal, etc.)
- Localhost and local variants
"""
import ipaddress
from typing import Tuple
from urllib.parse import urlparse
from fastapi import HTTPException, status


# Blocked IP ranges and addresses
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),           # RFC 1918 - Private network
    ipaddress.ip_network("172.16.0.0/12"),        # RFC 1918 - Private network
    ipaddress.ip_network("192.168.0.0/16"),       # RFC 1918 - Private network
    ipaddress.ip_network("127.0.0.0/8"),          # Loopback
    ipaddress.ip_network("::1/128"),              # IPv6 Loopback
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local / APIPA
    ipaddress.ip_network("fe80::/10"),            # IPv6 Link-local
    ipaddress.ip_network("0.0.0.0/8"),            # This network
    ipaddress.ip_network("::/128"),               # IPv6 Unspecified
]

# Blocked hostnames and patterns (cloud metadata endpoints, localhost variants)
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "169.254.169.254",                            # AWS metadata endpoint
    "metadata.google.internal",                   # GCP metadata endpoint
    "metadata.internal",                          # GCP alternative
    "100.100.100.200",                            # Aliyun metadata endpoint
    "169.254.169.255",                            # Azure metadata endpoint (alternative)
    "metadata.service.consul",                    # Consul metadata
}


def validate_webhook_url(url: str) -> Tuple[bool, str]:
    """
    Validate that a webhook URL is safe and not targeting internal/metadata endpoints.
    
    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if URL is valid and safe
        - (False, error_msg) if URL is invalid or blocked
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"
    
    # Validate scheme
    if parsed.scheme not in ("http", "https"):
        return False, "URL must use http or https scheme"
    
    # Get hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must have a hostname"
    
    # Check against blocked hostnames first (fast path)
    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Webhook URL targets blocked hostname: {hostname}"
    
    # Prevent *.localhost domains
    if hostname_lower.endswith(".localhost") or hostname_lower.endswith(".local"):
        return False, f"Webhook URL targets local network: {hostname}"
    
    # Try to resolve to IP and check against blocked ranges
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_ip_blocked(ip):
            return False, f"Webhook URL targets blocked IP address: {hostname}"
    except ValueError:
        # Not an IP address, try DNS resolution
        try:
            import socket
            try:
                # Resolve hostname to IP
                ip_str = socket.gethostbyname(hostname)
                ip = ipaddress.ip_address(ip_str)
                if _is_ip_blocked(ip):
                    return False, f"Webhook URL resolves to blocked IP address: {ip_str}"
            except socket.gaierror:
                # DNS resolution failed - this is okay, might be an external service
                pass
            except Exception as e:
                # Other resolution errors - log and allow (better to send failed request than block legitimate URL)
                return True, ""
        except Exception:
            # If we can't resolve, allow it to proceed (will fail at HTTP request time)
            pass
    
    return True, ""


def _is_ip_blocked(ip: ipaddress.ip_address) -> bool:
    """Check if an IP address is in a blocked range."""
    for blocked_range in BLOCKED_IP_RANGES:
        if ip in blocked_range:
            return True
    return False


def assert_webhook_url_safe(url: str) -> None:
    """
    Validate a webhook URL and raise HTTPException if it's unsafe.
    
    Raises:
        HTTPException: If URL is invalid, not a valid webhook, or targets blocked addresses
    """
    is_valid, error_msg = validate_webhook_url(url)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook URL: {error_msg}",
        )
