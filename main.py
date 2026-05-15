"""Application entry point for the UHCCP Internal Chatbot.

Main responsibility:
- Create the Flask application via the factory in app/ and expose it
  as the ``app`` variable for gunicorn (``main:app``).

Not handled here:
- Route definitions (see app/routes.py).
- Business logic (see app/chat/, app/tools/, app/ppt/, app/link_validator/).
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7669)
