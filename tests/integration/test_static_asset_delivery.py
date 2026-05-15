"""Static asset delivery regression tests."""

import main


def test_stylesheet_route_serves_css():
    """Stylesheet should remain accessible under static route alias."""
    client = main.app.test_client()
    response = client.get("/uhccp-internal-chatbot/static/styles.css")

    assert response.status_code == 200
    assert "text/css" in response.mimetype
    css = response.get_data(as_text=True)
    assert ".app-shell" in css


def test_script_route_serves_javascript():
    """Script should remain accessible under static route alias."""
    client = main.app.test_client()
    response = client.get("/uhccp-internal-chatbot/static/scripts.js")

    assert response.status_code == 200
    assert "javascript" in response.mimetype or "text/plain" in response.mimetype
    script = response.get_data(as_text=True)
    assert "sendMessage" in script
