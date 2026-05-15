"""Chatbot-facing handlers for web-link-validator commands."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .models import RunMeta, RunMode, RunStatus
from .runner import (
    cancel_current_run,
    get_current_run,
    is_running,
    start_run_async,
)

LOGGER = logging.getLogger(__name__)


def get_web_link_validator_status(**kwargs) -> str:
    """Return a summary of the last web link validation run and next scheduled time."""
    # Check in-process run first (same worker/thread)
    current = get_current_run()
    LOGGER.debug("[web-link-validator-status] current_run=%s, is_running=%s", current, is_running())
    if current and current.status == RunStatus.RUNNING:
        progress = 0
        if current.total_pages > 0:
            progress = round(current.pages_checked / current.total_pages * 100, 1)
        lines = [
            f"Web Link Validator is currently **running** (run ID: `{current.run_id}`)",
            f"Progress: {current.pages_checked}/{current.total_pages} pages ({progress}%)",
            f"Links checked so far: {current.links_checked}",
            f"Errors so far: {current.errors}",
        ]
        return "\n".join(lines)

    # Check disk: file lock or any run with status "running"
    running_on_disk = is_running()
    latest = RunMeta.latest()

    if running_on_disk or (latest and latest.status == RunStatus.RUNNING):
        if latest and latest.status == RunStatus.RUNNING:
            progress = 0
            if latest.total_pages > 0:
                progress = round(latest.pages_checked / latest.total_pages * 100, 1)
            lines = [
                f"Web Link Validator is currently **running** (run ID: `{latest.run_id}`)",
                f"Progress: {latest.pages_checked}/{latest.total_pages} pages ({progress}%)",
                f"Links checked so far: {latest.links_checked}",
                f"Errors so far: {latest.errors}",
            ]
            return "\n".join(lines)
        return "A web link validation run is in progress. Status details will be available shortly."

    if not latest:
        return "No web link validation runs found yet. Use 'run web link validator' to start a manual run."

    start_str = datetime.fromtimestamp(latest.start_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    csv_url = f"/uhccp-internal-chatbot/web-link-validator/report/{latest.run_id}"
    lines = [
        f"**Last run** (`{latest.run_id}`): {latest.status.value}",
        f"Started: {start_str} | Duration: {latest.duration_s}s",
        f"Pages checked: {latest.pages_checked}/{latest.total_pages}",
        f"Links checked: {latest.links_checked}/{latest.total_links}",
        f"Results: 2xx={latest.status_2xx}, 3xx={latest.status_3xx}, 4xx={latest.status_4xx}, 5xx={latest.status_5xx}, errors={latest.errors}",
    ]
    if latest.top_failing_domains:
        top = ", ".join(f"{d} ({c})" for d, c in list(latest.top_failing_domains.items())[:5])
        lines.append(f"Top failing domains: {top}")

    lines.append(f"[Download CSV Report]({csv_url})")

    # Scheduler is disabled — runs are on-demand only
    lines.append("Scheduler: disabled (on-demand only)")

    return "\n".join(lines)


def run_web_link_validator_now(**kwargs) -> str:
    """Start a new web link validation run on demand."""
    if is_running():
        current = get_current_run()
        if current:
            return f"A web link validation run is already in progress (run ID: `{current.run_id}`). Please wait for it to finish or cancel it first."
        # Run is active in another process (detected via file lock)
        latest = RunMeta.latest()
        if latest and latest.status == RunStatus.RUNNING:
            return f"A web link validation run is already in progress (run ID: `{latest.run_id}`, pages: {latest.pages_checked}/{latest.total_pages}). Please wait for it to finish."
        return "A web link validation run is already in progress on this server. Please wait for it to finish."

    try:
        run_id = start_run_async(mode=RunMode.MANUAL)
        return f"Web link validation run started (run ID: `{run_id}`). Use the status command to track progress."
    except RuntimeError as exc:
        return f"Could not start run: {exc}"


def get_web_link_validator_report(**kwargs) -> str:
    """Return the file path of the latest (or specific) web link validation CSV report."""
    run_id = kwargs.get("run_id", "").strip() if kwargs.get("run_id") else ""

    if run_id:
        meta = RunMeta.load(run_id)
        if not meta:
            return f"Run `{run_id}` not found."
    else:
        meta = RunMeta.latest()
        if not meta:
            return "No web link validation runs found yet."

    import os
    csv_path = meta.csv_path
    if not os.path.exists(csv_path):
        return f"CSV report for run `{meta.run_id}` not found at expected path."

    csv_url = f"/uhccp-internal-chatbot/web-link-validator/report/{meta.run_id}"
    verified_url = f"/uhccp-internal-chatbot/web-link-validator/verified/{meta.run_id}"

    summary = ""
    if os.path.exists(meta.summary_path):
        with open(meta.summary_path) as f:
            summary_data = json.load(f)
        summary = (
            f"\n**Summary**: Pages={summary_data.get('pages_checked',0)}, "
            f"Links={summary_data.get('links_checked',0)}, "
            f"2xx={summary_data.get('status_buckets',{}).get('2xx',0)}, "
            f"4xx={summary_data.get('status_buckets',{}).get('4xx',0)}, "
            f"5xx={summary_data.get('status_buckets',{}).get('5xx',0)}, "
            f"errors={summary_data.get('status_buckets',{}).get('errors',0)}"
        )

    # Check for verified failures report
    verified = ""
    verified_path = os.path.join(os.path.dirname(csv_path), "verified_failures.csv")
    if os.path.exists(verified_path):
        import csv as csv_mod
        try:
            with open(verified_path, "r", encoding="utf-8") as vf:
                reader = csv_mod.DictReader(vf)
                rows = list(reader)
            confirmed = len([r for r in rows if r.get("stillBroken") == "YES"])
            restricted = len([r for r in rows if r.get("stillBroken") == "RESTRICTED"])
            false_pos = len([r for r in rows if r.get("stillBroken") == "NO"])
            verified = f"\n**Verification**: {confirmed} confirmed broken"
            if restricted:
                verified += f", {restricted} restricted (require login)"
            verified += f", {false_pos} false positives (were transient)"
            verified += f"\n[Download Verified Failures CSV]({verified_url})"
        except Exception:
            pass

    return f"Report for run `{meta.run_id}` ({meta.status.value}):\n[Download CSV Report]({csv_url}){summary}{verified}"


def cancel_web_link_validator_run(**kwargs) -> str:
    """Cancel the currently running web link validation."""
    if cancel_current_run():
        return "Web link validation run cancellation requested. The run will stop after the current batch completes."
    return "No web link validation run is currently in progress."


def email_web_link_validator_report(**kwargs) -> str:
    """Email functionality is intentionally disabled.

    The corporate SMTP relay requires an approved sender address.
    To re-enable, set EMAIL_ENABLED=True in config.py and configure an approved sender.
    """
    return "Email notifications are currently disabled."


def _dispatch_web_link_validator_query(question: str) -> str:
    """Fallback router when the LLM doesn't pick a web-link-validator tool.

    Matches the user's intent via keywords and calls the appropriate handler
    directly, so the request never falls through to vector search.
    """
    text = question.lower()

    if any(kw in text for kw in ("cancel", "stop")):
        return cancel_web_link_validator_run()

    if any(kw in text for kw in ("run", "start", "scan", "check links")):
        return run_web_link_validator_now()

    if any(kw in text for kw in ("report", "csv", "result", "download")):
        return get_web_link_validator_report()

    if any(kw in text for kw in ("email", "send", "mail")):
        return email_web_link_validator_report()

    # Default: show status
    return get_web_link_validator_status()

