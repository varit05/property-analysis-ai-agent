import pytest
from fastapi.testclient import TestClient

from server.main import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI app instance for each test."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    with TestClient(app) as c:
        yield c