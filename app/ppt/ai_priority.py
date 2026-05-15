"""AI prioritization helpers for weekly PPT content generation."""

from __future__ import annotations

import logging
import re

from app.chat.search import openaii

LOGGER = logging.getLogger(__name__)

from .config import PRIORITY_AI_MODEL
import app.ppt.config as settings


def format_ai_priority(value: str) -> str:
    labels = {
        "4": "Critical",
        "3": "High",
        "2": "Medium",
        "1": "Low",
    }
    cleaned = (value or "").strip()
    if not cleaned:
        cleaned = "2"
    match = re.search(r"[1-4]", cleaned)
    level = match.group(0) if match else "2"
    return f"{level}[AI] - {labels[level]}"


def heuristic_priority_from_text(text: str) -> str:
    t = (text or "").lower()
    critical_keywords = ["prod down", "outage", "security", "vulnerability", "data loss", "breach", "critical"]
    high_keywords = ["accessibility", "a11y", "not loaded", "error", "failed", "migration", "blocking", "upgrade"]
    medium_keywords = ["enhancement", "report", "analysis", "refactor", "improve", "tool"]

    if any(k in t for k in critical_keywords):
        return format_ai_priority("4")
    if any(k in t for k in high_keywords):
        return format_ai_priority("3")
    if any(k in t for k in medium_keywords):
        return format_ai_priority("2")
    return format_ai_priority("1")


def get_ai_priority(description: str) -> str:
    """Use AI to determine priority (1-4) based on description."""
    if not description:
        return format_ai_priority("2")

    if not settings.AI_PRIORITY_DEPLOYMENT_AVAILABLE:
        return heuristic_priority_from_text(description)

    try:
        messages = [
            {
                "role": "system",
                "content": """You are a priority assessment expert. Analyze the given description and assign a priority level:
- 4: Critical (Security, data loss, system down, blocking major features)
- 3: High (Significant impact, major functionality issues, affects many users)
- 2: Medium (Moderate impact, some feature issues, affects some users)
- 1: Low (Minor issues, cosmetic, affects few users)

Respond with ONLY the priority number (1-4), nothing else.""",
            },
            {
                "role": "user",
                "content": f"Assign priority to this item: {description[:500]}",
            },
        ]

        response = openaii.chat.completions.create(
            model=PRIORITY_AI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=10,
        )

        priority = response.choices[0].message.content.strip()
        return format_ai_priority(priority)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Error getting AI priority: %s", e)
        if "DeploymentNotFound" in str(e):
            settings.AI_PRIORITY_DEPLOYMENT_AVAILABLE = False
        return heuristic_priority_from_text(description)

