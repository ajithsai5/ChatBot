"""Scheduling helpers for validator background execution."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from .config import SCHEDULE_CRON
from .models import RunMode
from .runner import is_running, run_link_check

LOGGER = logging.getLogger(__name__)


def _parse_simple_cron(cron_expr: str) -> dict:
    """Parse a 5-field cron expression into a dict with minute, hour, dom, month, dow.

    Supports: numbers, '*', and '*/N' step syntax.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (need 5 fields): {cron_expr}")

    fields = {}
    field_names = ["minute", "hour", "dom", "month", "dow"]
    field_ranges = {
        "minute": (0, 59),
        "hour": (0, 23),
        "dom": (1, 31),
        "month": (1, 12),
        "dow": (0, 6),
    }
    for name, part in zip(field_names, parts):
        lo, hi = field_ranges[name]
        if part == "*":
            fields[name] = None  # any
        elif part.startswith("*/"):
            raw = part[2:]
            try:
                step = int(raw)
            except ValueError:
                raise ValueError(f"Invalid step value in '{part}' for {name}: must be a positive integer")
            if step < 1 or step > hi:
                raise ValueError(f"Invalid step value in '{part}' for {name}: must be between 1 and {hi}")
            fields[name] = ("step", step)
        else:
            try:
                val = int(part)
            except ValueError:
                raise ValueError(f"Invalid value '{part}' for {name}: must be an integer")
            if val < lo or val > hi:
                raise ValueError(f"Value {val} out of range for {name}: must be between {lo} and {hi}")
            fields[name] = ("exact", val)
    return fields


def _cron_matches(fields: dict, dt: datetime) -> bool:
    """Check if a datetime matches parsed cron fields."""
    checks = [
        ("minute", dt.minute),
        ("hour", dt.hour),
        ("dom", dt.day),
        ("month", dt.month),
        ("dow", dt.weekday()),  # 0 = Monday in Python; cron uses 0 = Sunday
    ]
    for name, value in checks:
        spec = fields.get(name)
        if spec is None:
            continue
        kind, num = spec
        if kind == "exact":
            # For dow, cron 0=Sunday..6=Saturday. Python weekday() 0=Monday..6=Sunday.
            if name == "dow":
                cron_dow = (value + 1) % 7  # Python Sun=6 -> cron 0, Mon=0 -> cron 1
                if cron_dow != num:
                    return False
            elif value != num:
                return False
        elif kind == "step":
            if value % num != 0:
                return False
    return True


def next_scheduled_time(cron_expr: str | None = None) -> datetime | None:
    """Compute the next datetime matching the cron expression, up to 7 days out."""
    cron_expr = cron_expr or SCHEDULE_CRON
    try:
        fields = _parse_simple_cron(cron_expr)
    except ValueError:
        return None

    now = datetime.now()
    # Check each minute for the next 7 days
    candidate = now.replace(second=0, microsecond=0)
    from datetime import timedelta
    for _ in range(7 * 24 * 60):
        candidate += timedelta(minutes=1)
        if _cron_matches(fields, candidate):
            return candidate
    return None


class WebLinkValidatorScheduler:
    """Simple in-process scheduler that checks cron every 60 seconds."""

    def __init__(self, cron_expr: str | None = None) -> None:
        self._cron_expr = cron_expr or SCHEDULE_CRON
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="web-link-validator-scheduler")
        self._thread.start()
        LOGGER.info("Scheduler started with cron: %s", self._cron_expr)

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        LOGGER.info("Scheduler stopped.")

    @property
    def is_active(self) -> bool:
        return self._running

    def _loop(self) -> None:
        try:
            fields = _parse_simple_cron(self._cron_expr)
        except ValueError as exc:
            LOGGER.error("Invalid cron expression, scheduler exiting: %s", exc)
            self._running = False
            return

        last_trigger_minute: str = ""

        while not self._stop_event.is_set():
            now = datetime.now()
            minute_key = now.strftime("%Y-%m-%d %H:%M")

            if minute_key != last_trigger_minute and _cron_matches(fields, now):
                last_trigger_minute = minute_key
                if not is_running():
                    LOGGER.info("Scheduled run triggered at %s", now.isoformat())
                    try:
                        meta = run_link_check(mode=RunMode.SCHEDULED)
                        # Email is intentionally disabled — no send_report_async() call
                    except Exception as exc:
                        LOGGER.warning("Scheduled run failed: %s", exc)
                else:
                    LOGGER.info("Scheduled run skipped: another run is in progress.")

            # Sleep 30 seconds between checks
            self._stop_event.wait(timeout=30)

        self._running = False


# Module-level singleton
_scheduler: WebLinkValidatorScheduler | None = None


def get_scheduler() -> WebLinkValidatorScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = WebLinkValidatorScheduler()
    return _scheduler

