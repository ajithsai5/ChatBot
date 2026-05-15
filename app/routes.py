"""HTTP route handlers for the UHCCP Internal Chatbot.

Main responsibility:
- Define all Flask route endpoints: home, chat, stream, health,
  PPT download, and web-link-validator report serving.

Not handled here:
- Application factory or CORS setup (see app/__init__.py).
- Business logic or orchestration (see app/chat/orchestrator.py).
"""

from flask import Flask, jsonify, request, send_from_directory, render_template, Response, send_file, stream_with_context
from flask_cors import cross_origin
from config import env
from app.chat import orchestrator
import json
import os
import threading
from html import escape
from queue import Queue


# ---------------------------------------------------------------------------
# Home and static asset routes
# ---------------------------------------------------------------------------

def register_routes(application: Flask) -> None:
    """Attach all route handlers to the given Flask application."""

    @application.route("/")
    @application.route("/uhccp")
    def home():
        return render_template("index.html", title="AI Chatbot")

    @application.route("/uhccp-internal-chatbot/static/<path:filename>")
    @cross_origin()
    def static_files(filename):
        return send_from_directory(application.static_folder, filename)

    @application.route("/favicon.ico")
    @cross_origin()
    def favicon():
        """Serve favicon from static assets when present."""
        favicon_path = os.path.join(application.static_folder, "favicon.ico")
        if os.path.exists(favicon_path):
            return send_from_directory(application.static_folder, "favicon.ico")
        return "", 204

    # -------------------------------------------------------------------
    # Chat routes
    # -------------------------------------------------------------------

    @application.route("/chat", methods=["GET", "POST"])
    @application.route("/uhccp-internal-chatbot/chat", methods=["GET", "POST"])
    @cross_origin()
    def uhccp_internal_chatbot():
        env.set_env(dev=False)

        user_input = request.args.get("msg")
        username = "anonymous"
        if request.method == "POST":
            post_body = request.get_json(silent=True) or {}
            username = post_body["username"] if "username" in post_body else None

        follow_up_qs: dict = {}

        if not user_input:
            error_msg = "No message provided"
            return Response(
                _format_msg(error_msg, questions=[], links=[]),
                mimetype="application/json",
            )

        response_data = orchestrator.get_chatbot_response(
            user_input, prt=True, prt_data=follow_up_qs, username=username
        )

        if "error" in response_data:
            return Response(
                _format_msg(
                    response_data["error"],
                    questions=follow_up_qs.get("questions", []),
                    links=follow_up_qs.get("links", []),
                ),
                mimetype="application/json",
            )

        return Response(
            _format_msg(
                response_data["response"],
                questions=follow_up_qs.get("questions", []),
                links=follow_up_qs.get("links", []),
            ),
            mimetype="application/json",
        )

    @application.route("/chat/stream", methods=["POST"])
    @application.route("/uhccp-internal-chatbot/chat/stream", methods=["POST"])
    @cross_origin()
    def uhccp_internal_chatbot_stream():
        env.set_env(dev=False)
        post_body = request.get_json(silent=True) or {}
        user_input = post_body.get("message") or post_body.get("msg") or request.args.get("msg")
        username = post_body.get("username", "anonymous")
        history = post_body.get("history", [])

        if not user_input:
            return Response(
                _sse_event("error", "No message provided"),
                mimetype="text/event-stream",
            )

        def event_stream():
            queue: Queue = Queue()

            def progress_callback(progress_message: str):
                queue.put({"type": "progress", "message": progress_message})

            def worker():
                try:
                    if orchestrator.is_weekly_ppt_request(user_input):
                        queue.put({"type": "progress", "message": "Understood. Starting weekly PPT generation request."})
                        result = orchestrator.generate_weekly_ppt_with_progress(
                            user_input, progress_callback=progress_callback
                        )
                        if result:
                            queue.put({"type": "final", "message": result})
                        else:
                            queue.put({"type": "error", "message": "Could not generate the weekly PPT for this request."})
                    else:
                        response_data = orchestrator.get_chatbot_response(
                            user_input, history=history, username=username
                        )
                        if "error" in response_data:
                            queue.put({"type": "error", "message": response_data["error"]})
                        else:
                            queue.put({"type": "final", "message": response_data["response"]})
                except Exception as exc:
                    queue.put({"type": "error", "message": f"Request failed: {exc}"})
                finally:
                    queue.put({"type": "done", "message": "done"})

            threading.Thread(target=worker, daemon=True).start()

            while True:
                item = queue.get()
                yield _sse_event(item["type"], item["message"])
                if item["type"] == "done":
                    break

        headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers=headers,
        )

    @application.route("/chatbot", methods=["POST"])
    @application.route("/uhccp-internal-chatbot/chatbot", methods=["POST"])
    @cross_origin()
    def chat():
        payload = request.get_json(silent=True) or {}
        user_input = payload.get("message")
        context = payload.get("context", "")
        if not user_input:
            return jsonify({"error": "No message provided"}), 400
        response_data = orchestrator.chat_bot_response(user_input)
        if "error" in response_data["response"]:
            return jsonify({"error": response_data["response"]}), 500
        return jsonify({"response": response_data["response"], "context": context})

    # -------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------

    @application.route("/health", methods=["GET"])
    @application.route("/uhccp-internal-chatbot/health", methods=["GET"])
    @cross_origin()
    def health_check():
        return "OK", 200

    # -------------------------------------------------------------------
    # PPT download route
    # -------------------------------------------------------------------

    @application.route("/<path:filename>.pptx", methods=["GET"])
    @application.route("/uhccp-internal-chatbot/<path:filename>.pptx", methods=["GET"])
    @cross_origin()
    def serve_pptx(filename):
        # Reject path separators to prevent directory traversal.
        if not filename or "/" in filename or os.sep in filename:
            return "Invalid file name", 400

        base_dir = os.path.realpath(os.path.join(os.getcwd(), "generated_ppts"))
        file_path = os.path.realpath(os.path.join(base_dir, f"{filename}.pptx"))

        if not file_path.startswith(base_dir + os.sep):
            return "Invalid file path", 400

        if os.path.exists(file_path):
            return send_file(
                file_path,
                mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                as_attachment=True,
                download_name=f"{filename}.pptx",
            )
        return "File not found", 404

    # -------------------------------------------------------------------
    # Web link validator report routes
    # -------------------------------------------------------------------

    @application.route("/web-link-validator/report/<run_id>", methods=["GET"])
    @application.route("/uhccp-internal-chatbot/web-link-validator/report/<run_id>", methods=["GET"])
    @cross_origin()
    def serve_web_link_validator_report(run_id):
        from app.link_validator.config import REPORTS_DIR

        if not run_id or "/" in run_id or os.sep in run_id or ".." in run_id:
            return "Invalid run ID", 400

        base_dir = os.path.realpath(REPORTS_DIR)
        csv_path = os.path.realpath(os.path.join(base_dir, run_id, "results.csv"))

        if not csv_path.startswith(base_dir + os.sep):
            return "Invalid path", 400

        if os.path.exists(csv_path):
            return send_file(
                csv_path,
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"web-link-validator-{run_id}.csv",
            )
        return "Report not found", 404

    @application.route("/web-link-validator/summary/<run_id>", methods=["GET"])
    @application.route("/uhccp-internal-chatbot/web-link-validator/summary/<run_id>", methods=["GET"])
    @cross_origin()
    def serve_web_link_validator_summary(run_id):
        from app.link_validator.config import REPORTS_DIR

        if not run_id or "/" in run_id or os.sep in run_id or ".." in run_id:
            return "Invalid run ID", 400

        base_dir = os.path.realpath(REPORTS_DIR)
        summary_path = os.path.realpath(os.path.join(base_dir, run_id, "summary.json"))

        if not summary_path.startswith(base_dir + os.sep):
            return "Invalid path", 400

        if os.path.exists(summary_path):
            with open(summary_path) as f:
                return jsonify(json.load(f))
        return "Summary not found", 404

    @application.route("/web-link-validator/verified/<run_id>", methods=["GET"])
    @application.route("/uhccp-internal-chatbot/web-link-validator/verified/<run_id>", methods=["GET"])
    @cross_origin()
    def serve_web_link_validator_verified(run_id):
        from app.link_validator.config import REPORTS_DIR

        if not run_id or "/" in run_id or os.sep in run_id or ".." in run_id:
            return "Invalid run ID", 400

        base_dir = os.path.realpath(REPORTS_DIR)
        verified_path = os.path.realpath(os.path.join(base_dir, run_id, "verified_failures.csv"))

        if not verified_path.startswith(base_dir + os.sep):
            return "Invalid path", 400

        if os.path.exists(verified_path):
            return send_file(
                verified_path,
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"verified-failures-{run_id}.csv",
            )
        return "Verified report not found", 404


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _sse_event(event_type: str, message: str) -> str:
    """Build a Server-Sent Events data line from type and message."""
    payload = {"type": event_type, "message": message}
    return f"data: {json.dumps(payload)}\n\n"


def _escape_html_content(value):
    """Recursively HTML-escape strings within nested structures."""
    if isinstance(value, str):
        return escape(value, quote=True)
    if isinstance(value, list):
        return [_escape_html_content(item) for item in value]
    if isinstance(value, dict):
        return {key: _escape_html_content(item) for key, item in value.items()}
    return value


def _format_msg(response: str, questions=None, links=None, context: str = "") -> str:
    """Serialize a chatbot response payload to JSON."""
    questions = questions if questions is not None else []
    links = links if links is not None else []
    obj = {
        "response": _escape_html_content(response),
        "questions": _escape_html_content(questions),
        "persona": "uhccp",
        "urlInfo": _escape_html_content(links),
    }
    return json.dumps(obj).replace("\n", "\n<br>")
