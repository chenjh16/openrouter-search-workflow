#!/usr/bin/env python3
"""Alfred Script Filter for searching OpenRouter AI models."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# Configure logging - DEBUG only in debug mode to avoid stderr noise in Alfred
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("ALFRED_WORKFLOW_DEBUG") == "1" else logging.ERROR
)


class Config:
    """Configuration constants for the workflow."""
    # API URLs
    MODELS_URL = "https://openrouter.ai/api/v1/models"
    ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model_id}/endpoints"
    MODEL_PAGE_URL = "https://openrouter.ai/models/{model_id}"
    HF_PAGE_URL = "https://huggingface.co/{hf_id}"
    MODELSCOPE_URL = "https://modelscope.cn/models/{hf_id}"

    # Cache TTL (in seconds)
    MODELS_TTL = int(os.environ.get("MODELS_TTL") or 1440) * 60
    ENDPOINTS_TTL = int(os.environ.get("ENDPOINTS_TTL") or 30) * 60
    ICONS_TTL = int(os.environ.get("ICONS_TTL") or 43200) * 60

    # Display constants
    NEW_MODEL_DAYS = 14
    ICON_REFRESH_SECONDS = 300  # 5 minutes
    IMAGE_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg", ".webp")

    # Paths
    DEBUG_MODE = os.environ.get("ALFRED_WORKFLOW_DEBUG") == "1"
    DEBUG_CACHE_DIR = os.path.join(
        os.path.dirname(__file__), ".temp", "alfred-openrouter"
    )
    CACHE_DIR = os.environ.get("alfred_workflow_cache") or DEBUG_CACHE_DIR
    ICONS_DIR = os.path.join(CACHE_DIR, "icons")
    ENDPOINTS_DIR = os.path.join(CACHE_DIR, "endpoints")
    API_KEY = os.environ.get("OPENROUTER_API_KEY") or ""


@dataclass
class AlfredItem:  # pylint: disable=too-many-instance-attributes
    """Represents an item in Alfred's Script Filter JSON output.

    See: https://www.alfredapp.com/help/workflows/inputs/script-filter/json/
    """

    title: str
    """The large text displayed as the main item title."""

    subtitle: str
    """The smaller text displayed below the title."""

    arg: str | None = None
    """The argument passed to connected output actions when actioned (Enter key)."""

    autocomplete: str | None = None
    """The value inserted into Alfred's search field when user presses Tab."""

    icon: str | None = None
    """Path to icon file (PNG, ICNS, or app bundle). Uses workflow default if None."""

    valid: bool = True
    """Whether the item can be actioned. If False, Enter does nothing and item is dimmed."""

    mods: dict[str, Any] | None = None
    """Modifier key overrides (cmd/alt/ctrl/shift/fn) with 'valid', 'arg', 'subtitle'."""

    text: dict[str, str] | None = None
    """Text for copy (Cmd+C) and Large Type (Cmd+L). Dict with 'copy'/'largetype' keys."""

    quicklookurl: str | None = None
    """URL to preview when user presses Shift or Cmd+Y. Disabled if None."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the item to a dictionary for JSON serialization."""
        item: dict[str, Any] = {
            "title": self.title,
            "subtitle": self.subtitle,
            "arg": self.arg,
            "valid": self.valid,
        }
        if self.autocomplete is not None:
            item["autocomplete"] = self.autocomplete
        if self.icon:
            item["icon"] = {"path": self.icon}
        if self.mods:
            item["mods"] = self.mods
        if self.text:
            item["text"] = self.text
        if self.quicklookurl:
            item["quicklookurl"] = self.quicklookurl
        return item


def output_alfred_items(items: list[AlfredItem]) -> None:
    """Output a list of AlfredItem objects as JSON to stdout."""
    print(json.dumps({"items": [item.to_dict() for item in items]}))


