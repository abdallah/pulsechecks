"""
Cloud Run entry point for Pulsechecks API.

This module provides the entry point for running the FastAPI application
on Google Cloud Run with uvicorn. The main FastAPI app is imported from
app.main and works natively with uvicorn without any adapter layer.

Usage:
    uvicorn main_cloudrun:app --host 0.0.0.0 --port 8080

Environment Variables:
    CLOUD_PROVIDER: Should be set to "gcp" for Cloud Run
    PORT: Port to bind to (default: 8080, set by Cloud Run)
"""

from app.main import app

# Export the FastAPI app for uvicorn
# No adapter needed - FastAPI works natively with uvicorn on Cloud Run
__all__ = ["app"]
