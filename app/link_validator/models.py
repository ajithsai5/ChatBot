"""Data models used by validator run lifecycle and summaries."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

def _reports_dir() -> str:
    """Import REPORTS_DIR at call time so env-var overrides always apply."""
    from .config import REPORTS_DIR
    return REPORTS_DIR


class RunMode(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunMeta:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    mode: RunMode = RunMode.MANUAL
    status: RunStatus = RunStatus.RUNNING
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_pages: int = 0
    pages_checked: int = 0
    total_links: int = 0
    links_checked: int = 0
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    errors: int = 0
    top_failing_domains: dict = field(default_factory=dict)
    checkpoint_index: int = 0  # next sitemap URL index to resume from

    @property
    def duration_s(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)

    @property
    def csv_path(self) -> str:
        return os.path.join(_reports_dir(), self.run_id, "results.csv")

    @property
    def summary_path(self) -> str:
        return os.path.join(_reports_dir(), self.run_id, "summary.json")

    @property
    def meta_path(self) -> str:
        return os.path.join(_reports_dir(), self.run_id, "meta.json")

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.meta_path), exist_ok=True)
        with open(self.meta_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def save_summary(self) -> None:
        summary = {
            "run_id": self.run_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_s": self.duration_s,
            "total_pages": self.total_pages,
            "pages_checked": self.pages_checked,
            "total_links": self.total_links,
            "links_checked": self.links_checked,
            "status_buckets": {
                "2xx": self.status_2xx,
                "3xx": self.status_3xx,
                "4xx": self.status_4xx,
                "5xx": self.status_5xx,
                "errors": self.errors,
            },
            "top_failing_domains": self.top_failing_domains,
        }
        os.makedirs(os.path.dirname(self.summary_path), exist_ok=True)
        with open(self.summary_path, "w") as f:
            json.dump(summary, f, indent=2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mode"] = self.mode.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RunMeta":
        data = dict(data)
        data["mode"] = RunMode(data.get("mode", "manual"))
        data["status"] = RunStatus(data.get("status", "running"))
        if "top_failing_domains" not in data:
            data["top_failing_domains"] = {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def load(cls, run_id: str) -> Optional["RunMeta"]:
        meta_path = os.path.join(_reports_dir(), run_id, "meta.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def list_runs(cls) -> list["RunMeta"]:
        if not os.path.isdir(_reports_dir()):
            return []
        runs = []
        for name in os.listdir(_reports_dir()):
            meta = cls.load(name)
            if meta:
                runs.append(meta)
        runs.sort(key=lambda r: r.start_time, reverse=True)
        return runs

    @classmethod
    def latest(cls) -> Optional["RunMeta"]:
        runs = cls.list_runs()
        return runs[0] if runs else None

    def increment_status(self, status_code: int) -> None:
        if 200 <= status_code < 300:
            self.status_2xx += 1
        elif 300 <= status_code < 400:
            self.status_3xx += 1
        elif 400 <= status_code < 500:
            self.status_4xx += 1
        elif 500 <= status_code < 600:
            self.status_5xx += 1

    def record_error(self) -> None:
        self.errors += 1

    def record_failing_domain(self, domain: str) -> None:
        self.top_failing_domains[domain] = self.top_failing_domains.get(domain, 0) + 1

