"""Icon management module."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from typing import Any

from .config import Config
from .utils import sanitize_name


class IconManager:
    """Manages the downloading and caching of provider icons."""

    _metadata: dict[str, Any] | None = None
    _triggered: set[str] = set()

    @staticmethod
    def _get_metadata(provider_name: str) -> dict[str, Any] | None:
        """Load icon metadata for a given provider."""
        if IconManager._metadata is None:
            metadata_path = os.path.join(Config.CACHE_DIR, "icons.json")
            IconManager._metadata = {}
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        IconManager._metadata = json.load(f)
                except Exception as e:
                    logging.error(f"Failed to load metadata: {e}")

        assert IconManager._metadata is not None  # for python3.8 pylint
        return IconManager._metadata.get(provider_name)

    @staticmethod
    def _resolve_cached_path(provider_name: str, meta: dict[str, Any] | None) -> str | None:
        """Resolve the cached icon file path, or None if not cached."""
        if meta:
            status = meta.get("status")
            if status in ["success", "cached"]:
                filename = meta.get("filename")
                if filename:
                    path = os.path.join(Config.ICONS_DIR, filename)
                    if os.path.exists(path):
                        return path
            return None

        # No metadata: try to find icon by filename pattern
        safe_name = sanitize_name(provider_name)
        for ext in Config.IMAGE_EXTENSIONS:
            path = os.path.join(Config.ICONS_DIR, f"{safe_name}{ext}")
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def _should_download(meta: dict[str, Any] | None, cached_path: str | None) -> bool:
        """Determine whether a background download should be triggered."""
        now = time.time()

        if not meta:
            return True  # No metadata at all

        status = meta.get("status")
        timestamp = meta.get("timestamp", 0)

        if status == "failed":
            return now - timestamp >= Config.ICONS_TTL

        if status in ["success", "cached"]:
            if not cached_path:
                return True  # File missing
            return now - timestamp > Config.ICON_REFRESH_SECONDS

        return True

    @staticmethod
    def get_icon_path(provider_name: str) -> str:
        """Get the path to a provider's icon, triggering download if necessary."""
        default_icon = os.path.join(Config.PROJECT_ROOT, "resources", "openrouter.svg")

        if not provider_name:
            return default_icon

        meta = IconManager._get_metadata(provider_name)
        cached_path = IconManager._resolve_cached_path(provider_name, meta)

        if IconManager._should_download(meta, cached_path) and provider_name not in IconManager._triggered:
            IconManager._triggered.add(provider_name)
            IconManager.trigger_batch_download(provider_name)

        return cached_path if cached_path else default_icon

    @staticmethod
    def trigger_batch_download(provider_name: str) -> None:
        """Trigger a background process to download an icon."""
        if not provider_name:
            return

        script = os.path.join(Config.PROJECT_ROOT, "download_icon.py")
        cache_dir_arg = Config.CACHE_DIR

        cmd = [sys.executable, script, cache_dir_arg, provider_name]
        with subprocess.Popen(
            cmd,
            cwd=Config.PROJECT_ROOT,
            stdout=subprocess.DEVNULL if not Config.DEBUG_MODE else None,
            stderr=subprocess.DEVNULL if not Config.DEBUG_MODE else None,
            close_fds=True,
        ) as _:
            pass
