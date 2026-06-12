"""Security surface regression tests for backend app configuration."""
from pathlib import Path
import ast

from fastapi.testclient import TestClient

from app.handlers import late_detector_handler, __all__ as handlers_all
from app.main import app


CLIENT = TestClient(app)


def test_late_detector_handler_defined_once_and_exported():
    """The Lambda handler should only be defined once and exported cleanly."""
    source = Path(__file__).resolve().parents[1] / "app" / "handlers.py"
    tree = ast.parse(source.read_text())

    defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "late_detector_handler"]
    assert len(defs) == 1
    assert handlers_all == ["late_detector_handler"]
    assert callable(late_detector_handler)


def test_cors_allows_required_request_headers_and_not_wildcard():
    """CORS should use an explicit allow-list for frontend/auth headers."""
    response = CLIENT.options(
        "/health",
        headers={
            "Origin": "https://pulsechecks.web.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type,x-correlation-id",
        },
    )

    assert response.status_code in (200, 204)
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "*" not in allow_headers
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers
    assert "x-correlation-id" in allow_headers


def test_security_headers_present_on_api_responses():
    """Responses should include basic hardening headers."""
    response = CLIENT.get("/health")

    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "same-origin"
    assert "server" not in {k.lower() for k in response.headers.keys()}
