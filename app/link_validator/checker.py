"""HTTP link checking core logic for validator runs."""

from __future__ import annotations

import time
import threading
from typing import Optional

import requests

from .config import (
    CONNECT_TIMEOUT_S,
    READ_TIMEOUT_S,
    RETRIES,
    RATE_LIMIT_RPS,
)

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class RateLimiter:
    """Token-bucket rate limiter, thread-safe."""

    def __init__(self, rps: float = RATE_LIMIT_RPS) -> None:
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()


class LinkCheckResult:
    __slots__ = ("url", "status_code", "redirected_to", "error_type", "response_time_ms")

    def __init__(
        self,
        url: str,
        status_code: int = 0,
        redirected_to: str = "",
        error_type: str = "",
        response_time_ms: int = 0,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.redirected_to = redirected_to
        self.error_type = error_type
        self.response_time_ms = response_time_ms


def _classify_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return "timeout"
    if "connectionerror" in name or "dns" in msg or "name or service" in msg:
        return "dns"
    if "ssl" in name or "tls" in msg or "certificate" in msg:
        return "tls"
    return "other"


def _status_error_type(code: int) -> str:
    if 400 <= code < 500:
        return "4xx"
    if 500 <= code < 600:
        return "5xx"
    return ""


def check_url(
    url: str,
    rate_limiter: Optional[RateLimiter] = None,
    retries: int = RETRIES,
    timeout: tuple[float, float] = (CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
    get_body: bool = False,
) -> tuple[LinkCheckResult, Optional[str]]:
    """Check a single URL. Returns (result, body_text_or_none).

    Uses HEAD first, falls back to GET if HEAD returns 405/501.
    If get_body is True, always uses GET to retrieve HTML body.
    """
    if rate_limiter:
        rate_limiter.wait()

    method = "GET" if get_body else "HEAD"
    body_text: Optional[str] = None
    last_exc: Optional[Exception] = None
    headers = {"User-Agent": "UHCCP-WebLinkValidator/1.0"}

    for attempt in range(retries + 1):
        try:
            start = time.monotonic()
            resp = requests.request(
                method,
                url,
                timeout=timeout,
                headers=headers,
                allow_redirects=True,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # If HEAD returned 405 or 501, retry with GET
            if method == "HEAD" and resp.status_code in (405, 501):
                method = "GET"
                continue

            redirected_to = ""
            if resp.history:
                redirected_to = resp.url if resp.url != url else ""

            result = LinkCheckResult(
                url=url,
                status_code=resp.status_code,
                redirected_to=redirected_to,
                error_type=_status_error_type(resp.status_code),
                response_time_ms=elapsed_ms,
            )

            if get_body and resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type.lower():
                    body_text = resp.text

            # Retry on transient errors
            if resp.status_code in _TRANSIENT_STATUS_CODES and attempt < retries:
                backoff = min(2 ** attempt, 5)
                time.sleep(backoff)
                continue

            return result, body_text

        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                backoff = min(2 ** attempt, 5)
                time.sleep(backoff)
                continue

    # All retries exhausted
    error_type = _classify_error(last_exc) if last_exc else "other"
    return LinkCheckResult(url=url, error_type=error_type), None

