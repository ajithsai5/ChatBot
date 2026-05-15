"""Configuration settings for PPT automation workflows."""

from __future__ import annotations

import os

# AI model used for priority scoring.
PRIORITY_AI_MODEL = os.getenv("PRIORITY_AI_MODEL", "").strip()
AI_PRIORITY_DEPLOYMENT_AVAILABLE = bool(PRIORITY_AI_MODEL)

# Runtime debug toggle.
PPT_DEBUG = os.getenv("PPT_DEBUG", "").strip().lower() in {"1", "true", "yes"}

# Shared cache for milestone lookups.
MILESTONE_RELEASE_CACHE = {
    "upcoming_release": None,
    "milestone_dates": {},
    "milestone_info": {},
    "milestone_names": {},
}


def debug(message: str) -> None:
    """Emit debug logs only when PPT_DEBUG mode is enabled."""
    if PPT_DEBUG:
        import logging
        logging.getLogger(__name__).debug("%s", message)


def get_rally_api_key() -> str | None:
    """Return Rally API key from environment if configured."""
    return os.getenv("GPD_RALLY_API_KEY") or None

