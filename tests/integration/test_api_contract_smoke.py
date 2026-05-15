"""API compatibility smoke tests for stable HTTP routes."""

import json

import pytest

import config
import main


@pytest.fixture()
def client(monkeypatch):
    """Return Flask test client with environment toggles patched for tests."""
    monkeypatch.setattr(config.env, "set_env", lambda **kwargs: None)
    return main.app.test_client()


def test_health_endpoint_returns_ok(client):
    """Health endpoint remains backward compatible."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "OK"


def test_chatbot_missing_message_returns_400(client):
    """Chatbot endpoint keeps validation behavior for missing input."""
    response = client.post("/chatbot", json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "No message provided"


def test_chat_missing_msg_returns_error_payload(client):
    """Chat endpoint keeps no-message behavior with JSON response body."""
    response = client.post("/chat", json={})

    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["response"] == "No message provided"
    assert data["persona"] == "uhccp"


def test_stream_missing_message_emits_error_event(client):
    """Streaming endpoint keeps event-stream error behavior on empty input."""
    response = client.post("/chat/stream", json={})

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    body = response.get_data(as_text=True)
    assert '"type": "error"' in body
    assert "No message provided" in body


def test_static_asset_route_serves_stylesheet(client):
    """Static asset route remains reachable for frontend compatibility."""
    response = client.get("/uhccp-internal-chatbot/static/styles.css")

    assert response.status_code == 200
    assert "text/css" in response.mimetype
