"""Environment and endpoint configuration for chatbot runtime.

Main responsibility:
- Expose Azure service API keys loaded from environment variables.
- Provide the ``Environment`` singleton that controls dev/prod endpoints.

Not handled here:
- Route definitions, business logic, or AI model orchestration.
"""

import os

AZURE_AI_SERVICE_KEY: str | None = os.getenv("AZURE_AI_Service_KEY")
AZURE_SEARCH_SERVICE_KEY: str | None = os.getenv("AZURE_Search_Service_KEY")

# ---------------------------------------------------------------------------
# Legacy aliases — existing imports reference the old names.
# Remove these once every consumer has been updated.
# ---------------------------------------------------------------------------
AZURE_AI_Service_KEY = AZURE_AI_SERVICE_KEY
AZURE_Search_Service_KEY = AZURE_SEARCH_SERVICE_KEY

# ---------------------------------------------------------------------------
# Default service endpoints (overridden when ``set_env(dev=True)`` is called)
# ---------------------------------------------------------------------------
_DEFAULT_CHATBOT_ENDPOINT = "https://hcccloud-uhgdlm-dtlapi-dev.uhc.com/uhccp-internal-chatbot"
_DEFAULT_TICKETS_ENDPOINT = "https://hcccloud-uhgdlm-dtlapi-dev.uhc.com/lpm-gpd-tickets"


class Environment:
    """Holds mutable runtime environment flags and service endpoints."""

    def __init__(self) -> None:
        self.DEVELOPMENT: bool = False
        self.SCRUM: bool = False
        self.RALLY: bool = False
        self.CHATBOT_ENDPOINT: str = _DEFAULT_CHATBOT_ENDPOINT
        self.TICKETS_ENDPOINT: str = _DEFAULT_TICKETS_ENDPOINT

    def set_env(self, dev: bool = False, scrum: bool = False, rally: bool = False) -> None:
        """Set runtime mode flags and recalculate endpoint targets.

        Args:
            dev: Enable local-development endpoints when True.
            scrum: Enable scrum-specific state when True.
            rally: Enable Rally-specific state when True.
        """
        self.DEVELOPMENT = dev
        self.SCRUM = scrum
        self.RALLY = rally
        self.TICKETS_ENDPOINT = "http://127.0.0.1:8082" if dev else _DEFAULT_TICKETS_ENDPOINT
        self.CHATBOT_ENDPOINT = "http://127.0.0.1:7669" if dev else _DEFAULT_CHATBOT_ENDPOINT
        if self.SCRUM:
            self.TEAM: str | None = None
            self.CALL_SIGN: str | None = None
            self.TICKETS_DATA: list = []

    def get_tickets_endpoint(self) -> str:
        """Return active tickets service endpoint."""
        return self.TICKETS_ENDPOINT

    def get_chatbot_endpoint(self) -> str:
        """Return active chatbot endpoint."""
        return self.CHATBOT_ENDPOINT


env = Environment()