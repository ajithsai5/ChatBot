"""Chatbot orchestration and response composition for UHCCP workflows.

Main responsibility:
- Route user queries to the correct handler (Rally tools, link validator,
  Azure Search, or PPT generator).
- Compose final responses by combining tool data, search results, and
  LLM completions.
- Provide intent detection for weekly PPT generation and web link validator.

Not handled here:
- Search retrieval internals (see search.py).
- Tool registry and dispatch mechanics (see tools/dispatcher.py).
- PPT rendering (see ppt/generator.py).
"""

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from app.chat.prompts import uhccp_chat_system_message
from app.chat.search import (
    get_vectorized_query,
    search_documents,
    single_chatbot_response,
    openai_chat_client,
)

from app.chat.personas import personas
from app.tools.dispatcher import tool_call

from config import env, AZURE_AI_Service_KEY
from app.chat.logger import ChatbotLogger
import datetime
import os
import requests
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
import logging

from app.ppt.generator import fill_weekly_status_ppt, DEFAULT_TEMPLATE, DEFAULT_OUTPUT
from app.link_validator.response_checker import check_response_urls


LOGGER = logging.getLogger(__name__)

AZURE_AI_SERVICE_LLM_ENDPOINT = (
    "https://gpdacq-dev-1-eastus-openai.openai.azure.com/openai/deployments/UHCCP_ChatBot"
)

client = ChatCompletionsClient(
    endpoint=AZURE_AI_SERVICE_LLM_ENDPOINT,
    credential=AzureKeyCredential(AZURE_AI_Service_KEY),
)


# ---------------------------------------------------------------------------
# Primary chatbot response handler
# ---------------------------------------------------------------------------

