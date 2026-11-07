"""FastAPI service. Owner: agent-1. Run with `uvicorn jane_avenue.api.app:app --port 8000`."""
from .app import create_app

__all__ = ["create_app"]
