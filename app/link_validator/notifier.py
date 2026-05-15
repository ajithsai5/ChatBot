"""Email notification for web link validator reports.

Sends an HTML email with summary tables and CSV attachments
after each web link validation run completes.

Uses Outlook desktop app (win32com) by default — no SMTP config needed.
Falls back to SMTP if Outlook is unavailable.
"""
from __future__ import annotations

import csv as csv_module
import logging
import os
import smtplib
import threading
from datetime import datetime, timezone, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import (
    EMAIL_ENABLED,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_USE_TLS,
    EMAIL_SMTP_USER,
    EMAIL_SMTP_PASSWORD,
    EMAIL_SENDER,
    EMAIL_RECIPIENTS,
    EMAIL_SUBJECT_PREFIX,
    REPORTS_DIR,
)
from .models import RunMeta

LOGGER = logging.getLogger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

try:
    import win32com.client
    win32com_available = True
except ImportError:
    win32com_available = False


def _format_timestamp(epoch: float | None) -> str:
    if epoch is None:
        return "N/A"
    return datetime.fromtimestamp(epoch, tz=_IST).strftime("%Y-%m-%d %I:%M:%S %p IST")


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _load_verified_rows(meta: RunMeta) -> list[dict]:
    path = os.path.join(REPORTS_DIR, meta.run_id, "verified_failures.csv")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return list(csv_module.DictReader(f))
    except Exception:
        return []


def _status_color(count: int) -> str:
    return "#f8d7da" if count > 0 else "#d4edda"


