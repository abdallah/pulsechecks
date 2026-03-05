"""Tests for middleware functionality."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def test_app():
    """Create test FastAPI app with correlation middleware."""
    app = FastAPI()
    
    # Mock the logging functions to avoid signature issues
    with patch('app.middleware.set_request_context'), \
         patch('app.middleware.clear_request_context'):
        from app.middleware import correlation_id_middleware
        app.middleware("http")(correlation_id_middleware)
    
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {
            "correlation_id": getattr(request.state, 'correlation_id', None),
            "message": "test"
        }
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


def test_correlation_id_middleware_generates_id(client):
    """Test that middleware generates correlation ID when not provided."""
    response = client.get("/test")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have generated a correlation ID
    assert "correlation_id" in data
    assert data["correlation_id"] is not None
    assert len(data["correlation_id"]) > 0
    
    # Should be in response headers
    assert "X-Correlation-ID" in response.headers
    assert response.headers["X-Correlation-ID"] == data["correlation_id"]


def test_correlation_id_middleware_uses_provided_id(client):
    """Test that middleware uses provided correlation ID."""
    custom_id = "test-correlation-123"
    
    response = client.get("/test", headers={"X-Correlation-ID": custom_id})
    
    assert response.status_code == 200
    data = response.json()
    
    # Should use the provided correlation ID
    assert data["correlation_id"] == custom_id
    
    # Should be in response headers
    assert response.headers["X-Correlation-ID"] == custom_id


@patch("app.middleware.set_request_context")
@patch("app.middleware.clear_request_context")
def test_correlation_id_middleware_sets_logging_context(mock_clear, mock_set):
    """Test that middleware sets and clears logging context."""
    app = FastAPI()
    
    from app.middleware import correlation_id_middleware
    app.middleware("http")(correlation_id_middleware)
    
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"message": "test"}
    
    client = TestClient(app)
    response = client.get("/test")
    
    assert response.status_code == 200
    
    # Should have called set_request_context with correlation_id
    mock_set.assert_called_once()
    args = mock_set.call_args[0]
    assert len(args) >= 1  # At least correlation_id
    
    # Should have called clear_request_context
    mock_clear.assert_called_once()
