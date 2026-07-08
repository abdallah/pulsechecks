"""Regression tests for CSV formula injection in report exports."""
from app.routers.reports import _csv_safe, _render_report_content


class TestCsvSafe:
    def test_formula_prefixes_are_neutralized(self):
        for payload in ("=1+1", "+1", "-1", "@SUM(A1)", "=cmd|'/c calc'!A1",
                        "=HYPERLINK(\"http://evil\",\"x\")", "\ttab", "\rcr"):
            out = _csv_safe(payload)
            assert out.startswith("'"), f"{payload!r} was not neutralized"

    def test_normal_values_unchanged(self):
        for payload in ("Nightly Backup", "check-1", "up", "prod db", "500", ""):
            assert _csv_safe(payload) == payload

    def test_non_strings_unchanged(self):
        assert _csv_safe(42) == 42
        assert _csv_safe(None) is None
        assert _csv_safe(3.14) == 3.14


class TestReportCsvRendering:
    def test_malicious_check_name_is_escaped_in_csv(self):
        payload = {
            "teamId": "team-1", "reportType": "summary", "from": "a", "to": "b",
            "checks": [{
                "checkId": "c1", "name": "=cmd|'/c calc'!A1", "type": "cron", "status": "up",
                "uptimePct": 99.9, "downtimeMinutes": 1, "excludedMaintenanceMinutes": 0,
                "totalFailures": 0, "mostCommonCode": None, "avgResponseMs": 10,
                "p95ResponseMs": 20, "latestResponseMs": 15,
            }],
        }
        content, ctype = _render_report_content("summary", "csv", payload)
        assert ctype == "text/csv"
        # The dangerous cell must be quoted, never emitted starting with '='
        assert "'=cmd" in content
        for line in content.splitlines()[1:]:
            first_cell = line.split(",")[0].strip('"')
            assert not first_cell.startswith("=")
