"""Core route regression tests for health and chatbot endpoints."""

import main
from app.chat import orchestrator


def test_health_alias_route_returns_ok():
    """Health alias route should remain stable and return OK."""
    client = main.app.test_client()
    response = client.get("/uhccp-internal-chatbot/health")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "OK"


def test_chatbot_route_returns_mocked_response(monkeypatch):
    """Chatbot route should preserve response shape and status behavior."""
    monkeypatch.setattr(orchestrator, "chat_bot_response", lambda message: {"response": f"echo: {message}"})

    client = main.app.test_client()
    response = client.post("/chatbot", json={"message": "hello", "context": "ctx"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["response"] == "echo: hello"
    assert payload["context"] == "ctx"


def test_chatbot_missing_message_still_returns_400():
    """Chatbot route should keep missing-message validation semantics."""
    client = main.app.test_client()
    response = client.post("/chatbot", json={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No message provided"
