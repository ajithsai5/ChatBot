"""Rally integration helpers for fetching delivery artifacts and metadata.

Main responsibility:
- Communicate with the tickets/Rally proxy service to fetch user stories,
  features, defects, capabilities, iterations, and releases.
- Provide formatted response strings consumed by the chatbot orchestrator.

Not handled here:
- LLM tool-call resolution or schema registration (see dispatcher.py, registry.py).
"""

import datetime
import logging
import os

import requests

from config import env
from app.chat.search import get_embeddings


LOGGER = logging.getLogger(__name__)

rally_teams: list[str] = []
NO_TEAM_MESSAGE = (
    "No team specified. A team must be mentioned to get information on. "
    "Ask the user to ask again with a team in mind."
)

_RALLY_DEBUG = os.getenv(
    "RALLY_DEBUG", os.getenv("PPT_DEBUG", "")
).strip().lower() in {"1", "true", "yes"}
_HTTP_TIMEOUT_SECONDS = int(os.getenv("RALLY_HTTP_TIMEOUT_SECONDS", "45"))


def _debug(message: str) -> None:
    """Emit a debug message only when the RALLY_DEBUG env flag is active."""
    if _RALLY_DEBUG:
        LOGGER.debug(message)

def set_rally_teams() -> None:
    """Populate the global rally_teams list from the tickets service."""
    _debug("Setting Rally Teams...")
    if len(rally_teams) == 0:
        _debug(f"{env.get_tickets_endpoint()}/uhccp/teams")
        for team in requests.get(
            f"{env.get_tickets_endpoint()}/uhccp/teams", verify="./optum.pem"
        ).json():
            rally_teams.append(team)
    _debug(f"{rally_teams}")

def get_allowed_teams(args=None) -> str:
    """Return the list of Rally teams available for queries."""
    if len(rally_teams) == 0:
        set_rally_teams()
    return f"Here are the teams they are asking for found in Rally: {rally_teams}"

def get_rally_messages(user_input: str) -> list[dict]:
    """Build system/user message pair for Rally-specific tool selection."""
    _debug(f"Get rally messages. User Input: {user_input}")
    return [
        {"role": "system","content": f"You only respond if there is a tool call. A sprint is equal to the last two weeks. Never change the capitalization of sprints, iterations, or releases. If the user does not need to call any functions then exit quick with response 'N/A'. Today is {datetime.datetime.now()}. For data in a whole month, use the first of the current month to the first of the next month. Match a team name to one in the list if the user comes close to one. Do not pick a team if the user does not mention any. The only teams that can be used are Teams: {rally_teams}"},
        {"role": "user", "content": user_input}
    ]

def user_story_template(args: dict, endpoint: str) -> str:
    """Fetch user stories from the tickets service and format a summary string."""
    _debug(f"Function:user_story_template, args: {args}, endpoint: {endpoint}")

    team = args['team'] if 'team' in args else None

    if not team:
        return NO_TEAM_MESSAGE

    _debug(f"Using team: {team}")

    iteration = args.get('iteration',None)
    release = args.get('release',None)
    feature = args.get('feature',None)
    from_date = args.get('from_date',None)
    to_date = args.get('to_date',None)
    response_str = ''
    if not iteration and not release and not feature:
        try:
            iteration_url = f'{env.get_tickets_endpoint()}/uhccp/{team}/iterations/current'
            response = requests.get(iteration_url,verify='./optum.pem')
            iteration = response.json()[0]['Name']
            response_str += f"Since none specified, using Current Iteration: {iteration}\n"
        except Exception as exc:
            LOGGER.warning("Failed to resolve current iteration for team %s: %s", team, exc)
            return f"This team, {team}, is unavailable for metrics."
    try:
        url = f'{env.get_tickets_endpoint()}/uhccp/{team}/user_stories{"/" if len(endpoint) > 0 else ""}{endpoint}'
        if iteration:
            url += f'?iteration={iteration}'
        elif feature:
            url += f'?feature={feature}'
        elif release:
            url += f'?release={release}'
        if from_date:
            url += f'&from_date={from_date}' if '?' in url else f'?from_date={from_date}'
        if to_date:
            url += f'&to_date={to_date}' if '?' in url else f'?to_date={to_date}'
        if 'ai' in args and args['ai']:
            url += f'&ai=true'
        if 'milestone' in args and args['milestone']:
            url += f'&milestone=true'
        if 'ppm' in args and args['ppm']:
            url += f'&ppm=true'
        response = requests.get(url,verify='./optum.pem')
        
        return f"{response_str}\nThere are {len(response.json())} total User Stories found {'for team ' + team} {('in release ' + release if release else '')}{('in iteration ' + iteration if iteration else '')}\nUser Stories found: {response.json()}"

    except Exception as exc:
        LOGGER.warning("Failed to fetch user stories: %s", exc)
        return "I am unable to provide information on the ask since I could not find the right information."