def get_chatbot_response(
    question: str,
    prt: bool = False,
    prt_data: dict | None = None,
    history: list | None = None,
    username: str | None = None,
) -> dict:
    """Return chatbot response for user input while preserving route contract shape.

    Orchestrates the full response lifecycle: intent detection, tool dispatch,
    Azure Search retrieval, LLM completion, and inline URL health checking.
    """
    history = history if history is not None else []

    persona_obj = personas["uhccp"]

    logger = ChatbotLogger()
    logger.set_environment("Dev" if env.DEVELOPMENT else "Prod")

    messages = [
        {
            "role": "system",
            "content": (
                persona_obj.get("system_message", uhccp_chat_system_message)
                + f" Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}"
            ),
        }
    ]
    search_client = persona_obj.get("search_client")

    logger.set_question(question)
    LOGGER.debug("Received question for processing.")

    # Check if the user is requesting a weekly PPT before doing any search.
    ppt_response = maybe_generate_weekly_ppt(question)
    if ppt_response:
        logger.set_answer(ppt_response)
        logger.send_to_logstash()
        return {"response": ppt_response}

    if username and username.strip():
        logger.set_username(username.strip())
    else:
        logger.set_username("anonymous")

    rally_query = is_rally_query(question)
    link_validator_query = is_web_link_validator_query(question)
    # Append iteration/release metadata if referenced in the query.
    question += rally_iteration_release_parse(question)
    LOGGER.debug("Question normalized for routing.")

    search = question
    url_info: list = []
    team_contact = ""

    if rally_query or link_validator_query:
        LOGGER.debug("Routing query through tool path.")
        outdata, tools_data, props = tool_call(
            persona=persona_obj,
            user_input=question,
            search=search,
            logger=logger,
            history=history,
            team_contact=team_contact,
        )
        # Web link validator tools return user-facing strings directly.
        if link_validator_query:
            if tools_data:
                valid = [str(t) for t in tools_data if t]
                if valid:
                    result = "\n".join(valid)
                    logger.set_answer(result)
                    logger.send_to_logstash()
                    return {"response": result}
            # LLM didn't pick a tool — dispatch via keyword fallback.
            from app.link_validator.handlers import _dispatch_web_link_validator_query

            result = _dispatch_web_link_validator_query(question)
            logger.set_answer(result)
            logger.send_to_logstash()
            return {"response": result}
    else:
        LOGGER.debug("Routing query through Azure Search path.")
        outdata, tools_data, props = "", None, {"long_res": False}

    long_res = props["long_res"]

    # Replace formatting artifacts that interfere with rendering.
    outdata = outdata.replace(".0", ".O").replace("<img", "<p")

    if "on call" in search.lower() or "count" in search.lower():
        search += ". Today is " + str(datetime.datetime.now().strftime("%A, %B %d, %Y"))
    LOGGER.debug("Search query prepared for retrieval.")

    # Build the search result — either from tool data or vector retrieval.
    search_result = None
    if (rally_query or link_validator_query) and tools_data:
        valid_tool_data = [str(t) for t in tools_data if t]
        LOGGER.debug("Tool/Rally data items: %s", len(valid_tool_data))
        if valid_tool_data:
            search_result = {
                "role": "user",
                "content": "question: " + search + "\nData : " + "\n".join(valid_tool_data),
                "search_mode": "rally",
            }

    if search_result is None:
        vector_query = get_vectorized_query(search)
        search_result = search_documents(search, [vector_query])
        LOGGER.debug("Retrieval mode: %s", search_result.get("search_mode", "unknown"))

    data = search_result.get("content", "NO Info").strip()
    file_link = search_result.get("file_link")
    file_name = search_result.get("file_name")

    if not data or data == "NO info":
        return {"response": "NO Info"}

    # Merge any remaining tool data into the retrieval context.
    if tools_data and search_result.get("search_mode") != "rally":
        LOGGER.debug("Appending tool/rally data count: %s", len(tools_data))
        for tool_data in tools_data:
            search_result["content"] += f"\n{tool_data}"
    elif not tools_data:
        LOGGER.debug("No tool/rally data appended.")

    messages.append(search_result)

    # Propagate URL info into the caller's prt_data dict.
    if prt_data is not None:
        if "links" in prt_data:
            prt_data["links"] = prt_data["links"]
        else:
            prt_data["links"] = url_info
    else:
        prt_data = {"links": url_info}

    chat_response = single_chatbot_response(
        messages, outdata, long_res=long_res, logger=logger, prt_data=prt_data
    )

    # Append a source-document link when the response came from Azure Search.
    if file_link and not tools_data:
        chat_response += (
            f"\n\n\nFor more information, refer to the given files: [{file_name}]({file_link})"
        )

    # Inline URL health check for URLs surfaced in the LLM response.
    try:
        url_footer = check_response_urls(chat_response)
        if url_footer:
            chat_response += url_footer
    except Exception as exc:
        LOGGER.warning("[inline-url-check] Non-blocking failure: %s", exc)

    return {"response": chat_response}


# ---------------------------------------------------------------------------
# Rally metadata helpers
# ---------------------------------------------------------------------------

def rally_iteration_release_parse(search: str) -> str:
    """Append latest iteration/release metadata when requested in query text."""
    res = ""
    if "iteration" in search.lower() or "sprint" in search.lower():
        res += "\n" + str(get_latest_iterations())
    if "release" in search.lower():
        res += "\n" + str(get_latest_releases())

    LOGGER.debug("Rally iteration/release parse completed.")
    return res

# ---------------------------------------------------------------------------
# Intent detection helpers
# ---------------------------------------------------------------------------

def is_rally_query(search: str) -> bool:
    """Return True when the user's input likely targets Rally data."""
    if not search:
        return False
    text = search.lower()
    rally_keywords = (
        "rally", "user story", "user stories", "feature", "features",
        "defect", "defects", "iteration", "sprint", "release",
        "capability", "capabilities", "milestone", "ppm",
    )
    if any(keyword in text for keyword in rally_keywords):
        return True
    # Match artifact IDs such as US1234, DE567, F890.
    if re.search(r"\b(us|de|f)\d+\b", text, flags=re.IGNORECASE):
        return True
    return False


