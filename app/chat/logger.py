"""Structured logging helper for chatbot usage and telemetry.

Main responsibility:
- Collect per-request metadata (question, answer, username, environment).
- Export structured log records to Logstash for analytics.

Not handled here:
- Application-level logging configuration or log rotation.
"""

import json
import logging
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


class ChatbotLogger:
    """Collects chatbot interaction fields and exports them to Logstash."""

    def __init__(self, log_file: str = "chatbot_log.json") -> None:
        self.log_file = log_file

        self.data: dict[str, Any] = {
            "_index_tag": "chatbot_usage",
            "_index_frequency": "YEARLY",
            "chatbot": "persona",
            "persona": "uhccp",
        }

    # ------------------------------------------------------------------
    # Field setters
    # ------------------------------------------------------------------

    def set_question(self, question: str) -> None:
        """Store the user question after collapsing newlines."""
        self.data["question"] = question.replace("\n", " ")

    def set_answer(self, answer: str) -> None:
        """Store the chatbot answer after collapsing newlines."""
        self.data["answer"] = answer.replace("\n", " ")

    def set_environment(self, environment: str) -> None:
        """Store the active runtime environment label."""
        self.data["environment"] = environment

    def set_username(self, username: str) -> None:
        """Store the requesting user's identity."""
        self.data["username"] = username

    def set_ask_type(self, ask_type: str) -> None:
        """Store the classification of the user's query."""
        self.data["ask_type"] = ask_type

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def send_to_logstash(self, endpoint: str = "http://rn000125170:8080/generic_export") -> None:
        """Post the collected log payload to the Logstash generic export endpoint.

        Failures are logged as warnings — they must never break the chat flow.
        """
        try:
            # Logstash expects newline-delimited JSON for batch ingestion.
            payload = json.dumps(self.data)
            headers = {"Content-type": "application/json"}
            response = requests.post(endpoint, data=payload, headers=headers)
            LOGGER.info("Logstash response status=%s", response.status_code)
        except Exception as exc:
            LOGGER.warning("Error occurred while sending data to Logstash: %s", exc)