def feature_template(args: dict, endpoint: str) -> str:
    """Fetch features from the tickets service and format a summary string."""
    _debug(f"Function:feature_template, args: {args}, endpoint: {endpoint}")
    team = args['team'] if 'team' in args else None
    if not team:
        return NO_TEAM_MESSAGE
    
    _debug(f"Using team: {team}")

    release = args.get('release',None)
    from_date = args.get('from_date',None)
    to_date = args.get('to_date',None)
    url = f'{env.get_tickets_endpoint()}/uhccp/{team}/features{"/" if len(endpoint) > 0 else ""}{endpoint}'
    _debug(url)
    response_str = ''
    if not release:
        try:
            release_url = f'{env.get_tickets_endpoint()}/uhccp/{team}/releases/current'
            _debug(f"Calling current release endpoint for {team} with timeout={_HTTP_TIMEOUT_SECONDS}s")
            response = requests.get(release_url, verify='./optum.pem', timeout=_HTTP_TIMEOUT_SECONDS)
            release = response.json()[0]['Name']
            response_str += f"Since none specified, using Current release: {release}\n"
            _debug(f"Resolved release for {team}: {release}")
        except requests.exceptions.Timeout:
            return (
                f"Timed out while fetching current release for team {team}. "
                f"Please try again."
            )
        except Exception as e:
            LOGGER.warning("Error: %s", e)
            return f"This team, {team}, is unavailable for metrics."
    try:
        if release:
            url += f'?release={release}'
        if from_date:
            url += f'&from_date={from_date}' if release else f'?from_date={from_date}'
        if to_date:
            url += f'&to_date={to_date}' if release or from_date else f'?to_date={to_date}'
        if 'ai' in args and args['ai']:
            url += f'&ai=true'
        if 'milestone' in args and args['milestone']:
            url += f'&milestone=true'
        if 'ppm' in args and args['ppm']:
            url += f'&ppm=true'
        _debug(f"Calling features endpoint with timeout={_HTTP_TIMEOUT_SECONDS}s: {url}")
        response = requests.get(url, verify='./optum.pem', timeout=_HTTP_TIMEOUT_SECONDS)
        _debug(f"Features endpoint returned status: {response.status_code}")
        
        return f"{response_str}\nThere are {len(response.json())} total features found for team {team} {('in release ' + release if release else '')}\nFeatures found: {response.json()}"

    except requests.exceptions.Timeout:
        return (
            f"Timed out while fetching features for team {team}. "
            f"Please try again."
        )

    except Exception as exc:
        LOGGER.warning("Failed to fetch features: %s", exc)
        return "I am unable to provide information on the ask since I could not find the right information."

