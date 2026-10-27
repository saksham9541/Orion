import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app, on_startup


def test_health_check_format():
    """Health check endpoint must return only status, models_loaded, and database_ok."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    # Must contain exact expected keys
    assert set(data.keys()) == {"status", "models_loaded", "database_ok"}
    assert data["status"] == "ok"
    assert isinstance(data["models_loaded"], bool)
    assert isinstance(data["database_ok"], bool)
    # Must NOT contain internal state counters
    assert "tasks" not in data
    assert "windows" not in data
    assert "plans" not in data


def test_startup_handles_postgres_failure_gracefully():
    """When PostgreSQL connection fails on startup, app runs in degraded mode with database_ok = False."""
    mock_engine = MagicMock()
    mock_engine.url.drivername = "postgresql+psycopg"

    with patch("backend.main.engine", mock_engine), \
         patch("backend.main.check_connection_with_retry", side_effect=Exception("Neon connection timeout")):
        on_startup()

    assert app.state.database_ok is False


def test_startup_marks_models_unloaded_when_missing():
    """When model pkl files are missing, models_loaded must be False and no exception raised."""
    with patch("os.path.exists", return_value=False):
        on_startup()

    assert app.state.models_loaded is False
