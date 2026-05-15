"""Template rendering regression tests for frontend compatibility."""

import main


def test_home_page_renders_with_chat_shell():
    """Home route should render chatbot shell with expected hooks."""
    client = main.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "chat-form" in html
    assert "conversation" in html
    assert "UHCCP" in html


def test_uhccp_alias_renders_template():
    """Alias route should continue rendering the same frontend template."""
    client = main.app.test_client()
    response = client.get("/uhccp")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "app-shell" in html