def is_web_link_validator_query(search: str) -> bool:
    """Return True when the user's input targets the web link validator."""
    if not search:
        return False
    text = search.lower()
    link_validator_keywords = (
        "link checker", "link check", "broken link", "link health",
        "scan links", "check links", "dead link", "link report",
        "site health", "website health", "cancel link", "stop link",
        "email link", "send link report", "mail link report", "email report",
        "linker checker", "linker check", "linkchecker", "link cheaker",
        "run link", "start link", "link scan", "link status",
        "web link validator", "link validator", "web link validation",
    )
    return any(kw in text for kw in link_validator_keywords)


# ---------------------------------------------------------------------------
# External data helpers
# ---------------------------------------------------------------------------

def get_latest_releases() -> str:
    """Return latest release summary from tickets endpoint."""
    url = f"{env.get_tickets_endpoint()}/uhccp/releases"
    res = requests.get(url, verify="./optum.pem")
    return f"Recent Releases found: {res.json()}"


def get_latest_iterations() -> str:
    """Return latest iteration summary from tickets endpoint."""
    url = f"{env.get_tickets_endpoint()}/uhccp/iterations"
    res = requests.get(url, verify="./optum.pem")
    return f"Recent Iterations found: {res.json()}"


# ---------------------------------------------------------------------------
# Legacy chatbot response path
# ---------------------------------------------------------------------------

def chat_bot_response(question: str) -> dict:
    """Legacy chatbot response path used by the /chatbot route.

    Performs a direct vector search and single LLM completion without
    tool routing or follow-up question generation.
    """
    vector_query = get_vectorized_query(question)
    search_result = search_documents(question, [vector_query])

    data = search_result.get("content", "NO Info").strip()
    file_link = search_result.get("file_link")
    file_name = search_result.get("file_name")

    LOGGER.debug("Legacy route file metadata prepared.")

    if not data or data == "NO info":
        return {"response": "NO Info"}

    legacy_messages = [
        {
            "role": "system",
            "content": (
                "You are an AI assistant developed by the UHCCP Dev Ops Team to assist "
                "users in obtaining information for the UHCCP team. Your responses should "
                "be accurate, contextually relevant to the user's input, and directly "
                "address the query. Ensure that your answers are clear, concise, and "
                "refrain from using third-person pronouns. If the provided data does not "
                "contain the required information, respond with 'NO info'. If the user's "
                "input is unclear, respond with 'Please provide more information'."
            ),
        }
    ]
    content = f"Question: {question}\nData: {data}"
    legacy_messages.append({"role": "user", "content": content})

    response = client.complete(
        messages=legacy_messages,
        temperature=0.5,
        max_tokens=1500,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None,
    )
    chat_response = response.choices[0].message.content.strip()

    LOGGER.debug("Legacy route file link appended to response when available.")
    if file_link:
        chat_response += (
            f"\n\n\nFor more information, refer to the given files: [{file_name}]({file_link})"
        )
    return {"response": chat_response}


# ---------------------------------------------------------------------------
# PPT generation helpers
# ---------------------------------------------------------------------------

