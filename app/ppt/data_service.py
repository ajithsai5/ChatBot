"""Data access layer for weekly PPT generation.

Responsible only for retrieving and enriching story/feature data.
"""

from __future__ import annotations

import ast
import json
import logging

import requests

LOGGER = logging.getLogger(__name__)

from app.tools.rally_service import get_features, get_user_stories

from .milestone_service import fetch_missing_milestone_user_stories
from .config import debug, get_rally_api_key
from .story_utils import extract_formatted_id, extract_status_from_rally_story


def parse_user_story_response(response_text: str) -> list[dict]:
    if not response_text:
        return []

    marker = None
    if "User Stories found:" in response_text:
        marker = "User Stories found:"
    elif "Features found:" in response_text:
        marker = "Features found:"

    payload = response_text.split(marker, 1)[1].strip() if marker else response_text.strip()
    if not payload:
        return []

    try:
        return json.loads(payload)
    except Exception:
        try:
            return ast.literal_eval(payload)
        except Exception:
            return []


def get_user_story_items(team: str | None = None, iteration: str = "current", ai: bool = True, milestone: bool = True) -> list[dict]:
    args: dict = {}
    if team:
        args["team"] = team
    if iteration:
        args["iteration"] = iteration
    args["ai"] = ai
    args["milestone"] = milestone

    response_text = get_user_stories(args)
    if isinstance(response_text, list):
        return response_text
    if isinstance(response_text, dict):
        return [response_text]
    if isinstance(response_text, str):
        return parse_user_story_response(response_text)
    return []


def get_feature_items(team: str | None = None, iteration: str = "current", ai: bool = True, milestone: bool = True) -> list[dict]:
    args: dict = {}
    if team:
        args["team"] = team
    if iteration:
        args["iteration"] = iteration
    args["ai"] = ai
    args["milestone"] = milestone

    response_text = get_features(args)
    if isinstance(response_text, list):
        return response_text
    if isinstance(response_text, dict):
        return [response_text]
    if isinstance(response_text, str):
        return parse_user_story_response(response_text)
    return []


def get_user_stories_from_rally_api(iteration: str = "current", team: str = "UHCCP", ai: bool = True, milestone: bool = True) -> list[dict]:
    """Get US from HCC Cloud, add missing milestone stories, enrich with Rally BusinessValue + status."""
    team = team or "UHCCP"
    base_stories = get_user_story_items(team, iteration, ai, milestone)
    if not base_stories:
        return []

    rally_api_key = get_rally_api_key()
    if not rally_api_key:
        LOGGER.warning("GPD_RALLY_API_KEY not set — returning HCC Cloud stories without Rally Business Value.")
        return base_stories

    if milestone:
        try:
            base_stories = fetch_missing_milestone_user_stories(base_stories)
        except Exception as e:
            debug(f"Failed to merge missing milestone user stories: {e}")

    try:
        url = "https://rally1.rallydev.com/slm/webservice/v2.0/hierarchicalrequirement"
        headers = {"Accept": "application/json", "ZSESSIONID": rally_api_key}
        cookies = {"ZSESSIONID": rally_api_key}

        formatted_ids: list[str] = []
        for item in base_stories:
            fid = extract_formatted_id(item)
            if fid:
                formatted_ids.append(fid)

        seen = set()
        formatted_ids = [fid for fid in formatted_ids if not (fid in seen or seen.add(fid))]
        if not formatted_ids:
            return base_stories

        business_value_by_id: dict[str, str] = {}
        status_by_id: dict[str, str] = {}
        auth_failed = False

        for fid in formatted_ids:
            if auth_failed:
                break

            try:
                params = {"query": f'(FormattedID = "{fid}")', "fetch": "true"}
                response = requests.get(url, cookies=cookies, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                results = response.json().get("QueryResult", {}).get("Results", [])
                if not results:
                    continue

                story = results[0]
                bv = story.get("c_BusinessValue") or story.get("BusinessValue")
                status = extract_status_from_rally_story(story)

                if bv is None:
                    for key, value in story.items():
                        key_lower = str(key).lower()
                        if key_lower in ("c_businessvalue", "businessvalue"):
                            bv = value
                            break

                if bv is not None:
                    business_value_by_id[fid] = str(bv)
                if status:
                    status_by_id[fid] = status

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    import logging
                    LOGGER.warning("Rally API authentication failed (401). Check GPD_RALLY_API_KEY. Skipping enrichment.")
                    auth_failed = True
                    break
                debug(f"Error fetching {fid}: {e}")
            except Exception as e:
                debug(f"Error fetching {fid}: {e}")

        enriched_count = 0
        unmatched_ids: list[str] = []
        for item in base_stories:
            fid = extract_formatted_id(item)
            if not fid:
                continue

            if fid in business_value_by_id:
                item["c_BusinessValue"] = business_value_by_id[fid]
                item["BusinessValue"] = business_value_by_id[fid]
                enriched_count += 1
            else:
                unmatched_ids.append(fid)

            if fid in status_by_id:
                item["FlowState"] = status_by_id[fid]
                item["State"] = status_by_id[fid]

        debug(f"Sample enriched values: {list(business_value_by_id.items())[:5]}")
        if unmatched_ids:
            debug(f"IDs without Rally BusinessValue (sample): {unmatched_ids[:10]}")

        debug(f"HCC Cloud stories: {len(base_stories)} | Rally BusinessValue enriched: {enriched_count}")
        return base_stories

    except Exception as e:
        import logging
        LOGGER.warning("Error enriching Rally Business Value: %s. Returning HCC Cloud stories only.", e)
        return base_stories

