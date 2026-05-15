"""CSV output writer utilities for validator report generation."""

from __future__ import annotations

import csv
import os
import threading
from typing import TextIO

CSV_COLUMNS = [
    "runId",
    "checkedAt",
    "pageUrl",
    "pageStatus",
    "linkUrl",
    "linkStatus",
    "linkType",
    "redirectedTo",
    "errorType",
    "responseTimeMs",
]


VERIFIED_COLUMNS = [
    "linkUrl",
    "originalStatus",
    "verifiedStatus",
    "verifiedAt",
    "errorType",
    "responseTimeMs",
    "stillBroken",
    "affectedPages",
]


class CsvStreamWriter:
    """Thread-safe, incrementally write web link validation results to a CSV file."""

    def __init__(self, csv_path: str) -> None:
        self._path = csv_path
        self._file: TextIO | None = None
        self._writer: csv.DictWriter | None = None
        self._lock = threading.Lock()

    def open(self, append: bool = False) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if append and os.path.exists(self._path):
            self._file = open(self._path, "a", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=CSV_COLUMNS)
        else:
            self._file = open(self._path, "w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=CSV_COLUMNS)
            self._writer.writeheader()

    def write_row(self, row: dict) -> None:
        with self._lock:
            if self._writer is None:
                raise RuntimeError("CsvStreamWriter not opened")
            self._writer.writerow(row)
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if self._file:
                try:
                    self._file.flush()
                    self._file.close()
                except OSError:
                    pass
                self._file = None
                self._writer = None

    def __enter__(self) -> "CsvStreamWriter":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __del__(self) -> None:
        """Safety net: release file handle if close() was never called."""
        if self._file and not self._file.closed:
            try:
                self._file.close()
            except OSError:
                pass