def _get_env_int(name: str, default: int) -> int:
    """Read an integer from the environment, returning *default* on failure."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def cleanup_old_ppts(max_age_hours: int = 2, max_count: int = 3) -> None:
    """Remove old PPT files to prevent disk filling.

    Deletes files older than *max_age_hours* first, then keeps only the
    newest *max_count* files if the directory is still over the limit.
    """
    try:
        ppts_dir = Path("generated_ppts")
        if not ppts_dir.exists():
            return
        
        # Get all .pptx files with their modification times
        ppt_files = [(f, f.stat().st_mtime) for f in ppts_dir.glob("*.pptx")]
        
        # Remove files older than max_age_hours
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        for file_path, mtime in ppt_files:
            if current_time - mtime > max_age_seconds:
                file_path.unlink(missing_ok=True)
        
        # If still too many files, keep only the newest max_count
        remaining_files = sorted(
            [(f, f.stat().st_mtime) for f in ppts_dir.glob("*.pptx")],
            key=lambda x: x[1],
            reverse=True
        )
        if len(remaining_files) > max_count:
            for file_path, _ in remaining_files[max_count:]:
                file_path.unlink(missing_ok=True)
    except Exception as exc:
        LOGGER.warning("PPT cleanup warning: %s", exc)


def _normalize_text(text: str) -> str:
    """Strip punctuation and collapse whitespace for fuzzy-matching."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _fuzzy_contains_token(
    tokens: list[str], targets: tuple[str, ...], threshold: float = 0.82
) -> bool:
    """Return True if any token fuzzy-matches one of the target words."""
    target_set = set(targets)
    for token in tokens:
        if token in target_set:
            return True
        for target in targets:
            if SequenceMatcher(None, token, target).ratio() >= threshold:
                return True
    return False


def _is_weekly_ppt_request(question: str) -> bool:
    """Detect whether the user is asking for a weekly status PPT.

    Uses fuzzy matching so common typos (e.g. ``weeklt``) still trigger.
    """
    normalized = _normalize_text(question)
    if not normalized:
        return False

    tokens = normalized.split()

    wants_generate = _fuzzy_contains_token(
        tokens,
        ("generate", "create", "build", "make", "prepare", "produce", "share"),
        threshold=0.78,
    )
    wants_ppt = (
        _fuzzy_contains_token(
            tokens, ("ppt", "pptx", "powerpoint", "slides", "deck"), threshold=0.75
        )
        or "weekly status" in normalized
    )
    wants_weekly = (
        _fuzzy_contains_token(
            tokens, ("weekly", "week", "weeklt", "wekly", "wekli"), threshold=0.72
        )
        or "weekly status" in normalized
    )

    return wants_generate and wants_ppt and wants_weekly


def is_weekly_ppt_request(question: str) -> bool:
    """Public wrapper for weekly PPT intent detection."""
    return _is_weekly_ppt_request(question)


def generate_weekly_ppt_with_progress(
    question: str, progress_callback=None
) -> str | None:
    """Generate a weekly-status PPT, calling *progress_callback* for SSE updates.

    Returns a user-facing message string with the download link on success,
    or None when the question does not match the PPT intent.
    """
    if not question:
        return None

    if not _is_weekly_ppt_request(question):
        return None

    template_path = Path(DEFAULT_TEMPLATE)

    # Create a unique filename so concurrent requests never collide.
    from datetime import datetime as _dt

    timestamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"Weekly-Status-{timestamp}.pptx"
    output_path = Path("generated_ppts") / output_filename

    if not template_path.exists():
        return (
            "Weekly PPT template not found. "
            "Please add templates/Weekly-Status-Template.pptx and try again."
        )

    try:
        output, filled_rows, pages_created = fill_weekly_status_ppt(
            template_path,
            output_path,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        return f"Failed to generate the weekly PPT: {exc}"

    # Prevent disk from filling up with stale generated files.
    cleanup_old_ppts(
        max_age_hours=_get_env_int("PPT_MAX_AGE_HOURS", 2),
        max_count=_get_env_int("PPT_MAX_COUNT", 3),
    )

    public_path = f"/uhccp-internal-chatbot/{output.name}"
    return (
        f"Weekly PPT generated: [{public_path}]({public_path}). "
        f"User stories filled: {filled_rows} across {pages_created} page(s)."
    )


def maybe_generate_weekly_ppt(question: str) -> str | None:
    """Non-streaming entry point for weekly PPT intent check and generation."""
    return generate_weekly_ppt_with_progress(question, progress_callback=None)