def capability_template(args: dict, endpoint: str) -> str:
    """Fetch capabilities from the tickets service and format a summary string."""
    _debug(f"Function:capability_template, args: {args}, endpoint: {endpoint}")

    team = args['team'] if 'team' in args else None
    if team not in rally_teams:
        team = 'UHCCP'
    if not team:
        return NO_TEAM_MESSAGE
    
    _debug(f"Using team: {team}")

    release = args.get('release',None)
    from_date = args.get('from_date',None)
    to_date = args.get('to_date',None)
    url = f'{env.get_tickets_endpoint()}/uhccp/{team}/capabilities{"/" if len(endpoint) > 0 else ""}{endpoint}'

    response_str = ''
    if not release:
        try:
            release_url = f'{env.get_tickets_endpoint()}/uhccp/{team}/releases/current'
            response = requests.get(release_url,verify='./optum.pem')
            release = response.json()[0]['Name']
            response_str += f"Since none specified, using Current release: {release}\n"
        except Exception as exc:
            LOGGER.warning("Failed to resolve current release for capabilities team %s: %s", team, exc)
            return f"This team, {team}, is unavailable for metrics."
    try:
        if release:
            url += f'?release={release}'
        if from_date:
            url += f'&from_date={from_date}' if release else f'?from_date={from_date}'
        if to_date:
            url += f'&to_date={to_date}' if release or from_date else f'?to_date={to_date}'
        response = requests.get(url,verify='./optum.pem')

        return f"{response_str}\nThere are {len(response.json())} total capabilities found for team {team} {('in release ' + release if release else '')}\nCapabilities found: {response.json()}"
    except Exception as exc:
        LOGGER.warning("Failed to fetch capabilities: %s", exc)
        return "I am unable to provide information on the ask since I could not find the right information."

def defect_template(args: dict, endpoint: str) -> str:
    """Fetch defects from the tickets service and format a summary string."""
    _debug(f"Function:defect_template, args: {args}, endpoint: {endpoint}")

    team = args['team'] if 'team' in args else None
    if team not in rally_teams:
        team = 'UHCCP'
    if not team:
        return NO_TEAM_MESSAGE

    _debug(f"Using team: {team}")

    iteration = args.get('iteration',None)
    release = args.get('release',None)
    from_date = args.get('from_date',None)
    to_date = args.get('to_date',None)
    response_str = ''
    if not iteration and not release:
        try:
            iteration_url = f'{env.get_tickets_endpoint()}/uhccp/{team}/iterations/current'
            response = requests.get(iteration_url,verify='./optum.pem')
            iteration = response.json()[0]['Name']
            response_str += f"Since none specified, using Current Iteration: {iteration}\n"
        except Exception as exc:
            LOGGER.warning("Failed to resolve current iteration for defects team %s: %s", team, exc)
            return f"This team, {team}, is unavailable for metrics."
    try:
        url = f'{env.get_tickets_endpoint()}/uhccp/{team}/defects{"/" if len(endpoint) > 0 else ""}{endpoint}'
        if iteration:
            url += f'?iteration={iteration}'
        elif release:
            url += f'?release={release}'
        if from_date:
            url += f'&from_date={from_date}' if '?' in url else f'?from_date={from_date}'
        if to_date:
            url += f'&to_date={to_date}' if '?' in url else f'?to_date={to_date}'
        response = requests.get(url,verify='./optum.pem')
        
        return f"{response_str}\nThere are {len(response.json())} total defects found {'for team '+ team} {('in release ' + release if release else '')}{('in iteration ' + iteration if iteration else '')}\nDefects found: {response.json()}"
    except Exception as exc:
        LOGGER.warning("Failed to fetch defects: %s", exc)
        return "I am unable to provide information on the ask since I could not find the right information."

def iteration_template(args: dict, endpoint: str) -> str:
    """Fetch iterations from the tickets service and format a summary string."""
    _debug(f"Function:iteration_template, args: {args}, endpoint: {endpoint}")

    team = args['team'] if 'team' in args else None
    if team not in rally_teams:
        team = 'UHCCP'
    if not team:
        return NO_TEAM_MESSAGE
    try:
        url = f'{env.get_tickets_endpoint()}/uhccp/{team}/iterations/{endpoint}'
        response = requests.get(url,verify='./optum.pem')

        return f"Iterations found: {response.json()}"
    except Exception as exc:
        LOGGER.warning("Failed to fetch iterations: %s", exc)
        return "I am unable to provide information on the ask since I could not find the right information."

def release_template(args: dict, endpoint: str) -> str:
    """Fetch releases from the tickets service and format a summary string."""
    team = args['team'] if 'team' in args else None
    if team not in rally_teams:
        team = 'UHCCP'
    _debug(f"Function:release_template, Using team: {team}")

    try:
        url = f'{env.get_tickets_endpoint()}/uhccp/{team}/releases/{endpoint}'
        response = requests.get(url,verify='./optum.pem')

        return f"Releases found: {response.json()}"
    except Exception as exc:
        LOGGER.warning("Failed to fetch releases: %s", exc)
        return "I am unable to provide information on the ask since I could not find the right information."


