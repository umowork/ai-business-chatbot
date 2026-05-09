"""
Tests for FastAPI web API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from api.web import WebAPI


@pytest.fixture
def test_client(test_config, test_db):
    """Create a TestClient for the FastAPI app."""
    web_api = WebAPI(test_config, test_db)
    return TestClient(web_api.app)


class TestHealthEndpoint:
    """Test GET /health"""

    def test_health_ok(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "mock_mode" in data
        assert "services" in data


class TestChatEndpoint:
    """Test POST /chat"""

    def test_chat_missing_message(self, test_client):
        response = test_client.post("/chat", json={"user_id": "123"})
        assert response.status_code == 422

    def test_chat_missing_user_id(self, test_client):
        response = test_client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 422

    def test_chat_empty_message(self, test_client):
        response = test_client.post("/chat", json={"message": "", "user_id": "123"})
        assert response.status_code == 422


class TestLeadsEndpoint:
    """Test GET /leads"""

    def test_leads_list(self, test_client):
        response = test_client.get("/leads")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_leads_pagination(self, test_client):
        response = test_client.get("/leads?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestStatsEndpoint:
    """Test GET /stats"""

    def test_stats(self, test_client):
        response = test_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "leads" in data
        assert "dialog_messages" in data


class TestCORS:
    """Test CORS headers are present."""

    def test_cors_headers(self, test_client):
        response = test_client.options("/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
