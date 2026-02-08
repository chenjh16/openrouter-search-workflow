"""OpenRouter API client."""

from __future__ import annotations
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from .config import Config
from .cache import CacheManager


class APIClient:
    """Handles HTTP requests to the OpenRouter API."""

    @staticmethod
    def fetch(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Fetch JSON data from a URL."""
        if headers is None:
            headers = {}
        default_headers = {
            "User-Agent": Config.USER_AGENT,
            "Authorization": f"Bearer {Config.API_KEY}",
        }
        default_headers.update(headers)
        req = urllib.request.Request(url, headers=default_headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                return json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as e:
            logging.error(f"HTTP Error {e.code}: {e.reason}")
            raise
        except urllib.error.URLError as e:
            logging.error(f"URL Error: {e.reason}")
            raise
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response")
            raise

    @staticmethod
    def get_models(force: bool = False) -> list[dict[str, Any]]:
        """Fetch list of available models from cache or API."""
        if not force:
            cached = CacheManager.read("models.json", Config.MODELS_TTL)
            if cached is not None:
                return cached

        data = APIClient.fetch(Config.MODELS_URL)
        models = data.get("data", [])
        CacheManager.write("models.json", models)
        return models

    @staticmethod
    def get_endpoints(model_id: str, force: bool = False) -> list[dict[str, Any]]:
        """Fetch endpoints for a specific model."""
        cache_file = "endpoints/" + model_id.replace("/", "_") + ".json"
        if not force:
            cached = CacheManager.read(cache_file, Config.ENDPOINTS_TTL)
            if cached is not None:
                return cached

        url = Config.ENDPOINTS_URL.format(model_id=model_id)
        data = APIClient.fetch(url)
        endpoints = data.get("data", {}).get("endpoints", [])
        CacheManager.write(cache_file, endpoints)
        return endpoints
