"""URL extraction helpers for validator source collection."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .config import MAX_LINKS_PER_PAGE

_SKIP_SCHEMES = {"mailto", "tel", "javascript", "data", "ftp"}

# Static resource extensions — used by the runner to skip checking these.
SKIP_EXTENSIONS = frozenset({
    ".js", ".css", ".json", ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
})


def is_static_resource(url: str) -> bool:
    """Return True if the URL points to a static resource (JS/CSS/image)."""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


class _LinkParser(HTMLParser):
    """Extract links from HTML tags: <a>, <link>, <script>, <img>."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # (url, link_type)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: v for k, v in attrs if v}
        tag_lower = tag.lower()
        # <a href="..."> — navigational hyperlink, classified as "href"
        if tag_lower == "a" and "href" in attr_map:
            self.links.append((attr_map["href"], "href"))
        elif tag_lower == "link" and "href" in attr_map:
            self.links.append((attr_map["href"], "css"))
        elif tag_lower == "script" and "src" in attr_map:
            self.links.append((attr_map["src"], "script"))
        elif tag_lower == "img" and "src" in attr_map:
            self.links.append((attr_map["src"], "img"))

    def error(self, message: str) -> None:
        pass  # required override


def _should_skip(url: str) -> bool:
    """Return True if the URL should be filtered out."""
    stripped = url.strip()
    if not stripped or stripped == "#":
        return True
    parsed = urlparse(stripped)
    if parsed.scheme and parsed.scheme.lower() in _SKIP_SCHEMES:
        return True
    # pure fragment
    if stripped.startswith("#"):
        return True
    return False


def normalize_url(url: str, base_url: str) -> str | None:
    """Resolve relative URLs and strip fragments. Returns None if should be skipped."""
    if _should_skip(url):
        return None
    absolute = urljoin(base_url, url)
    parsed = urlparse(absolute)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    # strip fragment
    clean = parsed._replace(fragment="").geturl()
    return clean


def extract_links(html: str, page_url: str, max_links: int | None = None) -> list[tuple[str, str]]:
    """Parse HTML and return up to max_links (url, link_type) tuples.

    Extracts all link types: href, css, script, img.
    link_type values: "href" (navigational), "css", "script", "img".
    """
    if max_links is None:
        max_links = MAX_LINKS_PER_PAGE

    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:
        pass

    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_url, link_type in parser.links:
        normalized = normalize_url(raw_url, page_url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            results.append((normalized, link_type))
            if len(results) >= max_links:
                break
    return results