# ---------------------------------------------------------------------------
# Public tool functions (invoked via registry → dispatcher)
# ---------------------------------------------------------------------------

def get_user_stories(args: dict) -> str:
    """Fetch user stories for the specified team and filters."""
    return user_story_template(args, "")


def get_features(args: dict) -> str:
    """Fetch features for the specified team and filters."""
    return feature_template(args, "")


def get_current_iterations(args: dict) -> str:
    """Fetch the current iteration for a team."""
    return iteration_template(args, "current")


def get_current_releases(args: dict) -> str:
    """Fetch the current release for a team."""
    return release_template(args, "current")


def get_features_plan_estimates(args: dict) -> str:
    """Fetch plan estimates for features."""
    return feature_template(args, "plan_estimates")


def get_accepted_features_plan_estimates(args: dict) -> str:
    """Fetch accepted plan estimates for features."""
    return feature_template(args, "accepted_estimates")


def get_rally_obj_info(args: dict) -> str:
    """Fetch information for a specific Rally object by FormattedID."""
    formatted_id = args["FormattedID"].upper()
    # Sanitize to alphanumeric only to prevent injection.
    clean_id = "".join(ch for ch in formatted_id if ch.isalnum())
    if formatted_id != clean_id:
        return (
            f"Error: FormattedID {formatted_id} is not in the correct format. "
            "Please provide a FormattedID that is alphanumeric."
        )
    try:
        url = f"{env.get_tickets_endpoint()}/uhccp/from_id/{clean_id}"
        response = requests.get(url, verify="./optum.pem")
        return f"Features found: {response.json()}"
    except Exception as exc:
        LOGGER.warning("Failed to fetch Rally object %s: %s", clean_id, exc)
        return "I am unable to provide information on the ask since I could not find the right information."


def get_rally_obj(search: str, logger=None) -> str:
    """Search for Rally objects by embedding similarity."""
    try:
        url = f"{env.get_tickets_endpoint()}/tickets/rally/obj"
        req_body = {"desc": get_embeddings(search)}
        _debug(url)
        response = requests.post(url, json=req_body, verify="./optum.pem")
        if response.status_code == 200:
            data = response.json()
            if data:
                return f"This feature and user story data was found: {data}"
            return "No feature or user story data was found."
    except Exception as exc:
        LOGGER.warning("Failed to get similar Rally data: %s", exc)
    return ""


def get_rally_obj_info_no_id(args: dict, search: str) -> str:
    """Fetch Rally object info by description similarity (no FormattedID)."""
    return get_rally_obj(search)


def get_defects(args: dict) -> str:
    """Fetch defects for the specified team and filters."""
    return defect_template(args, "")


def get_release_defects(args: dict) -> str:
    """Fetch all defects in the next upcoming release."""
    url = f"{env.get_tickets_endpoint()}/uhccp/open_defects_next_release"
    res = requests.get(url, verify="./optum.pem")
    return f"Defects found: {res.json()}"


def get_release_features(args: dict) -> str:
    """Fetch all features in the next upcoming release."""
    url = f"{env.get_tickets_endpoint()}/uhccp/features_next_release"
    res = requests.get(url, verify="./optum.pem")
    return f"Features found: {res.json()}"


def get_capabilites(args: dict) -> str:
    """Fetch capabilities for the specified team and filters."""
    return capability_template(args, "")


def get_user_story_states(args: dict) -> str:
    """Fetch work-progress states for user stories."""
    return user_story_template(args, "states")


def get_features_states(args: dict) -> str:
    """Fetch work-progress states for features."""
    return feature_template(args, "states")

def get_user_story_acceptance_criteria(args):
    return user_story_template(args, 'acceptance_criteria')

def get_user_stories_no_acceptance_criteria(args):
    return user_story_template(args, 'no_acceptance_criteria')

def get_completed_user_story_estimates(args):
    return user_story_template(args, 'accepted_estimates')

def get_accepted_user_story_estimates(args):
    return user_story_template(args, 'accepted_estimates')
    
def get_user_story_descriptions(args):
    return user_story_template(args, 'descriptions')

def get_user_story_estimates(args):
    return user_story_template(args, 'estimates')
