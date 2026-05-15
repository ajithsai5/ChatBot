"""Tool-call formatting and dispatch helpers for routed chatbot requests.

Main responsibility:
- Convert tool-registry entries into OpenAI function-call schemas.
- Invoke resolved tool functions with dynamic arguments extracted from
  the LLM tool-call response.

Not handled here:
- Tool definitions or implementations (see registry.py, rally_service.py).
- LLM model configuration or persona selection.
"""

from app.tools.registry import tools
from app.chat.search import openaii

import json
import logging


LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema formatting helpers
# ---------------------------------------------------------------------------

def tool_list_format_obj(obj: dict) -> dict | None:
    """Format one tool entry into the OpenAI tool-call schema.

    Only ``function`` type tools are supported; other types are skipped.
    """
    if obj["type"] != "function":
        LOGGER.debug("Unknown tool type encountered during format.")
        return None

    return {
        "type": "function",
        "function": {
            "name": obj["name"],
            "description": obj["description"],
            "parameters": obj["parameters"],
            "result": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }


def create_tool_list(tool_list: list[str]) -> list[dict]:
    """Build a list of formatted tool definitions from registry names."""
    formatted_tool_list: list[dict] = []
    for tool_name in tool_list:
        if tool_name in tools:
            formatted_tool_list.append(
                tool_list_format_obj({"name": tool_name, **tools[tool_name]})
            )
    return formatted_tool_list


def create_tool_functions(tool_list: list[str]) -> dict:
    """Build a map of callable tool function metadata keyed by tool name."""
    formatted_tool_list: dict = {}
    for tool_name in tool_list:
        if tool_name in tools:
            formatted_tool_list[tool_name] = {"name": tool_name, **tools[tool_name]}
    return formatted_tool_list


# ---------------------------------------------------------------------------
# Tool invocation
# ---------------------------------------------------------------------------

def tool_call_format_obj(
    obj: dict,
    user_input: str,
    search: str = "",
    logger=None,
    team_contact: str = "",
    history: list | None = None,
) -> object:
    """Invoke one resolved tool function with dynamic arguments.

    Extra context (user_input, search, logger, history) is injected only
    when the tool's metadata flags them as required.
    """
    if "function" not in obj or "args" not in obj:
        return None

    args: dict = {"args": obj["args"]}
    if obj.get("user_input"):
        args["user_input"] = user_input
    if obj.get("search"):
        args["search"] = search
    if obj.get("logger"):
        args["logger"] = logger
    if obj.get("history"):
        args["history"] = history

    return obj["function"](**args)


# ---------------------------------------------------------------------------
# Orchestration entry point
# ---------------------------------------------------------------------------

def tool_call(
    persona: dict,
    user_input: str,
    search: str = "",
    team_contact: str = "",
    logger=None,
    history: list | None = None,
) -> tuple[str, list | None, dict]:
    """Resolve and execute tool calls for a persona prompt.

    Returns a tuple of (outdata, return_data, props) where *return_data*
    is None when the LLM chose no tools.
    """
    messages_input = persona["message"](user_input)

    if history:
        messages_input[1]["content"] += (
            f"\n\nHere is the last few questions and responses in ask order: {history}."
        )

    tool_list = create_tool_list(persona["tools"])
    tool_funcs = create_tool_functions(persona["tools"])

    completion = openaii.chat.completions.create(
        model="UHCCP_ChatBot",
        messages=messages_input,
        max_tokens=600,
        temperature=0.4,
        top_p=1,
        tools=tool_list,
    )
    finish_reason = completion.choices[0].finish_reason
    return_data: list = []
    outdata = ""
    props: dict = {"long_res": False}

    LOGGER.debug("Tool selection finish reason: %s", finish_reason)

    if finish_reason == "stop":
        if logger:
            logger.set_ask_type("Doc Search")
        return outdata, None, props

    if finish_reason == "tool_calls":
        LOGGER.debug("Tool calls returned: %s", completion.choices[0].message.tool_calls)
        for single_tool_call in completion.choices[0].message.tool_calls:
            LOGGER.debug("Executing tool function: %s", single_tool_call.function.name)

            args = json.loads(single_tool_call.function.arguments)
            if single_tool_call.function.name in tool_funcs:
                func_meta = tool_funcs[single_tool_call.function.name]
                if func_meta.get("long_res"):
                    props["long_res"] = True
                if isinstance(func_meta.get("doc_count"), int):
                    props["doc_count"] = func_meta["doc_count"]
                    LOGGER.debug("Tool doc_count override: %s", props["doc_count"])
                return_data.append(
                    tool_call_format_obj(
                        obj={"args": args, **func_meta},
                        user_input=user_input,
                        search=search,
                        logger=logger,
                        team_contact=team_contact,
                        history=history,
                    )
                )
            else:
                LOGGER.warning("Tool not found in registry: %s", single_tool_call.function.name)
                return_data.append(None)

    return outdata, return_data, props