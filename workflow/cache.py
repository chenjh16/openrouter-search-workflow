"""Cache management."""

from __future__ import annotations
import json
import logging
import os
import tempfile
import time
from typing import Any

from .config import Config


class CacheManager:
    """Manages local file caching for models and endpoints."""

    @staticmethod
    def ensure_dir() -> None:
        """Ensure cache directories exist."""
        os.makedirs(Config.CACHE_DIR, exist_ok=True)
        os.makedirs(Config.ICONS_DIR, exist_ok=True)

    @staticmethod
    def read(filename: str, ttl: int) -> Any:
        """Read data from cache if valid."""
        path = os.path.join(Config.CACHE_DIR, filename)
        try:
            if not os.path.exists(path):
                return None

            # ttl < 0 means infinity
            if 0 <= ttl <= time.time() - os.path.getmtime(path):
                return None

            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.warning(f"Failed to read cache {path}: {e}")
        return None

    @staticmethod
    def write(filename: str, data: Any) -> None:
        """Write data to cache atomically."""
        CacheManager.ensure_dir()
        path = os.path.join(Config.CACHE_DIR, filename)
        try:
            # Ensure subdirectories exist (e.g. "endpoints/model.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Atomic write using temp file in same directory as target
            target_dir = os.path.dirname(path)
            fd, temp_path = tempfile.mkstemp(dir=target_dir, text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(temp_path, path)
            logging.debug(f"Wrote cache: {path}")
        except OSError as e:
            logging.error(f"Failed to write cache {path}: {e}")
            if "temp_path" in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
