"""Regression tests for /chat and /chat/stream endpoints."""

import config
import main
from app.chat import orchestrator


def test_chat_route_returns_formatted_payload(monkeypatch):
    """Chat route should preserve output JSON keys and persona field."""
    monkeypatch.setattr(config.env, "set_env", lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, "get_chatbot_response", lambda *args, **kwargs: {"response": "sample"})

    client = main.app.test_client()
    response = client.post("/chat?msg=hello", json={"history": [], "username": "tester"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["response"] == "sample"
    assert body["persona"] == "uhccp"
    assert "urlInfo" in body


def test_chat_stream_route_emits_final_event(monkeypatch):
    """Streaming chat route should continue sending SSE final/done events."""
    monkeypatch.setattr(config.env, "set_env", lambda **kwargs: None)
    monkeypatch.setattr(orchestrator, "is_weekly_ppt_request", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(orchestrator, "get_chatbot_response", lambda *args, **kwargs: {"response": "streamed"})

    client = main.app.test_client()
    response = client.post("/chat/stream", json={"message": "hello", "history": []})

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    body = response.get_data(as_text=True)
    assert '"type": "final"' in body
    assert "streamed" in body
    assert '"type": "done"' in body