def output_error(title: str, subtitle: str, arg: str = "") -> None:
    """Output an error message as an AlfredItem."""
    output_alfred_items(
        [AlfredItem(title=title, subtitle=subtitle, arg=arg, valid=False)]
    )


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
            # Atomic write using temp file
            fd, temp_path = tempfile.mkstemp(dir=Config.CACHE_DIR, text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(temp_path, path)
            logging.debug(f"Wrote cache: {path}")
        except OSError as e:
            logging.error(f"Failed to write cache {path}: {e}")
            if "temp_path" in locals() and os.path.exists(temp_path):
                os.remove(temp_path)


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
    def get_icon_path(provider_name: str) -> str:
        """Get the path to a provider's icon, triggering download if necessary."""
        default_icon = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "resources", "openrouter.svg"
        )

        if not provider_name:
            return default_icon

        meta = IconManager._get_metadata(provider_name)
        now = time.time()
        should_download = False
        cached_path = None

        if meta:
            status = meta.get("status")
            timestamp = meta.get("timestamp", 0)

            if status == "failed":
                if now - timestamp < Config.ICONS_TTL:
                    return default_icon
                should_download = True

            elif status in ["success", "cached"]:
                filename = meta.get("filename")
                if filename:
                    path = os.path.join(Config.ICONS_DIR, filename)
                    if os.path.exists(path):
                        cached_path = path
                        if now - timestamp > Config.ICON_REFRESH_SECONDS:
                            should_download = True
                    else:
                        should_download = True
                else:
                    should_download = True
        else:
            safe_name = "".join(c for c in provider_name if c.isalnum() or c in "._-")
            for ext in Config.IMAGE_EXTENSIONS:
                path = os.path.join(Config.ICONS_DIR, f"{safe_name}{ext}")
                if os.path.exists(path):
                    cached_path = path
                    should_download = True  # Create metadata
                    break
            if not cached_path:
                should_download = True

        if should_download and provider_name not in IconManager._triggered:
            IconManager._triggered.add(provider_name)
            IconManager.trigger_batch_download(provider_name)

        return cached_path if cached_path else default_icon

    @staticmethod
    def trigger_batch_download(provider_name: str) -> None:
        """Trigger a background process to download an icon."""
        if not provider_name:
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        script = os.path.join(script_dir, "download_icon.py")
        cache_dir_arg = Config.CACHE_DIR

        cmd = [sys.executable, script, cache_dir_arg, provider_name]
        with subprocess.Popen(
            cmd,
            cwd=script_dir,
            stdout=subprocess.DEVNULL if not Config.DEBUG_MODE else None,
            stderr=subprocess.DEVNULL if not Config.DEBUG_MODE else None,
            close_fds=True,
        ) as _:
            pass


