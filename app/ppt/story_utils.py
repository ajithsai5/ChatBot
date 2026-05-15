"""User-story formatting and utility helpers for PPT workflows.

Shared parsing helpers for Rally/HCC story payloads.
These helpers normalize inconsistent API shapes so the renderer and
data services can stay simple.
"""

from __future__ import annotations


def extract_formatted_id(item: dict) -> str:
    return str(
        item.get("FormattedID")
        or item.get("FormattedId")
        or item.get("ID")
        or item.get("id")
        or ""
    ).strip().upper()


def extract_milestone_ids(milestone_data) -> list[str]:
    """Extract milestone IDs from string/list/dict payload variants.

    Why: Rally and HCC APIs return `Milestones` in different formats.
    """
    milestone_ids: list[str] = []

    if not milestone_data:
        return milestone_ids

    if isinstance(milestone_data, str):
        milestone_ids.append(milestone_data.strip())
    elif isinstance(milestone_data, list):
        for value in milestone_data:
            milestone_ids.extend(extract_milestone_ids(value))
    elif isinstance(milestone_data, dict):
        tags = milestone_data.get("_tagsNameArray")
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, dict):
                    formatted_id = tag.get("FormattedID")
                    if formatted_id:
                        milestone_ids.append(str(formatted_id).strip())
        formatted_id = milestone_data.get("FormattedID")
        if formatted_id:
            milestone_ids.append(str(formatted_id).strip())

    seen: set[str] = set()
    return [mid for mid in milestone_ids if mid and not (mid in seen or seen.add(mid))]


def normalize_rally_milestones(milestone_data):
    """Normalize Rally milestone container to one ID or ID list."""
    milestone_ids = extract_milestone_ids(milestone_data)
    if not milestone_ids:
        return milestone_data
    return milestone_ids[0] if len(milestone_ids) == 1 else milestone_ids


def extract_status_from_rally_story(story: dict) -> str:
    """Return a stable status string from Rally story payload.

    Prefers flow-state naming first, then state/schedule fallbacks.
    """
    flow_state = story.get("FlowState")
    if isinstance(flow_state, dict):
        return str(flow_state.get("_refObjectName") or flow_state.get("Name") or "").strip()
    if flow_state:
        return str(flow_state).strip()

    state = story.get("State")
    if isinstance(state, dict):
        return str(state.get("_refObjectName") or state.get("Name") or "").strip()
    if state:
        return str(state).strip()

    schedule_state = story.get("ScheduleState")
    if schedule_state:
        return str(schedule_state).strip()

    return ""


def extract_current_status(item: dict) -> str:
    """Get current status from normalized story/feature dictionaries."""
    return (
        item.get("FlowState")
        or item.get("flowState")
        or item.get("State")
        or item.get("state")
        or ""
    )


def extract_primary_milestone_id(item: dict) -> str | None:
    """Return the first milestone ID used for release-target rendering."""
    milestone_data = item.get("Milestones") or item.get("milestones")
    if isinstance(milestone_data, list) and milestone_data:
        return str(milestone_data[0]).strip()
    if milestone_data:
        return str(milestone_data).strip()
    return None

