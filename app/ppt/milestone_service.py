"""Milestone integration service.

Handles blob release date lookup and Rally milestone/story expansion.
"""

from __future__ import annotations

import logging
from datetime import date

import requests

from .config import MILESTONE_RELEASE_CACHE, debug, get_rally_api_key
from .story_utils import extract_formatted_id, extract_milestone_ids, normalize_rally_milestones

LOGGER = logging.getLogger(__name__)


def get_milestone_release_mapping(ref_date: date | None = None) -> str | None:
    """Fetch upcoming release date from blob API."""
    if MILESTONE_RELEASE_CACHE.get("upcoming_release"):
        return MILESTONE_RELEASE_CACHE.get("upcoming_release")

    if ref_date is None:
        ref_date = date.today()

    date_str = ref_date.strftime("%Y-%m-%d")
    url = f"https://hcccloud-uhgdlm-dtlapi-dev.uhc.com/gpd-backend-python/fetch-uhccp-blob-by-date?date={date_str}"

    try:
        response = requests.get(url, verify="./optum.pem", timeout=30)
        response.raise_for_status()
        data = response.json()

        upcoming_release = None
        if isinstance(data, dict):
            metrics = data.get("metrics")
            if isinstance(metrics, dict):
                servicenow = metrics.get("servicenow")
                if isinstance(servicenow, dict):
                    upcoming_release = servicenow.get("upcoming_release")
                    if upcoming_release:
                        debug(f"Found upcoming_release in blob response: {upcoming_release}")

        if not upcoming_release and isinstance(data, dict):
            for key1, value1 in data.items():
                if isinstance(value1, dict):
                    for key2, value2 in value1.items():
                        if isinstance(value2, dict) and "upcoming_release" in value2:
                            upcoming_release = value2["upcoming_release"]
                            debug(f"Found upcoming_release in data['{key1}']['{key2}']")
                            break
                if upcoming_release:
                    break

        MILESTONE_RELEASE_CACHE["upcoming_release"] = upcoming_release
        if upcoming_release:
            LOGGER.debug("Loaded upcoming release date: %s", upcoming_release)
        else:
            LOGGER.warning("No upcoming_release found in blob API response.")

        return upcoming_release
    except Exception as e:
        LOGGER.warning("Error fetching upcoming release from blob API: %s", e)
        return None


def parse_milestone_name_to_date(milestone_name: str) -> str | None:
    if not milestone_name:
        return None
    parts = milestone_name.split("_")
    year = next((part for part in parts if part.isdigit() and len(part) == 4), None)
    month = parts[-2] if len(parts) >= 3 else None
    day = parts[-1] if len(parts) >= 3 else None

    month_map = {
        "Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr",
        "May": "May", "Jun": "Jun", "Jul": "Jul", "Aug": "Aug",
        "Sep": "Sep", "Oct": "Oct", "Nov": "Nov", "Dec": "Dec",
    }
    if year and month in month_map and day and day.isdigit():
        return f"{month_map[month]} {int(day)} {year}"
    return None


def get_milestone_info_from_rally(milestone_id: str) -> dict | None:
    if not milestone_id:
        return None

    cached = MILESTONE_RELEASE_CACHE["milestone_info"].get(milestone_id)
    if cached:
        return cached

    rally_api_key = get_rally_api_key()
    if not rally_api_key:
        return None

    try:
        url = "https://rally1.rallydev.com/slm/webservice/v2.0/milestone"
        headers = {"Accept": "application/json", "ZSESSIONID": rally_api_key}
        cookies = {"ZSESSIONID": rally_api_key}
        params = {
            "query": f'(FormattedID = "{milestone_id}")',
            "fetch": "_ref,ObjectID,Name,Workspace,TargetDate",
            "pagesize": "1",
        }
        response = requests.get(url, cookies=cookies, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        results = response.json().get("QueryResult", {}).get("Results", [])
        if not results:
            return None

        result = results[0]
        info = {
            "formatted_id": milestone_id,
            "name": result.get("Name"),
            "object_id": result.get("ObjectID"),
            "target_date": result.get("TargetDate"),
            "workspace_ref": (result.get("Workspace") or {}).get("_ref"),
        }
        MILESTONE_RELEASE_CACHE["milestone_info"][milestone_id] = info
        if info.get("name"):
            MILESTONE_RELEASE_CACHE["milestone_names"][milestone_id] = info["name"]
        return info
    except Exception as e:
        debug(f"Failed to fetch milestone {milestone_id} from Rally: {e}")
        return None


def get_milestone_name_from_rally(milestone_id: str) -> str | None:
    if not milestone_id:
        return None

    cached = MILESTONE_RELEASE_CACHE["milestone_names"].get(milestone_id)
    if cached:
        return cached

    info = get_milestone_info_from_rally(milestone_id)
    if info and info.get("name"):
        return info["name"]
    return None


def get_milestone_release_date(milestone_id: str) -> str | None:
    if not milestone_id:
        return None

    cached_date = MILESTONE_RELEASE_CACHE["milestone_dates"].get(milestone_id)
    if cached_date:
        return cached_date

    name = get_milestone_name_from_rally(milestone_id)
    if name:
        parsed = parse_milestone_name_to_date(name)
        if parsed:
            MILESTONE_RELEASE_CACHE["milestone_dates"][milestone_id] = parsed
            return parsed
        return name
    return None


def fetch_missing_milestone_user_stories(base_stories: list[dict]) -> list[dict]:
    """Add missing user stories from Rally for milestones present in the base list."""
    rally_api_key = get_rally_api_key()
    if not rally_api_key or not base_stories:
        return base_stories

    existing_ids = {extract_formatted_id(item) for item in base_stories if extract_formatted_id(item)}

    milestone_ids: list[str] = []
    for item in base_stories:
        milestone_ids.extend(extract_milestone_ids(item.get("Milestones") or item.get("milestones")))

    seen_milestones: set[str] = set()
    milestone_ids = [mid for mid in milestone_ids if mid and not (mid in seen_milestones or seen_milestones.add(mid))]
    if not milestone_ids:
        return base_stories

    headers = {"Accept": "application/json", "ZSESSIONID": rally_api_key}
    cookies = {"ZSESSIONID": rally_api_key}
    url = "https://rally1.rallydev.com/slm/webservice/v2.0/hierarchicalrequirement"

    merged_stories = list(base_stories)
    added_count = 0

    for milestone_id in milestone_ids:
        info = get_milestone_info_from_rally(milestone_id)
        object_id = (info or {}).get("object_id")
        workspace_ref = (info or {}).get("workspace_ref")
        if not object_id or not workspace_ref:
            continue

        start = 1
        page_size = 200
        total_count = None

        while total_count is None or start <= total_count:
            params = {
                "query": f"(Milestones contains /milestone/{object_id})",
                "fetch": "FormattedID,Name,Milestones,FlowState,State",
                "workspace": workspace_ref,
                "pagesize": str(page_size),
                "start": str(start),
            }
            response = requests.get(url, cookies=cookies, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            query_result = response.json().get("QueryResult", {})
            total_count = query_result.get("TotalResultCount", 0)
            results = query_result.get("Results", [])
            if not results:
                break

            for story in results:
                formatted_id = extract_formatted_id(story)
                if not formatted_id or formatted_id in existing_ids:
                    continue
                story["Milestones"] = normalize_rally_milestones(story.get("Milestones"))
                merged_stories.append(story)
                existing_ids.add(formatted_id)
                added_count += 1

            start += page_size

    if added_count:
        debug(f"Added {added_count} missing milestone user stories from Rally")

    return merged_stories

