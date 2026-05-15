"""Configuration constants and paths for web-link-validator runtime."""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


BASE_URL: str = os.getenv("WEB_LINK_VALIDATOR_BASE_URL", "https://www.uhc.com/communityplan")
SITEMAP_URL: str = os.getenv("WEB_LINK_VALIDATOR_SITEMAP_URL", f"{BASE_URL}/sitemap.xml")
CONCURRENCY: int = _env_int("WEB_LINK_VALIDATOR_CONCURRENCY", 20)
RATE_LIMIT_RPS: float = _env_float("WEB_LINK_VALIDATOR_RATE_LIMIT_RPS", 20.0)
BATCH_SIZE: int = _env_int("WEB_LINK_VALIDATOR_BATCH_SIZE", 50)
MAX_LINKS_PER_PAGE: int = _env_int("WEB_LINK_VALIDATOR_MAX_LINKS_PER_PAGE", 200)
TIMEOUT_MS: int = _env_int("WEB_LINK_VALIDATOR_TIMEOUT_MS", 8000)
RETRIES: int = _env_int("WEB_LINK_VALIDATOR_RETRIES", 1)
SCHEDULE_CRON: str = os.getenv("WEB_LINK_VALIDATOR_SCHEDULE_CRON", "0 13 * * *")  # daily at 1:00 PM IST
REPORTS_DIR: str = os.getenv("WEB_LINK_VALIDATOR_REPORTS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "web-link-validator"))
MAX_RUNS_KEPT: int = _env_int("WEB_LINK_VALIDATOR_MAX_RUNS_KEPT", 10)
LRU_CACHE_SIZE: int = _env_int("WEB_LINK_VALIDATOR_LRU_CACHE_SIZE", 50000)
CONNECT_TIMEOUT_S: float = TIMEOUT_MS / 1000.0
READ_TIMEOUT_S: float = TIMEOUT_MS / 1000.0
MAX_SITEMAP_DEPTH: int = _env_int("WEB_LINK_VALIDATOR_MAX_SITEMAP_DEPTH", 5)

# Domains to skip when checking links (language subdomains outside our website scope)
_default_skip = (
    "es.uhc.com,ht.uhc.com,vi.uhc.com,zh.uhc.com,ilo.uhc.com,"
    "ko.uhc.com,tl.uhc.com,hmn.uhc.com,so.uhc.com,ar.uhc.com,"
    "mm.uhc.com,ksw.uhc.com"
)
SKIP_DOMAINS: set[str] = set(
    d.strip()
    for d in os.getenv("WEB_LINK_VALIDATOR_SKIP_DOMAINS", _default_skip).split(",")
    if d.strip()
)

# Domains that return 403 due to SSO/authentication — not truly broken
_default_restricted = "member.uhc.com,myuhc.com,www.myuhc.com,connect.werally.com"
RESTRICTED_DOMAINS: set[str] = set(
    d.strip()
    for d in os.getenv("WEB_LINK_VALIDATOR_RESTRICTED_DOMAINS", _default_restricted).split(",")
    if d.strip()
)

# Inline response URL checking settings
INLINE_CHECK_ENABLED: bool = os.getenv("WEB_LINK_VALIDATOR_INLINE_CHECK_ENABLED", "true").lower() in ("true", "1", "yes")
INLINE_CHECK_MAX_URLS: int = _env_int("WEB_LINK_VALIDATOR_INLINE_MAX_URLS", 5)
INLINE_CHECK_TIMEOUT_S: float = _env_float("WEB_LINK_VALIDATOR_INLINE_TIMEOUT_S", 3.0)

# ---------- Email notification settings ----------
# EMAIL IS INTENTIONALLY DISABLED. All email functionality has been turned off.
# The SMTP relay (maild2.corpmailsvcs.com) requires an approved sender address.
# To re-enable in the future, set WEB_LINK_VALIDATOR_EMAIL_ENABLED=true and configure
# an approved sender via WEB_LINK_VALIDATOR_EMAIL_SENDER.
EMAIL_ENABLED: bool = False  # Intentionally disabled — do not change without approved sender
EMAIL_SMTP_HOST: str = os.getenv("WEB_LINK_VALIDATOR_EMAIL_SMTP_HOST", "maild2.corpmailsvcs.com")
EMAIL_SMTP_PORT: int = _env_int("WEB_LINK_VALIDATOR_EMAIL_SMTP_PORT", 25)
EMAIL_USE_TLS: bool = os.getenv("WEB_LINK_VALIDATOR_EMAIL_USE_TLS", "false").lower() in ("true", "1", "yes")
EMAIL_SMTP_USER: str = os.getenv("WEB_LINK_VALIDATOR_EMAIL_SMTP_USER", "")
EMAIL_SMTP_PASSWORD: str = os.getenv("WEB_LINK_VALIDATOR_EMAIL_SMTP_PASSWORD", "")
EMAIL_SENDER: str = os.getenv("WEB_LINK_VALIDATOR_EMAIL_SENDER", "noreply-uhccp-chatbot@uhc.com")
EMAIL_RECIPIENTS: list[str] = [
    r.strip()
    for r in os.getenv("WEB_LINK_VALIDATOR_EMAIL_RECIPIENTS", "uhccp_portal_it@ds.uhc.com").split(",")
    if r.strip()
]
EMAIL_SUBJECT_PREFIX: str = os.getenv("WEB_LINK_VALIDATOR_EMAIL_SUBJECT_PREFIX", "[UHCCP Web Link Validator]")

