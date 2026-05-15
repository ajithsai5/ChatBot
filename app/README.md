# app/

Flask application package for the UHCCP Internal Chatbot.

## Structure

| Directory | Responsibility |
|:---|:---|
| `chat/` | Chat orchestration, Azure AI Search retrieval, LLM response generation, persona configuration, system prompts, and interaction logging. |
| `tools/` | Tool-call subsystem: tool registry, dispatch logic, Rally API integration, and ticketing service integration. |
| `ppt/` | Weekly status PowerPoint generation: data retrieval, milestone lookup, AI priority scoring, and presentation rendering. |
| `link_validator/` | Website link health validation: sitemap discovery, HTTP checking, CSV reporting, scheduling, and chatbot-facing command handlers. |

## Key Files

- `__init__.py` — Application factory (`create_app()`). Creates and configures the Flask instance.
- `routes.py` — All HTTP route handlers registered to the Flask app.
