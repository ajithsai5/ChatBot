"""Run orchestration logic for validator scan execution."""

from __future__ import annotations

import atexit
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse

from .checker import RateLimiter, check_url
from .config import (
    BATCH_SIZE,
    CONCURRENCY,
    LRU_CACHE_SIZE,
    MAX_LINKS_PER_PAGE,
    MAX_RUNS_KEPT,
    RATE_LIMIT_RPS,
    RESTRICTED_DOMAINS,
    SKIP_DOMAINS,
)
from .csv_writer import CsvStreamWriter, VERIFIED_COLUMNS
from .extractor import extract_links, is_static_resource
from .models import RunMeta, RunMode, RunStatus
from .sitemap import get_all_page_urls

import csv as csv_module
import logging


LOGGER = logging.getLogger(__name__)


class _LRUCache:
    """Thread-safe bounded LRU cache for deduplicating checked URLs within a run."""

    def __init__(self, maxsize: int = LRU_CACHE_SIZE) -> None:
        self._cache: OrderedDict[str, int] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str) -> int | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: str, status: int) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = status
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


# Global lock to ensure only one run at a time (in-process)
_run_lock = threading.Lock()
_current_run: RunMeta | None = None
_cancel_event = threading.Event()

# File-based lock to prevent duplicate runs across processes


def _lock_file_path() -> str:
    """Return the lock-file path based on the *current* REPORTS_DIR."""
    from .config import REPORTS_DIR as _dir
    return os.path.join(_dir, ".run.lock")


def _acquire_file_lock() -> bool:
    """Acquire a cross-process file lock. Returns True if acquired."""
    from .config import REPORTS_DIR as _dir
    lock = _lock_file_path()
    os.makedirs(_dir, exist_ok=True)
    # Check if lock file exists and is stale (older than 12 hours = stuck run)
    if os.path.exists(lock):
        try:
            age = time.time() - os.path.getmtime(lock)
            if age > 12 * 3600:
                os.remove(lock)  # stale lock, remove it
            else:
                return False  # another process holds the lock
        except OSError:
            return False
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_file_lock() -> None:
    """Release the cross-process file lock."""
    try:
        os.remove(_lock_file_path())
    except OSError:
        pass


def is_running() -> bool:
    # Check in-process state first
    if _current_run is not None and _current_run.status == RunStatus.RUNNING:
        return True
    # Check cross-process file lock
    lock = _lock_file_path()
    if os.path.exists(lock):
        try:
            age = time.time() - os.path.getmtime(lock)
            if age < 12 * 3600:
                return True
        except OSError:
            pass
    return False


def get_current_run() -> RunMeta | None:
    return _current_run


def cancel_current_run() -> bool:
    global _current_run
    if _current_run and _current_run.status == RunStatus.RUNNING:
        _cancel_event.set()
        return True
    return False


def _cleanup_on_exit() -> None:
    """Release file lock and mark run as failed if process exits unexpectedly."""
    global _current_run
    if _current_run and _current_run.status == RunStatus.RUNNING:
        _current_run.status = RunStatus.FAILED
        try:
            _current_run.save()
        except OSError:
            pass
        _current_run = None
    _release_file_lock()


atexit.register(_cleanup_on_exit)


def _cleanup_old_runs() -> None:
    from .config import REPORTS_DIR as _dir
    runs = RunMeta.list_runs()
    if len(runs) > MAX_RUNS_KEPT:
        for old_run in runs[MAX_RUNS_KEPT:]:
            run_dir = os.path.join(_dir, old_run.run_id)
            try:
                for f in os.listdir(run_dir):
                    os.remove(os.path.join(run_dir, f))
                os.rmdir(run_dir)
            except OSError:
                pass


