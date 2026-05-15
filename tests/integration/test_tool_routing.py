"""Integration tests for tool routing and fallback behavior."""

from app.chat import orchestrator


def test_rally_query_detection_handles_id_and_keywords():
    """Rally detection should work for IDs and keyword prompts."""
    assert orchestrator.is_rally_query("show US12345") is True
    assert orchestrator.is_rally_query("latest release report") is True
    assert orchestrator.is_rally_query("hello world") is False


def test_web_link_validator_query_detection_handles_variants():
    """Web link validator detection should match canonical and typo variants."""
    assert orchestrator.is_web_link_validator_query("run web link validator now") is True
    assert orchestrator.is_web_link_validator_query("link checker status") is True
    assert orchestrator.is_web_link_validator_query("link cheaker for site") is True
    assert orchestrator.is_web_link_validator_query("what is sprint velocity") is False


def test_weekly_ppt_intent_detection_handles_misspellings():
    """Weekly PPT intent parser should preserve fuzzy matching behavior."""
    assert orchestrator.is_weekly_ppt_request("please gererate weekly ppt") is True
    assert orchestrator.is_weekly_ppt_request("generate slides for weekly status") is True
    assert orchestrator.is_weekly_ppt_request("summarize incidents") is False
