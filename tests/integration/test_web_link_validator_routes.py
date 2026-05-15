"""Integration tests for web-link-validator report routes."""

import main


def test_report_route_rejects_invalid_run_id():
    """Report route should reject path traversal and malformed run IDs."""
    client = main.app.test_client()
    response = client.get("/web-link-validator/report/../bad")

    assert response.status_code == 400


def test_summary_route_rejects_invalid_run_id():
    """Summary route should reject invalid run IDs."""
    client = main.app.test_client()
    response = client.get("/web-link-validator/summary/../bad")

    assert response.status_code == 400


def test_verified_route_rejects_invalid_run_id():
    """Verified route should reject invalid run IDs."""
    client = main.app.test_client()
    response = client.get("/web-link-validator/verified/../bad")

    assert response.status_code == 400