def run_link_check(mode: RunMode = RunMode.MANUAL, resume_run_id: str | None = None, pre_run_id: str | None = None) -> RunMeta:
    """Execute a full web link validation run. Blocks until complete.

    If resume_run_id is provided, resumes from checkpoint_index of that run.
    If pre_run_id is provided, uses that ID for the new run (to match what was returned to the caller).
    """
    global _current_run

    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("A web link validation run is already in progress")

    if not _acquire_file_lock():
        _run_lock.release()
        raise RuntimeError("A link-check run is already in progress (another process)")

    _cancel_event.clear()

    try:
        # Clean up old runs at the start to free disk space
        _cleanup_old_runs()

        # Resume or new run
        if resume_run_id:
            meta = RunMeta.load(resume_run_id)
            if not meta:
                raise ValueError(f"Run {resume_run_id} not found")
            meta.status = RunStatus.RUNNING
        elif pre_run_id:
            meta = RunMeta(mode=mode)
            meta.run_id = pre_run_id
        else:
            meta = RunMeta(mode=mode)

        _current_run = meta
        meta.save()

        rate_limiter = RateLimiter(rps=RATE_LIMIT_RPS)
        url_cache = _LRUCache()

        # Fetch sitemap
        LOGGER.info("Run %s started (mode=%s)", meta.run_id, mode.value)
        page_urls = get_all_page_urls()
        meta.total_pages = len(page_urls)
        meta.save()
        LOGGER.info("Found %s pages in sitemap", len(page_urls))

        if not page_urls:
            meta.status = RunStatus.SUCCEEDED
            meta.end_time = time.time()
            meta.save()
            meta.save_summary()
            return meta

        csv_path = meta.csv_path
        csv_writer = CsvStreamWriter(csv_path)
        is_resume = resume_run_id is not None and meta.checkpoint_index > 0
        csv_writer.open(append=is_resume)

        try:
            start_index = meta.checkpoint_index
            # Process pages in batches
            for batch_start in range(start_index, len(page_urls), BATCH_SIZE):
                if _cancel_event.is_set():
                    LOGGER.info("Run %s cancelled at page index %s", meta.run_id, batch_start)
                    meta.status = RunStatus.CANCELLED
                    meta.checkpoint_index = batch_start
                    break

                batch_end = min(batch_start + BATCH_SIZE, len(page_urls))
                batch = page_urls[batch_start:batch_end]

                _process_page_batch(batch, meta, csv_writer, rate_limiter, url_cache)

                meta.checkpoint_index = batch_end
                meta.save()

            if meta.status == RunStatus.RUNNING:
                meta.status = RunStatus.SUCCEEDED

        except Exception as exc:
            LOGGER.error("Run %s failed: %s", meta.run_id, exc)
            meta.status = RunStatus.FAILED
        finally:
            csv_writer.close()

        meta.end_time = time.time()
        # Build top failing domains (top 10)
        sorted_domains = sorted(meta.top_failing_domains.items(), key=lambda x: x[1], reverse=True)[:10]
        meta.top_failing_domains = dict(sorted_domains)
        meta.save()
        meta.save_summary()

        # Verification pass: re-check all failed links to confirm
        if meta.status == RunStatus.SUCCEEDED and not _cancel_event.is_set():
            try:
                _verify_failed_links(meta, RateLimiter(rps=RATE_LIMIT_RPS))
            except Exception as exc:
                LOGGER.warning("Verification pass failed: %s", exc)

        _cleanup_old_runs()
        LOGGER.info("Run %s finished: %s in %ss", meta.run_id, meta.status.value, meta.duration_s)
        return meta

    finally:
        _current_run = None
        _release_file_lock()
        _run_lock.release()


def _process_page_batch(
    page_urls: list[str],
    meta: RunMeta,
    csv_writer: CsvStreamWriter,
    rate_limiter: RateLimiter,
    url_cache: _LRUCache,
) -> None:
    """Process a batch of page URLs with bounded concurrency."""
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {
            executor.submit(_check_single_page, url, meta, csv_writer, rate_limiter, url_cache): url
            for url in page_urls
        }
        for future in as_completed(futures):
            if _cancel_event.is_set():
                break
            try:
                future.result()
            except Exception as exc:
                LOGGER.warning("Page processing error: %s", exc)


