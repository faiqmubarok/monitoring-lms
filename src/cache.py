"""
cache.py
Phase 7: Cache sederhana berbasis JSON file di disk.

Cache menyimpan:
  - shortname → course info (id, fullname, dll)
  - course_id → sections raw

Cache hanya digunakan saat CACHE_ENABLED=true.
FULL REFRESH mode akan skip cache sepenuhnya.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from src import config

logger = logging.getLogger(__name__)

_CACHE_VERSION = 1
_SHORTNAME_FILE = "shortname_cache.json"
_CONTENTS_FILE = "contents_cache.json"


class DiskCache:
    """
    Cache key-value berbasis JSON file.
    Thread-safe untuk single-process (tidak memakai lock file).
    """

    def __init__(self, cache_file: str) -> None:
        self._path = Path(config.CACHE_DIR) / cache_file
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not config.CACHE_ENABLED:
            return
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    raw = json.load(f)
                if raw.get("version") == _CACHE_VERSION:
                    self._data = raw.get("entries", {})
                    logger.debug("Cache loaded: %s (%d entries)", self._path, len(self._data))
            except Exception as exc:
                logger.warning("Gagal load cache %s: %s", self._path, exc)
                self._data = {}

    def _save(self) -> None:
        if not config.CACHE_ENABLED or not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = {"version": _CACHE_VERSION, "entries": self._data}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except Exception as exc:
            logger.warning("Gagal simpan cache %s: %s", self._path, exc)

    def get(self, key: str) -> Any | None:
        if not config.CACHE_ENABLED:
            return None
        entry = self._data.get(key)
        if entry is None:
            return None
        # TTL check (opsional — saat ini tidak pakai TTL, refresh manual)
        return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        if not config.CACHE_ENABLED:
            return
        self._data[key] = {"value": value, "ts": time.time()}
        self._dirty = True

    def invalidate(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._dirty = True

    def clear(self) -> None:
        self._data = {}
        self._dirty = True
        self._save()

    def flush(self) -> None:
        self._save()

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data


# Singleton instances
_shortname_cache: DiskCache | None = None
_contents_cache: DiskCache | None = None


def get_shortname_cache() -> DiskCache:
    global _shortname_cache
    if _shortname_cache is None:
        _shortname_cache = DiskCache(_SHORTNAME_FILE)
    return _shortname_cache


def get_contents_cache() -> DiskCache:
    global _contents_cache
    if _contents_cache is None:
        _contents_cache = DiskCache(_CONTENTS_FILE)
    return _contents_cache


def flush_all() -> None:
    """Simpan semua cache ke disk."""
    if _shortname_cache:
        _shortname_cache.flush()
    if _contents_cache:
        _contents_cache.flush()


def clear_all() -> None:
    """Hapus semua cache (FULL REFRESH)."""
    for cache in [get_shortname_cache(), get_contents_cache()]:
        cache.clear()
    logger.info("Cache dibersihkan (FULL REFRESH).")
