"""Persona configuration and tool-routing metadata for chatbot orchestration.

Main responsibility:
- Build persona dictionaries that pair a system prompt, search index,
  and available tool list for each supported chatbot identity.

Not handled here:
- Tool execution logic (see tools/dispatcher.py).
- Search retrieval (see chat/search.py).
"""

import datetime
from app.tools.registry import tools
from app.chat.search import SearchClient, azure_credential


def get_persona_tool_call_messages(user_input: str) -> list[dict]:
    """Build system/user message pair for tool-selection prompts.

    If the user intent does not require a tool, the LLM should respond
    with 'N/A' immediately to avoid unnecessary function invocations.
    """
    return [
        {
            "role": "system",
            "content": (
                "You only respond if there is a tool call. If the user does not need to call "
                "any functions then exit quick with response 'N/A'. "
                f"Today is {datetime.datetime.now()}."
            ),
        },
        {"role": "user", "content": user_input},
    ]


def set_search_client(persona: dict) -> dict:
    """Attach an Azure Search client to a persona when search config is present.

    Returns a shallow copy of the persona dict with a ``search_client`` key
    so the original is never mutated.
    """
    if "search_service" not in persona or "search_index" not in persona:
        return persona

    return {
        **persona,
        "search_client": SearchClient(
            endpoint=f"https://{persona['search_service']}.search.windows.net",
            index_name=persona["search_index"],
            credential=azure_credential,
        ),
    }


# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

_UHCCP_PERSONA_CONFIG: dict = {
    "message": get_persona_tool_call_messages,
    "search_service": "gpdacq-dev-1-eastus-ai-search-cog-svc",
    "search_index": "uhccp-vector",
    "vbf_contacts": False,
    "tools": [
        "get_user_stories",
        "get_features",
        "get_current_iterations",
        "get_current_releases",
        "get_rally_obj_info",
        "get_capabilites",
        "get_defects",
        "get_release_defects",
        "get_release_features",
        "get_user_story_states",
        "get_features_states",
        "get_latest_inc",
        "get_ticket_details",
        "get_latest_prb",
        "get_latest_chg",
        "get_related_tickets",
        "get_related_stories",
        "get_dynatrace_problems",
        "get_splunk_report",
        "get_traffic_error_report",
        "get_performance_report",
        "get_performance_score",
        "get_crux_report",
        "get_web_link_validator_status",
        "run_web_link_validator_now",
        "get_web_link_validator_report",
        "cancel_web_link_validator_run",
        "email_web_link_validator_report",
    ],
}

personas: dict[str, dict] = {
    "uhccp": set_search_client(_UHCCP_PERSONA_CONFIG),
}