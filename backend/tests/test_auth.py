"""Tests for authentication module."""
import pytest
from unittest.mock import patch
from app.auth import check_domain_allowed, get_email_domain


def test_check_domain_allowed_single():
    """Test domain allowlist with single domain."""
    assert check_domain_allowed("user@example.com", "example.com")
    assert not check_domain_allowed("user@other.com", "example.com")


def test_check_domain_allowed_multiple():
    """Test domain allowlist with multiple domains."""
    allowed = "example.com,example.org"

    assert check_domain_allowed("user@example.com", allowed)
    assert check_domain_allowed("user@example.org", allowed)
    assert not check_domain_allowed("user@other.com", allowed)


def test_check_domain_allowed_case_insensitive():
    """Test domain check is case insensitive."""
    allowed = "Example.COM"

    assert check_domain_allowed("user@example.com", allowed)
    assert check_domain_allowed("user@EXAMPLE.COM", allowed)
    assert check_domain_allowed("User@Example.Com", allowed)


def test_check_domain_allowed_empty():
    """Test with no domain restriction."""
    # Empty string means no restriction
    assert check_domain_allowed("user@anything.com", "")
    assert check_domain_allowed("user@example.com", "")


def test_check_domain_allowed_whitespace():
    """Test domain allowlist with whitespace."""
    allowed = " example.com , example.org "

    assert check_domain_allowed("user@example.com", allowed)
    assert check_domain_allowed("user@example.org", allowed)


def test_get_email_domain():
    """Test email domain extraction."""
    assert get_email_domain("user@example.com") == "example.com"
    assert get_email_domain("User@Example.COM") == "example.com"
    assert get_email_domain("test.user@subdomain.example.com") == "subdomain.example.com"
