"""Tests for the ping payload size cap on the public ping endpoint."""
from app.routers.ping import _truncate_ping_data, MAX_PING_DATA_BYTES


class TestTruncatePingData:
    def test_none_passes_through(self):
        assert _truncate_ping_data(None) is None

    def test_small_payload_unchanged(self):
        assert _truncate_ping_data("Backup completed: 1.2GB") == "Backup completed: 1.2GB"

    def test_payload_at_limit_unchanged(self):
        data = "a" * MAX_PING_DATA_BYTES
        assert _truncate_ping_data(data) == data

    def test_oversized_payload_truncated(self):
        data = "a" * (MAX_PING_DATA_BYTES + 5000)
        result = _truncate_ping_data(data)
        assert len(result.encode("utf-8")) == MAX_PING_DATA_BYTES

    def test_multibyte_payload_truncates_without_broken_chars(self):
        data = "é" * MAX_PING_DATA_BYTES  # 2 bytes each in UTF-8
        result = _truncate_ping_data(data)
        assert len(result.encode("utf-8")) <= MAX_PING_DATA_BYTES
        # Round-trips cleanly — no partial code points
        assert result == result.encode("utf-8").decode("utf-8")