def _check_single_page(
    page_url: str,
    meta: RunMeta,
    csv_writer: CsvStreamWriter,
    rate_limiter: RateLimiter,
    url_cache: _LRUCache,
) -> None:
    """Fetch a page, extract links, check each link, write results to CSV."""
    if _cancel_event.is_set():
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    # Check the page itself
    page_result, page_body = check_url(page_url, rate_limiter=rate_limiter, get_body=True)
    meta.pages_checked += 1

    page_status = page_result.status_code

    # Write page-level row
    csv_writer.write_row({
        "runId": meta.run_id,
        "checkedAt": now_iso,
        "pageUrl": page_url,
        "pageStatus": page_status,
        "linkUrl": "",
        "linkStatus": "",
        "linkType": "page",
        "redirectedTo": page_result.redirected_to,
        "errorType": page_result.error_type,
        "responseTimeMs": page_result.response_time_ms,
    })

    meta.increment_status(page_status)
    if page_result.error_type and page_result.error_type not in ("4xx", "5xx"):
        meta.record_error()

    if not page_body:
        return

    # Extract all links from the page (href, css, script, img)
    # Static resources (JS, CSS, images) are skipped below before checking
    links = extract_links(page_body, page_url, max_links=MAX_LINKS_PER_PAGE)
    meta.total_links += len(links)

    for link_url, link_type in links:
        if _cancel_event.is_set():
            return

        # Skip static resources — JS, CSS, images, JSON, PDF are not checked or reported
        if link_type in ("css", "script", "img") or is_static_resource(link_url):
            continue

        # Skip links to excluded domains
        link_domain = urlparse(link_url).netloc
        if link_domain in SKIP_DOMAINS:
            continue

        # Dedup via LRU cache
        cached_status = url_cache.get(link_url)
        if cached_status is not None:
            meta.links_checked += 1
            csv_writer.write_row({
                "runId": meta.run_id,
                "checkedAt": now_iso,
                "pageUrl": page_url,
                "pageStatus": page_status,
                "linkUrl": link_url,
                "linkStatus": cached_status,
                "linkType": link_type,
                "redirectedTo": "",
                "errorType": _cached_error_type(cached_status),
                "responseTimeMs": 0,
            })
            meta.increment_status(cached_status)
            if cached_status == 0:
                meta.record_error()
            continue

        link_result, _ = check_url(link_url, rate_limiter=rate_limiter, get_body=False)
        meta.links_checked += 1
        url_cache.put(link_url, link_result.status_code)

        csv_writer.write_row({
            "runId": meta.run_id,
            "checkedAt": now_iso,
            "pageUrl": page_url,
            "pageStatus": page_status,
            "linkUrl": link_url,
            "linkStatus": link_result.status_code,
            "linkType": link_type,
            "redirectedTo": link_result.redirected_to,
            "errorType": link_result.error_type,
            "responseTimeMs": link_result.response_time_ms,
        })

        meta.increment_status(link_result.status_code)
        if link_result.error_type:
            if link_result.status_code == 0:
                meta.record_error()
            if link_result.status_code >= 400 or link_result.status_code == 0:
                domain = urlparse(link_url).netloc
                meta.record_failing_domain(domain)


def _cached_error_type(status: int) -> str:
    if 400 <= status < 500:
        return "4xx"
    if 500 <= status < 600:
        return "5xx"
    if status == 0:
        return "other"
    return ""


def _format_affected(pages: set[str]) -> str:
    """Format a set of affected page URLs into a truncated string."""
    affected = "; ".join(sorted(pages)[:5])
    if len(pages) > 5:
        affected += f" (+{len(pages) - 5} more)"
    return affected