def _build_html_body(meta: RunMeta, verified_rows: list[dict]) -> str:
    broken = [r for r in verified_rows if r.get("stillBroken") == "YES"]
    restricted = [r for r in verified_rows if r.get("stillBroken") == "RESTRICTED"]
    false_pos = [r for r in verified_rows if r.get("stillBroken") == "NO"]

    status_colors = {
        "succeeded": "#28a745", "failed": "#dc3545",
        "cancelled": "#ffc107", "running": "#17a2b8",
    }
    sc = status_colors.get(meta.status.value, "#6c757d")

    parts = []

    # HTML wrapper
    parts.append("""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Segoe UI,Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:900px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">""")

    # Header
    parts.append(f"""
<div style="background:#002677;color:#fff;padding:20px 30px;">
  <h1 style="margin:0;font-size:24px;">UHCCP Web Link Validator Report</h1>
  <p style="margin:8px 0 0;font-size:14px;color:#ccc;">Run ID: <code>{meta.run_id}</code>
    <span style="background:{sc};color:#fff;padding:2px 10px;border-radius:3px;font-size:12px;margin-left:10px;">
      {meta.status.value.upper()}
    </span>
  </p>
</div>""")

    # Summary
    parts.append(f"""
<div style="padding:25px 30px;">
  <h2 style="color:#002677;border-bottom:3px solid #FF612B;padding-bottom:8px;font-size:20px;margin-top:0;">Run Summary</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:20px;">
    <tr><td style="padding:8px 14px;border:1px solid #dee2e6;font-weight:bold;width:35%;background:#f8f9fa;">Mode</td>
        <td style="padding:8px 14px;border:1px solid #dee2e6;">{meta.mode.value.title()}</td></tr>
    <tr><td style="padding:8px 14px;border:1px solid #dee2e6;font-weight:bold;background:#f8f9fa;">Started</td>
        <td style="padding:8px 14px;border:1px solid #dee2e6;">{_format_timestamp(meta.start_time)}</td></tr>
    <tr><td style="padding:8px 14px;border:1px solid #dee2e6;font-weight:bold;background:#f8f9fa;">Finished</td>
        <td style="padding:8px 14px;border:1px solid #dee2e6;">{_format_timestamp(meta.end_time)}</td></tr>
    <tr><td style="padding:8px 14px;border:1px solid #dee2e6;font-weight:bold;background:#f8f9fa;">Duration</td>
        <td style="padding:8px 14px;border:1px solid #dee2e6;">{_format_duration(meta.duration_s)}</td></tr>
    <tr><td style="padding:8px 14px;border:1px solid #dee2e6;font-weight:bold;background:#f8f9fa;">Pages Scanned</td>
        <td style="padding:8px 14px;border:1px solid #dee2e6;">{meta.pages_checked} / {meta.total_pages}</td></tr>
    <tr><td style="padding:8px 14px;border:1px solid #dee2e6;font-weight:bold;background:#f8f9fa;">Links Checked</td>
        <td style="padding:8px 14px;border:1px solid #dee2e6;">{meta.links_checked:,} / {meta.total_links:,}</td></tr>
  </table>""")

    # Status distribution
    parts.append(f"""
  <h2 style="color:#002677;border-bottom:3px solid #FF612B;padding-bottom:8px;font-size:20px;">Status Distribution</h2>
  <table style="width:100%;border-collapse:collapse;text-align:center;font-size:14px;margin-bottom:20px;">
    <tr style="background:#f8f9fa;">
      <th style="padding:10px;border:1px solid #dee2e6;">2xx (OK)</th>
      <th style="padding:10px;border:1px solid #dee2e6;">3xx (Redirect)</th>
      <th style="padding:10px;border:1px solid #dee2e6;">4xx (Client Error)</th>
      <th style="padding:10px;border:1px solid #dee2e6;">5xx (Server Error)</th>
      <th style="padding:10px;border:1px solid #dee2e6;">Network Errors</th>
    </tr>
    <tr>
      <td style="padding:10px;border:1px solid #dee2e6;background:#d4edda;font-weight:bold;font-size:18px;">{meta.status_2xx:,}</td>
      <td style="padding:10px;border:1px solid #dee2e6;background:#fff3cd;font-weight:bold;font-size:18px;">{meta.status_3xx:,}</td>
      <td style="padding:10px;border:1px solid #dee2e6;background:{_status_color(meta.status_4xx)};font-weight:bold;font-size:18px;">{meta.status_4xx:,}</td>
      <td style="padding:10px;border:1px solid #dee2e6;background:{_status_color(meta.status_5xx)};font-weight:bold;font-size:18px;">{meta.status_5xx:,}</td>
      <td style="padding:10px;border:1px solid #dee2e6;background:{_status_color(meta.errors)};font-weight:bold;font-size:18px;">{meta.errors:,}</td>
    </tr>
  </table>""")

    # Verification summary
    if verified_rows:
        parts.append(f"""
  <h2 style="color:#002677;border-bottom:3px solid #FF612B;padding-bottom:8px;font-size:20px;">Verification Summary</h2>
  <table style="width:100%;border-collapse:collapse;text-align:center;font-size:14px;margin-bottom:20px;">
    <tr style="background:#f8f9fa;">
      <th style="padding:10px;border:1px solid #dee2e6;">Confirmed Broken</th>
      <th style="padding:10px;border:1px solid #dee2e6;">Restricted (SSO)</th>
      <th style="padding:10px;border:1px solid #dee2e6;">False Positives</th>
      <th style="padding:10px;border:1px solid #dee2e6;">Total Verified</th>
    </tr>
    <tr>
      <td style="padding:10px;border:1px solid #dee2e6;background:{_status_color(len(broken))};font-weight:bold;font-size:18px;">{len(broken)}</td>
      <td style="padding:10px;border:1px solid #dee2e6;background:#fff3cd;font-weight:bold;font-size:18px;">{len(restricted)}</td>
      <td style="padding:10px;border:1px solid #dee2e6;background:#d4edda;font-weight:bold;font-size:18px;">{len(false_pos)}</td>
      <td style="padding:10px;border:1px solid #dee2e6;font-weight:bold;font-size:18px;">{len(verified_rows)}</td>
    </tr>
  </table>""")

    # Top failing domains
    if meta.top_failing_domains:
        parts.append("""
  <h2 style="color:#002677;border-bottom:3px solid #FF612B;padding-bottom:8px;font-size:20px;">Top Failing Domains</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:20px;">
    <tr style="background:#002677;color:#fff;">
      <th style="padding:8px 14px;border:1px solid #dee2e6;text-align:left;">Domain</th>
      <th style="padding:8px 14px;border:1px solid #dee2e6;text-align:right;">Failures</th>
    </tr>""")
        for i, (domain, count) in enumerate(meta.top_failing_domains.items()):
            bg = "#f8f9fa" if i % 2 == 0 else "#fff"
            parts.append(f"""
    <tr style="background:{bg};">
      <td style="padding:8px 14px;border:1px solid #dee2e6;">{domain}</td>
      <td style="padding:8px 14px;border:1px solid #dee2e6;text-align:right;color:#dc3545;font-weight:bold;">{count}</td>
    </tr>""")
        parts.append("  </table>")

    # Confirmed broken links table
    if broken:
        parts.append(f"""
  <h2 style="color:#dc3545;border-bottom:3px solid #dc3545;padding-bottom:8px;font-size:20px;">
    Confirmed Broken Links ({len(broken)})
  </h2>
  <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
    <tr style="background:#dc3545;color:#fff;">
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:left;">URL</th>
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:center;width:70px;">Status</th>
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:center;width:90px;">Error Type</th>
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:left;">Affected Pages</th>
    </tr>""")
        for i, row in enumerate(broken):
            url = row.get("linkUrl", "")
            bg = "#f8d7da" if i % 2 == 0 else "#fce4e4"
            pages = row.get("affectedPages", "")
            parts.append(f"""
    <tr style="background:{bg};">
      <td style="padding:6px 10px;border:1px solid #dee2e6;word-break:break-all;"><a href="{url}" style="color:#dc3545;">{url}</a></td>
      <td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;font-weight:bold;">{row.get("verifiedStatus", "")}</td>
      <td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;">{row.get("errorType", "")}</td>
      <td style="padding:6px 10px;border:1px solid #dee2e6;font-size:11px;">{pages}</td>
    </tr>""")
        parts.append("  </table>")
    else:
        parts.append("""
  <div style="background:#d4edda;padding:15px 20px;border-radius:5px;margin:20px 0;">
    <strong style="color:#155724;">No confirmed broken links found.</strong>
  </div>""")

    # Restricted links table
    if restricted:
        parts.append(f"""
  <h2 style="color:#FF612B;border-bottom:3px solid #FF612B;padding-bottom:8px;font-size:20px;">
    Restricted Links ({len(restricted)})
  </h2>
  <p style="font-size:13px;color:#666;margin-top:0;">These URLs return 403 because they require SSO/authentication login. They are not truly broken.</p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
    <tr style="background:#FF612B;color:#fff;">
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:left;">URL</th>
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:center;width:70px;">Status</th>
      <th style="padding:8px 10px;border:1px solid #dee2e6;text-align:left;">Affected Pages</th>
    </tr>""")
        for i, row in enumerate(restricted):
            url = row.get("linkUrl", "")
            bg = "#fff3cd" if i % 2 == 0 else "#fff8e1"
            parts.append(f"""
    <tr style="background:{bg};">
      <td style="padding:6px 10px;border:1px solid #dee2e6;word-break:break-all;">{url}</td>
      <td style="padding:6px 10px;border:1px solid #dee2e6;text-align:center;">403</td>
      <td style="padding:6px 10px;border:1px solid #dee2e6;font-size:11px;">{row.get("affectedPages", "")}</td>
    </tr>""")
        parts.append("  </table>")

    # False positives note
    if false_pos:
        parts.append(f"""
  <p style="font-size:13px;color:#666;margin-top:10px;">
    <strong>{len(false_pos)}</strong> link(s) were transient failures (false positives) and are now reachable.
  </p>""")

    # Footer
    now_str = datetime.now(tz=_IST).strftime("%Y-%m-%d %I:%M %p IST")
    parts.append(f"""
</div>
<div style="background:#f8f9fa;padding:15px 30px;text-align:center;font-size:12px;color:#999;border-top:1px solid #dee2e6;">
  Generated by UHCCP Internal Chatbot | {now_str}<br>
  <span style="color:#bbb;">Full CSV data attached for detailed analysis.</span>
</div>
</div></body></html>""")

    return "".join(parts)


