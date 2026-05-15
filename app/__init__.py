"""UHCCP Internal Chatbot — Flask application factory.

Main responsibility:
- Create and configure the Flask application instance.
- Register route handlers and CORS middleware.

Not handled here:
- Business logic, data access, or external service integration.
"""

from flask import Flask
from flask_cors import CORS


MAX_CONTENT_BYTES = 16 * 1024 * 1024


def create_app() -> Flask:
    """Build and return a fully configured Flask application.

    The factory pattern keeps application creation testable and avoids
    circular-import issues between route modules and the app instance.
    """
    application = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    application.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_BYTES
    CORS(application)

    from app.routes import register_routes

    register_routes(application)

    return application
