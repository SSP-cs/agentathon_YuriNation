"""Tests for FastAPI backend endpoints."""

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_health_endpoint():
    """Verify health endpoint returns 200 with operational stats."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "models" in data
    assert "thresholds" in data

def test_ask_endpoint_empty():
    """Verify ask endpoint rejects empty queries."""
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 400

def test_runs_endpoint():
    """Verify runs listing endpoint returns list."""
    response = client.get("/runs?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

