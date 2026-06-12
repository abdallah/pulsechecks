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
import socket
from typing import Tuple
from urllib.parse import urlparse
from fastapi import HTTPException, status


# Blocked IP ranges and addresses
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::/128"),
]

# Blocked hostnames and patterns (cloud metadata endpoints, localhost variants)
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.internal",
    "100.100.100.200",
    "169.254.169.255",
    "metadata.service.consul",
}


def validate_webhook_url(url: str) -> Tuple[bool, str]:
    """Validate that a webhook URL is safe and not targeting internal/metadata endpoints."""
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Invalid URL format: {exc}"

    if parsed.scheme not in ("http", "https"):
        return False, "URL must use http or https scheme"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must have a hostname"

    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Webhook URL targets blocked hostname: {hostname}"

    if hostname_lower.endswith(".localhost") or hostname_lower.endswith(".local"):
        return False, f"Webhook URL targets local network: {hostname}"

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            # Resolve all candidate addresses and fail closed on any ambiguity.
            addrinfos = socket.getaddrinfo(hostname, parsed.port or 0, type=socket.SOCK_STREAM)
            if not addrinfos:
                return False, f"Unable to resolve hostname safely: {hostname}"

            resolved_ips = set()
            for _, _, _, _, sockaddr in addrinfos:
                resolved_ips.add(ipaddress.ip_address(sockaddr[0]))

            for resolved_ip in resolved_ips:
                if _is_ip_blocked(resolved_ip):
                    return False, f"Webhook URL resolves to blocked IP address: {resolved_ip}"
        except socket.gaierror:
            return False, f"Unable to resolve hostname safely: {hostname}"
        except Exception:
            return False, f"Unable to validate hostname safely: {hostname}"
    else:
        if _is_ip_blocked(ip):
            return False, f"Webhook URL targets blocked IP address: {hostname}"

    return True, ""


def _is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in a blocked range."""
    return any(ip in blocked_range for blocked_range in BLOCKED_IP_RANGES)


def assert_webhook_url_safe(url: str) -> None:
    """Validate a webhook URL and raise HTTPException if it's unsafe."""
    is_valid, error_msg = validate_webhook_url(url)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook URL: {error_msg}",
        )
