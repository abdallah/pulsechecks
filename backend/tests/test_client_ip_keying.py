"""Tests for rate-limiter client IP resolution behind trusted proxies."""
from unittest.mock import MagicMock, patch

from app.middleware import get_client_ip


def _request(peer="10.0.0.5", xff=None):
    request = MagicMock()
    request.client.host = peer
    request.headers = {"x-forwarded-for": xff} if xff else {}
    return request


def _settings(hops):
    settings = MagicMock()
    settings.trusted_proxy_hops = hops
    return settings


class TestGetClientIp:
    def test_hops_zero_uses_socket_peer(self):
        with patch("app.config.get_settings", return_value=_settings(0)):
            assert get_client_ip(_request(peer="1.2.3.4", xff="9.9.9.9")) == "1.2.3.4"

    def test_cloud_run_direct_uses_last_entry(self):
        # Cloud Run appends the caller's IP as the last XFF entry
        with patch("app.config.get_settings", return_value=_settings(1)):
            assert get_client_ip(_request(xff="6.6.6.6, 1.2.3.4")) == "1.2.3.4"

    def test_behind_glb_uses_second_from_last(self):
        # GFE appends "<client-ip>, <lb-ip>" — client is second-from-last
        with patch("app.config.get_settings", return_value=_settings(2)):
            assert get_client_ip(_request(xff="spoofed, 1.2.3.4, 130.211.0.1")) == "1.2.3.4"

    def test_spoofed_prefix_entries_are_ignored(self):
        # Attacker prepends fake IPs — only trailing trusted hops count
        with patch("app.config.get_settings", return_value=_settings(2)):
            xff = "8.8.8.8, 9.9.9.9, 1.2.3.4, 130.211.0.1"
            assert get_client_ip(_request(xff=xff)) == "1.2.3.4"

    def test_short_header_falls_back_to_peer(self):
        # Fewer entries than trusted hops → misconfiguration; fail safe to peer
        with patch("app.config.get_settings", return_value=_settings(2)):
            assert get_client_ip(_request(peer="10.1.1.1", xff="1.2.3.4")) == "10.1.1.1"

    def test_missing_header_falls_back_to_peer(self):
        with patch("app.config.get_settings", return_value=_settings(2)):
            assert get_client_ip(_request(peer="10.1.1.1")) == "10.1.1.1"
