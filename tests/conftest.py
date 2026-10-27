import os
import pytest

os.environ.setdefault("JWT_SECRET", "x" * 40)
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture(autouse=True)
def _ensure_default_env():
    """Ensure default environment variables remain set across tests."""
    os.environ.setdefault("JWT_SECRET", "x" * 40)
    os.environ.setdefault("ENVIRONMENT", "development")
    yield
    os.environ.setdefault("JWT_SECRET", "x" * 40)
    os.environ.setdefault("ENVIRONMENT", "development")