def _get_attachment_paths(meta: RunMeta) -> list[str]:
    """Return list of existing CSV file paths to attach."""
    paths = [
        meta.csv_path,
        os.path.join(REPORTS_DIR, meta.run_id, "verified_failures.csv"),
    ]
    return [p for p in paths if os.path.exists(p)]


def _send_via_outlook(subject: str, html_body: str, recipients: list[str],
                       attachments: list[str]) -> tuple[bool, str]:
    """Send email using Outlook desktop app via win32com. No SMTP config needed."""
    if not win32com_available:
        return (False, "win32com not available")
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.To = ";".join(recipients)
        for path in attachments:
            mail.Attachments.Add(os.path.abspath(path))
        mail.Send()
        return (True, f"Report emailed via Outlook to {len(recipients)} recipient(s)")
    except Exception as exc:
        return (False, f"Outlook send error: {exc}")


def _send_via_smtp(subject: str, html_body: str, recipients: list[str],
                    attachments: list[str]) -> tuple[bool, str]:
    """Send email using SMTP. Requires SMTP host to be configured."""
    if not EMAIL_SMTP_HOST:
        return (False, "SMTP host not configured. Set WEB_LINK_VALIDATOR_EMAIL_SMTP_HOST.")
    if not EMAIL_SENDER:
        return (False, "Email sender not configured. Set WEB_LINK_VALIDATOR_EMAIL_SENDER.")

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = EMAIL_SENDER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        for file_path in attachments:
            try:
                part = MIMEBase("application", "octet-stream")
                with open(file_path, "rb") as f:
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                name = os.path.basename(file_path)
                part.add_header("Content-Disposition", f"attachment; filename={name}")
                msg.attach(part)
            except Exception as exc:
                LOGGER.warning("Could not attach %s: %s", file_path, exc)

        server = smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, timeout=30)
        try:
            server.ehlo()
            if EMAIL_USE_TLS:
                server.starttls()
                server.ehlo()
            if EMAIL_SMTP_USER and EMAIL_SMTP_PASSWORD:
                server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)
            server.sendmail(EMAIL_SENDER, recipients, msg.as_string())
        finally:
            server.quit()

        return (True, f"Report emailed via SMTP to {len(recipients)} recipient(s)")

    except Exception as exc:
        return (False, f"SMTP send error: {exc}")


