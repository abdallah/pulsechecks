"""SSRF (Server-Side Request Forgery) protection utilities."""
import ipaddress
import urllib.parse
from typing import Tuple


def is_private_ip(ip: str) -> bool:
    """Check if IP address is in private/reserved ranges."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local or
            ip_obj.is_multicast or
            ip_obj.is_reserved
        )
    except ValueError:
        return False


def is_metadata_endpoint(hostname: str) -> bool:
    """Check if hostname is a known metadata endpoint."""
    metadata_hosts = {
        # AWS
        "169.254.169.254",
        "metadata.amazonaws.com",
        
        # GCP
        "metadata.google.internal",
        "metadata.gcp.internal",
        "169.254.169.254",  # GCP also uses this
        
        # Azure
        "169.254.169.254",
        "168.63.129.16",
        
        # Other cloud providers
        "fd00:ec2::254",  # IPv6 AWS
    }
    
    return hostname.lower() in metadata_hosts


def validate_webhook_url(url: str) -> Tuple[bool, str]:
    """
    Validate webhook URL for SSRF safety.
    
    Args:
        url: The webhook URL to validate
        
    Returns:
        Tuple of (is_safe, error_message)
        - If safe: (True, "")
        - If unsafe: (False, "reason")
    """
    if not url:
        return False, "URL cannot be empty"
    
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"
    
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"
    
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must have a valid hostname"
    
    # Block metadata endpoints
    if is_metadata_endpoint(hostname):
        return False, f"Metadata endpoint blocked: {hostname}"
    
    # Block private/loopback IPs
    try:
        if is_private_ip(hostname):
            return False, f"Private IP address blocked: {hostname}"
    except Exception:
        # If we can't parse as IP, continue (might be a domain)
        pass
    
    # Block localhost by name and special domains
    blocked_domains = {
        "localhost",
        "127.0.0.1",
        "::1",
        "[::1]",
        "localhost.local",
        "localhost.localhost",
    }
    
    hostname_lower = hostname.lower()
    if hostname_lower in blocked_domains:
        return False, f"Loopback address blocked: {hostname}"
    
    # Block .local and .localhost TLDs (often used for local services)
    if hostname_lower.endswith(".local") or hostname_lower.endswith(".localhost"):
        return False, f"Local domain blocked: {hostname}"
    
    # Block bare IP addresses in private ranges (catch edge cases)
    try:
        if is_private_ip(hostname):
            return False, f"Private IP blocked: {hostname}"
    except Exception:
        pass
    
    return True, ""


class SSRFValidationError(ValueError):
    """Raised when SSRF validation fails."""
    pass


def validate_webhook_url_strict(url: str) -> None:
    """
    Validate webhook URL and raise SSRFValidationError if unsafe.
    
    Args:
        url: The webhook URL to validate
        
    Raises:
        SSRFValidationError: If URL fails SSRF validation
    """
    is_safe, error_message = validate_webhook_url(url)
    if not is_safe:
        raise SSRFValidationError(f"Unsafe webhook URL: {error_message}")