class APIClient:
    """Handles HTTP requests to the OpenRouter API."""
    @staticmethod
    def fetch(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Fetch JSON data from a URL."""
        if headers is None:
            headers = {}
        default_headers = {
            "User-Agent": "Alfred-OpenRouter-Workflow",
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
    def get_models() -> list[dict[str, Any]]:
        """Fetch list of available models from cache or API."""
        cached = CacheManager.read("models.json", Config.MODELS_TTL)
        if cached is not None:
            return cached

        data = APIClient.fetch(Config.MODELS_URL)
        models = data.get("data", [])
        CacheManager.write("models.json", models)
        return models

    @staticmethod
    def get_endpoints(model_id: str) -> list[dict[str, Any]]:
        """Fetch endpoints for a specific model."""
        os.makedirs(Config.ENDPOINTS_DIR, exist_ok=True)
        safe_name = model_id.replace("/", "_") + ".json"
        path = os.path.join(Config.ENDPOINTS_DIR, safe_name)

        # Check cache
        try:
            if os.path.exists(path):
                if Config.ENDPOINTS_TTL < 0 or time.time() - os.path.getmtime(path) < Config.ENDPOINTS_TTL:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

        url = Config.ENDPOINTS_URL.format(model_id=model_id)
        data = APIClient.fetch(url)
        endpoints = data.get("data", {}).get("endpoints", [])

        # Write cache
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(endpoints, f)
        except OSError:
            pass
        return endpoints


class Formatter:
    """Helper class for formatting model information."""
    MODALITY_MAP = {"text": "T", "image": "I", "video": "V", "audio": "A", "file": "F"}

    @staticmethod
    def format_price(per_token_str: Any) -> str:
        """Format price per token."""
        try:
            val = float(per_token_str) * 1_000_000
            if val == 0:
                return "Free"
            if val < 0.01:
                return f"${val:.4f}"
            return f"${val:.2f}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def format_context_length(value: Any) -> str:
        """Format context length (e.g. 128000 -> 128K)."""
        try:
            v = int(value)
            if v == 0:
                return "0"
            k = v / 1000
            return f"{int(k)}K" if k == int(k) else f"{k:.1f}K"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def get_p50(values: Any) -> float | None:
        """Extract p50 value from stats."""
        if not values:
            return None
        try:
            if isinstance(values, dict):
                return float(values.get("p50", 0))
            return float(values)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def abbreviate_modality(modality: str) -> str:
        """Convert a modality string (e.g., 'text->image') to a short code."""
        if not modality:
            return ""
        try:
            # Handle formats like "text+image->text"
            parts = modality.split("->")
            if len(parts) != 2:
                return modality

            inputs = parts[0].split("+")
            outputs = parts[1].split("+")

            m = Formatter.MODALITY_MAP
            abbr_inputs = "+".join(m.get(i.strip(), i.strip()) for i in inputs)
            abbr_outputs = "+".join(m.get(o.strip(), o.strip()) for o in outputs)

            return f"{abbr_inputs}→{abbr_outputs}"
        except Exception:
            return modality

    @staticmethod
    def get_capability_icons(model: dict[str, Any]) -> str:
        """Generate icon string for model capabilities."""
        icons = []
        architecture = model.get("architecture") or {}
        input_modalities = architecture.get("input_modalities", [])
        supported_parameters = model.get("supported_parameters", [])

        # Vision
        if "image" in input_modalities:
            icons.append("👁️")

        # Tools
        if "tools" in supported_parameters:
            icons.append("🛠️")

        # JSON / Structured Outputs
        if "response_format" in supported_parameters or "structured_outputs" in supported_parameters:
            icons.append("🎯")

        # Reasoning / Thinking
        model_id = model.get("id", "").lower()
        if "thinking" in model_id or "reasoning" in supported_parameters or "include_reasoning" in supported_parameters:
            icons.append("🧠")

        return "".join(icons)


def create_endpoint_item(endpoint: dict[str, Any]) -> AlfredItem:
    """Create an AlfredItem for a model endpoint."""
    provider = endpoint.get("provider_name", "Unknown")
    tag = endpoint.get("tag")
    quantization = endpoint.get("quantization")

    # Tag display logic
    tag_display = ""
    if tag and quantization and quantization != "unknown" and quantization not in tag:
        tag_display = f" {tag}/{quantization}"
    elif tag:
        tag_display = f" {tag}"
    elif quantization and quantization != "unknown":
        tag_display = f" {quantization}"

    tag_str = f"[{tag_display.strip()}]" if tag_display else ""
    title = f"- {provider} {tag_str}".strip()

    pricing = endpoint.get("pricing") or {}
    context_length = endpoint.get("context_length", 0)

    subtitle_parts = [
        f"Ctx: {Formatter.format_context_length(context_length)}",
        f"In: {Formatter.format_price(pricing.get('prompt'))}",
        f"Out: {Formatter.format_price(pricing.get('completion'))}",
    ]

    cache_read = pricing.get("input_cache_read")
    if cache_read is not None:
        try:
            if float(cache_read) > 0:
                subtitle_parts.append(f"CR: {Formatter.format_price(cache_read)}")
        except (TypeError, ValueError):
            pass

    latency = Formatter.get_p50(endpoint.get("latency_last_30m"))
    throughput = Formatter.get_p50(endpoint.get("throughput_last_30m"))

    if latency is not None:
        subtitle_parts.append(f"Lat: {latency/1000:.2f}s")
    if throughput is not None:
        subtitle_parts.append(f"Tps: {throughput:.0f}/s")

    subtitle = " | ".join(subtitle_parts)

    # Modifiers
    mods = {
        "alt": {
            "valid": True,
            "arg": tag.strip() if tag else "",
            "subtitle": "Copy provider tag",
        },
        "ctrl": {
            "valid": True,
            "arg": provider,
            "subtitle": "Copy provider name",
        },
    }

    # Provider icons? Maybe. For now simpler models logic.
    return AlfredItem(title=title, subtitle=subtitle, arg=f"{title}\n{subtitle}", mods=mods)


# Common provider slug to display name mappings
PROVIDER_SLUG_MAP = {"meta-llama": "Meta", "qwen": "Qwen"}


def get_provider_from_model(model: dict[str, Any]) -> str:
    """Extract and format the provider name from a model dictionary."""
    # Attempt to extract provider/manufacturer from name "Provider: Model"
    name = model.get("name", "")
    if ":" in name:
        return name.split(":", 1)[0].strip()

    # Fallback to slug first part
    mid = model.get("id", "")
    if "/" in mid:
        slug = mid.split("/", 1)[0]
        # Check mapping first
        if slug in PROVIDER_SLUG_MAP:
            return PROVIDER_SLUG_MAP[slug]
        if slug.lower() in PROVIDER_SLUG_MAP:
            return PROVIDER_SLUG_MAP[slug.lower()]
        # Capitalize for display
        return slug.title() if slug.islower() else slug

    return ""


def _score_model(model: dict[str, Any], query: str) -> int | None:
    """Return match score (lower=better) or None if no match."""
    model_id = model.get("id", "").lower()
    name = model.get("name", "").lower()

    if query in (model_id, name):
        return 0
    if model_id.startswith(query) or name.startswith(query):
        return 1
    if query in model_id or query in name:
        return 2
    return None


def _find_model_by_id(model_id: str) -> dict[str, Any] | None:
    """Find model in cached data by ID."""
    try:
        models = CacheManager.read("models.json", Config.MODELS_TTL)
        if models:
            for model in models:
                if model.get("id") == model_id:
                    return model
    except Exception:
        pass
    return None


def search_mode(query: str) -> None:
    """Search for models matching the query and output Alfred results."""
    try:
        models = APIClient.get_models()
    except Exception as e:
        output_error("Error connecting to OpenRouter", str(e))
        return

    search_query = query.lower().strip()
    if not search_query:
        results = models
    else:
        scored = [(s, m) for m in models if (s := _score_model(m, search_query)) is not None]
        scored.sort(key=lambda x: x[0])
        results = [m for _, m in scored]

    if not results:
        output_alfred_items(
            [
                AlfredItem(
                    title=f"No models found for '{query}'",
                    subtitle="Try a different search term",
                    arg="",
                )
            ]
        )
        return

    items = []

    for model in results:
        model_id = model.get("id", "")
        name = model.get("name", model_id)
        pricing = model.get("pricing") or {}
        context_length = model.get("context_length", 0)

        # New model tag (within configured days)
        created_time = model.get("created", 0)
        current_time = time.time()
        is_new = (current_time - created_time) < (Config.NEW_MODEL_DAYS * 24 * 3600)
        display_name = f"[New] {name}" if is_new else name

        # Capability icons
        cap_icons = Formatter.get_capability_icons(model)

        # Modality abbreviation
        modality = model.get("architecture", {}).get("modality", "")
        abbr_modality = Formatter.abbreviate_modality(modality)

        subtitle_parts = []
        if cap_icons:
            subtitle_parts.append(cap_icons)
        if abbr_modality:
            subtitle_parts.append(f"[{abbr_modality}]")

        subtitle_parts.extend([
            f"Ctx: {Formatter.format_context_length(context_length)}",
            f"In: {Formatter.format_price(pricing.get('prompt'))}/M",
            f"Out: {Formatter.format_price(pricing.get('completion'))}/M"
        ])

        subtitle = " | ".join(subtitle_parts)

        provider = get_provider_from_model(model)
        icon_path = IconManager.get_icon_path(provider)

        items.append(
            AlfredItem(
                title=display_name,
                subtitle=subtitle,
                arg=Config.MODEL_PAGE_URL.format(model_id=model_id),
                autocomplete=">" + model_id,
                icon=icon_path,
            )
        )

    output_alfred_items(items)


def detail_mode(model_id: str) -> None:
    """Show detailed information for a specific model."""
    model_info = _find_model_by_id(model_id)

    name = model_info.get("name", model_id) if model_info else model_id
    description = model_info.get("description", "") if model_info else ""
    hf_id = model_info.get("hugging_face_id") if model_info else None
    model_url = Config.MODEL_PAGE_URL.format(model_id=model_id)

    provider = get_provider_from_model(model_info) if model_info else ""
    icon_path = IconManager.get_icon_path(provider)

    items = []

    # Header
    items.append(
        AlfredItem(
            title=f"{name} ({model_id})",
            subtitle=description[:100] + ("..." if len(description) > 100 else ""),
            arg=model_url,
            icon=icon_path,
        )
    )

    if hf_id:
        items.append(
            AlfredItem(
                title=f"HuggingFace: {hf_id}",
                subtitle="Open HuggingFace page",
                arg=Config.HF_PAGE_URL.format(hf_id=hf_id),
                icon="resources/huggingface.svg",
            )
        )
        items.append(
            AlfredItem(
                title=f"ModelScope: {hf_id}",
                subtitle="Open ModelScope page",
                arg=Config.MODELSCOPE_URL.format(hf_id=hf_id),
                icon="resources/modelscope.svg",
            )
        )

    try:
        endpoints = APIClient.get_endpoints(model_id)
    except Exception as e:
        output_alfred_items(
            items
            + [
                AlfredItem(
                    title="Error fetching endpoints",
                    subtitle=str(e),
                    arg=model_url,
                    valid=False,
                )
            ]
        )
        return

    # Filter and sort endpoints
    active_endpoints = [ep for ep in endpoints if (ep.get("status") or 0) > -5]
    active_endpoints.sort(
        key=lambda x: (-(x.get("status") or 0), -(x.get("uptime_last_30m") or 0))
    )

    for endpoint in active_endpoints:
        items.append(create_endpoint_item(endpoint))

    if not active_endpoints:
        items.append(
            AlfredItem(
                title="No active providers",
                subtitle="This model may not have active providers",
                arg=model_url,
            )
        )

    output_alfred_items(items)


def clear_cache_mode() -> None:
    """Clear all cached data."""
    cleared = []

    # Clear models cache
    models_path = os.path.join(Config.CACHE_DIR, "models.json")
    if os.path.exists(models_path):
        os.remove(models_path)
        cleared.append("models")

    # Clear endpoints directory
    if os.path.isdir(Config.ENDPOINTS_DIR):
        shutil.rmtree(Config.ENDPOINTS_DIR)
        cleared.append("endpoints")

    # Clear icons directory and metadata
    if os.path.isdir(Config.ICONS_DIR):
        shutil.rmtree(Config.ICONS_DIR)
        cleared.append("icons")

    icons_meta = os.path.join(Config.CACHE_DIR, "icons.json")
    if os.path.exists(icons_meta):
        os.remove(icons_meta)

    if cleared:
        output_alfred_items([
            AlfredItem(
                title="Cache cleared",
                subtitle=f"Cleared: {', '.join(cleared)}",
                arg="cleared",
            )
        ])
    else:
        output_alfred_items([
            AlfredItem(
                title="Cache already empty",
                subtitle="No cached data to clear",
                arg="empty",
            )
        ])


def main() -> None:
    """Main entry point."""
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    query = query.strip()

    if query == "clear":
        clear_cache_mode()
    elif query.startswith(">"):
        model_id = query[1:].strip()
        if model_id:
            detail_mode(model_id)
        else:
            output_alfred_items(
                [
                    AlfredItem(
                        title="Type a model ID after >",
                        subtitle="e.g., >openai/gpt-4o",
                        arg="",
                        valid=False,
                    )
                ]
            )
    else:
        search_mode(query)


if __name__ == "__main__":
    main()
