"""Sitemap discovery and parsing helpers for validator scans.

Main responsibility:
- Fetch sitemap XML from the configured URL.
- Parse sitemap indexes and leaf sitemaps to collect all page URLs.

Not handled here:
- Link checking or CSV reporting (see runner.py, checker.py).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Optional

import requests

from .config import SITEMAP_URL, CONNECT_TIMEOUT_S, READ_TIMEOUT_S, MAX_SITEMAP_DEPTH


LOGGER = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_sitemap_xml(url: str, timeout: tuple[float, float] | None = None) -> Optional[str]:
    timeout = timeout or (CONNECT_TIMEOUT_S, READ_TIMEOUT_S)
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "UHCCP-WebLinkValidator/1.0"})
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        LOGGER.warning("Failed to fetch sitemap %s: %s", url, exc)
        return None


def parse_sitemap_urls(xml_text: str) -> list[str]:
    """Extract <loc> URLs from a sitemap XML body."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        LOGGER.warning("Sitemap XML parse error: %s", exc)
        return []

    urls: list[str] = []
    # <url><loc>...</loc></url>
    for loc in root.findall(".//sm:url/sm:loc", SITEMAP_NS):
        if loc.text:
            urls.append(loc.text.strip())
    # fallback: no namespace
    if not urls:
        for loc in root.findall(".//url/loc"):
            if loc.text:
                urls.append(loc.text.strip())
    return urls


def parse_sitemap_index(xml_text: str) -> list[str]:
    """Extract child sitemap URLs from a sitemap index XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    sitemap_urls: list[str] = []
    for loc in root.findall(".//sm:sitemap/sm:loc", SITEMAP_NS):
        if loc.text:
            sitemap_urls.append(loc.text.strip())
    # fallback: no namespace
    if not sitemap_urls:
        for loc in root.findall(".//sitemap/loc"):
            if loc.text:
                sitemap_urls.append(loc.text.strip())
    return sitemap_urls


def is_sitemap_index(xml_text: str) -> bool:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False
    tag = root.tag.lower()
    return "sitemapindex" in tag


def get_all_page_urls(sitemap_url: str | None = None, depth: int = 0) -> list[str]:
    """Recursively fetch and parse sitemaps, returning all page URLs."""
    sitemap_url = sitemap_url or SITEMAP_URL
    if depth > MAX_SITEMAP_DEPTH:
        LOGGER.info("Max sitemap depth (%s) reached, stopping", MAX_SITEMAP_DEPTH)
        return []

    xml_text = fetch_sitemap_xml(sitemap_url)
    if not xml_text:
        return []

    if is_sitemap_index(xml_text):
        child_urls = parse_sitemap_index(xml_text)
        LOGGER.info("Sitemap index at %s: %s child sitemaps", sitemap_url, len(child_urls))
        all_urls: list[str] = []
        for child_url in child_urls:
            all_urls.extend(get_all_page_urls(child_url, depth=depth + 1))
        return all_urls
    else:
        urls = parse_sitemap_urls(xml_text)
        LOGGER.info("Sitemap at %s: %s page URLs", sitemap_url, len(urls))
        return urls

