"""Lightweight inline URL checker for chatbot responses.

Extracts URLs from LLM markdown output, quick-checks each with a HEAD
request, and returns a formatted footer summarising link health.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from .checker import check_url, LinkCheckResult
from .config import (
    INLINE_CHECK_ENABLED,
    INLINE_CHECK_MAX_URLS,
    INLINE_CHECK_TIMEOUT_S,
    RESTRICTED_DOMAINS,
)

# Regex: markdown links [text](url) — the URL character class excludes '[' so
# the engine cannot greedily consume into the next markdown link, preventing
# polynomial backtracking on repeated '[](http://…' sequences.
_MD_LINK_RE = re.compile(r'\[([^\[\]]*)\]\((https?://[^\s\)\[]+)\)')
# Regex: bare URLs not already inside a markdown link parenthetical
_BARE_URL_RE = re.compile(r'(?<!\()(https?://[^\s\)\]\[>]+)')


def extract_urls_from_markdown(text: str) -> list[str]:
    """Return unique http/https URLs found in markdown text, in order of appearance."""
    urls: list[str] = []
    seen: set[str] = set()

    for match in _MD_LINK_RE.finditer(text):
        url = match.group(2).rstrip('.,;:!?')
        if url not in seen:
            seen.add(url)
            urls.append(url)

    for match in _BARE_URL_RE.finditer(text):
        url = match.group(0).rstrip('.,;:!?')
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls


def classify_result(result: LinkCheckResult, url: str) -> tuple[str, str]:
    """Return (emoji, human_label) for a check result."""
    domain = urlparse(url).netloc.lower()
    code = result.status_code

    if code == 0:
        error = result.error_type or "unknown"
        label_map = {
            "timeout": "Timed out",
            "dns": "DNS resolution failed",
            "tls": "TLS/certificate error",
        }
        return ("\u26a0\ufe0f", label_map.get(error, "Unreachable"))

    if 200 <= code < 300:
        return ("\u2705", "Valid")

    if 300 <= code < 400:
        return ("\u2197\ufe0f", "Redirected")

    if code == 403 and domain in RESTRICTED_DOMAINS:
        return ("\U0001f512", "Restricted (requires login)")

    if code == 404:
        return ("\u274c", "Broken (not found)")

    if 400 <= code < 500:
        return ("\u274c", f"Client error ({code})")

    if 500 <= code < 600:
        return ("\u26a0\ufe0f", f"Server error ({code})")

    return ("\u26a0\ufe0f", f"Unexpected status ({code})")


def check_response_urls(response_text: str) -> str:
    """Extract URLs from a chatbot response, check them, return a markdown footer.

    - Disabled when WEB_LINK_VALIDATOR_INLINE_CHECK_ENABLED is false
    - Caps at INLINE_CHECK_MAX_URLS URLs (default 5)
    - Uses INLINE_CHECK_TIMEOUT_S per URL (default 3s)
    - Runs checks concurrently
    - Returns empty string if no http/https URLs found
    """
    if not INLINE_CHECK_ENABLED:
        return ""

    urls = extract_urls_from_markdown(response_text)
    if not urls:
        return ""

    urls = urls[:INLINE_CHECK_MAX_URLS]
    timeout = (INLINE_CHECK_TIMEOUT_S, INLINE_CHECK_TIMEOUT_S)

    results: list[tuple[str, str, str]] = []  # (url, emoji, label)

    with ThreadPoolExecutor(max_workers=len(urls)) as executor:
        future_to_url = {
            executor.submit(
                check_url,
                url,
                rate_limiter=None,
                retries=0,
                timeout=timeout,
                get_body=False,
            ): url
            for url in urls
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result, _ = future.result()
                emoji, label = classify_result(result, url)
                results.append((url, emoji, label))
            except Exception:
                results.append((url, "\u26a0\ufe0f", "Check failed"))

    if not results:
        return ""

    # Preserve the original order URLs appeared in the response
    url_order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda r: url_order.get(r[0], 999))

    lines = ["\n---", "**Link Status:**"]
    for url, emoji, label in results:
        display = url if len(url) <= 70 else url[:67] + "..."
        lines.append(f"- {emoji} `{display}` -- {label}")

    return "\n".join(lines)