def send_report(meta: RunMeta) -> tuple[bool, str]:
    """Build and send the email report. Returns (success, message).

    Tries Outlook first (no config needed), falls back to SMTP.
    """
    try:
        if not EMAIL_ENABLED:
            LOGGER.info("Email disabled (WEB_LINK_VALIDATOR_EMAIL_ENABLED != true).")
            return (False, "Email notifications are disabled. Set WEB_LINK_VALIDATOR_EMAIL_ENABLED=true to enable.")

        if not EMAIL_RECIPIENTS:
            LOGGER.warning("No email recipients configured.")
            return (False, "No email recipients configured. Set WEB_LINK_VALIDATOR_EMAIL_RECIPIENTS.")

        LOGGER.info("Preparing email report for run %s to %s", meta.run_id, EMAIL_RECIPIENTS)

        verified_rows = _load_verified_rows(meta)
        html_body = _build_html_body(meta, verified_rows)
        subject = f"{EMAIL_SUBJECT_PREFIX} Run {meta.run_id} - {meta.status.value.upper()}"
        attachments = _get_attachment_paths(meta)
        LOGGER.debug("Email attachments: %s", attachments)

        # Try Outlook first (works without any SMTP config)
        ok, msg = _send_via_outlook(subject, html_body, EMAIL_RECIPIENTS, attachments)
        if ok:
            LOGGER.info("Email sent via Outlook: %s", msg)
            return (ok, msg)

        # Fall back to SMTP if Outlook is not available
        LOGGER.info("Outlook unavailable (%s), trying SMTP to %s:%s...", msg, EMAIL_SMTP_HOST, EMAIL_SMTP_PORT)
        ok, msg = _send_via_smtp(subject, html_body, EMAIL_RECIPIENTS, attachments)
        if ok:
            LOGGER.info("Email sent via SMTP: %s", msg)
        else:
            LOGGER.warning("SMTP failed: %s", msg)
        return (ok, msg)

    except Exception as exc:
        LOGGER.warning("Email send error: %s", exc)
        return (False, f"Email send error: {exc}")


def send_report_async(meta: RunMeta) -> None:
    """Fire-and-forget email sending in a background thread."""
    def _worker():
        ok, msg = send_report(meta)
        if ok:
            LOGGER.info("%s", msg)
        else:
            LOGGER.warning("Email notification skipped/failed: %s", msg)

    t = threading.Thread(target=_worker, daemon=True, name="web-link-validator-email")
    t.start()