def _verify_failed_links(meta: RunMeta, rate_limiter: RateLimiter) -> None:
    """Re-check all failed/errored unique URLs using GET to confirm they are truly broken.

    Reads the main results CSV, collects unique failing URLs, re-checks each one,
    and writes a verified_failures.csv with results.
    """
    csv_path = meta.csv_path
    if not os.path.exists(csv_path):
        return

    LOGGER.info("Starting verification pass for run %s", meta.run_id)

    # Collect unique failing URLs and their affected pages
    failed_urls: dict[str, dict] = {}  # url -> {status, pages}
    try:
        csv_module.field_size_limit(10 * 1024 * 1024)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv_module.DictReader(f)
            for row in reader:
                link_url = row.get("linkUrl", "").strip()
                if not link_url:
                    continue
                try:
                    status = int(row.get("linkStatus", "0") or "0")
                except ValueError:
                    status = 0
                if status >= 400 or status == 0:
                    # Skip excluded domains
                    link_domain = urlparse(link_url).netloc
                    if link_domain in SKIP_DOMAINS:
                        continue
                    if link_url not in failed_urls:
                        failed_urls[link_url] = {"status": status, "pages": set()}
                    page = row.get("pageUrl", "")
                    if page:
                        failed_urls[link_url]["pages"].add(page)
    except Exception as exc:
        LOGGER.warning("Verification: could not read CSV: %s", exc)
        return

    if not failed_urls:
        LOGGER.info("Verification: no failed links to re-check")
        return

    LOGGER.info("Verification: re-checking %s unique failed URLs", len(failed_urls))

    # Write verified results
    verified_path = os.path.join(os.path.dirname(csv_path), "verified_failures.csv")
    confirmed_broken = 0
    restricted_count = 0
    false_positives = 0

    def _verify_one(url: str) -> dict:
        """Re-check a single URL and return the row dict."""
        info = failed_urls[url]

        # Skip restricted domains entirely — we already know they return 403
        domain = urlparse(url).netloc
        if domain in RESTRICTED_DOMAINS:
            return {
                "linkUrl": url,
                "originalStatus": info["status"],
                "verifiedStatus": 403,
                "verifiedAt": datetime.now(timezone.utc).isoformat(),
                "errorType": "4xx",
                "responseTimeMs": 0,
                "stillBroken": "RESTRICTED",
                "affectedPages": _format_affected(info["pages"]),
            }

        result, _ = check_url(url, rate_limiter=rate_limiter, get_body=False, retries=1)
        # If HEAD gave error, try GET as fallback
        if result.status_code == 0 or result.status_code >= 400:
            result_get, _ = check_url(url, rate_limiter=rate_limiter, get_body=True, retries=0)
            if result_get.status_code != 0 and result_get.status_code < 400:
                result = result_get

        still_broken = result.status_code >= 400 or result.status_code == 0
        if still_broken:
            broken_label = "YES"
        else:
            broken_label = "NO"

        return {
            "linkUrl": url,
            "originalStatus": info["status"],
            "verifiedStatus": result.status_code,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "errorType": result.error_type,
            "responseTimeMs": result.response_time_ms,
            "stillBroken": broken_label,
            "affectedPages": _format_affected(info["pages"]),
        }

    # Run verification concurrently
    verified_rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_to_url = {
            executor.submit(_verify_one, url): url
            for url in failed_urls
        }
        for future in as_completed(future_to_url):
            if _cancel_event.is_set():
                break
            try:
                row = future.result()
                verified_rows.append(row)
            except Exception as exc:
                url = future_to_url[future]
                LOGGER.warning("Verification error for %s: %s", url, exc)

    with open(verified_path, "w", newline="", encoding="utf-8") as f:
        writer = csv_module.DictWriter(f, fieldnames=VERIFIED_COLUMNS)
        writer.writeheader()
        for row in verified_rows:
            label = row["stillBroken"]
            if label == "RESTRICTED":
                restricted_count += 1
            elif label == "YES":
                confirmed_broken += 1
            else:
                false_positives += 1
            writer.writerow(row)

    LOGGER.info(
        "Verification complete: %s confirmed broken, %s restricted, %s false positives",
        confirmed_broken, restricted_count, false_positives,
    )
    LOGGER.info("Verified failures saved to: %s", verified_path)


def start_run_async(mode: RunMode = RunMode.MANUAL, resume_run_id: str | None = None) -> str:
    """Start a web link validation run in a background thread. Returns the run_id."""
    if is_running():
        raise RuntimeError("A web link validation run is already in progress")

    # Pre-create the RunMeta and persist it immediately so that status
    # queries from any worker/process can discover the run right away.
    if resume_run_id:
        run_id = resume_run_id
    else:
        meta = RunMeta(mode=mode)
        meta.save()
        run_id = meta.run_id

    def _worker():
        try:
            run_link_check(mode=mode, resume_run_id=resume_run_id, pre_run_id=run_id)
        except Exception as exc:
            LOGGER.error("Async run failed: %s", exc)

    t = threading.Thread(target=_worker, daemon=True, name=f"web-link-validator-{run_id}")
    t.start()
    return run_id

