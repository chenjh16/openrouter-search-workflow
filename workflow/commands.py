"""Main workflow commands."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from typing import Any

from .alfred import AlfredItem, output_alfred_items, output_error
from .api import APIClient
from .cache import CacheManager
from .config import Config
from .icons import IconManager
from .utils import Formatter, get_provider_from_model


def _format_tag(tag: str | None, quantization: str | None) -> str:
    """Format tag/quantization into a display string like '[tag/quant]' or ''."""
    parts = []
    if tag:
        parts.append(tag)
    if quantization and quantization != "unknown" and quantization not in (tag or ""):
        parts.append(quantization)
    return f"[{'/'.join(parts)}]" if parts else ""


def create_endpoint_item(endpoint: dict[str, Any]) -> AlfredItem:
    """Create an AlfredItem for a model endpoint."""
    provider = endpoint.get("provider_name", "Unknown")
    tag = endpoint.get("tag")
    model_id = endpoint.get("model_id")

    tag_str = _format_tag(tag, endpoint.get("quantization"))
    title = f"- {provider} {tag_str}".strip()

    pricing = endpoint.get("pricing") or {}

    subtitle_parts = [
        f"Ctx: {Formatter.format_context_length(endpoint.get('context_length', 0))}",
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
        subtitle_parts.append(f"Lat: {latency / 1000:.2f}s")
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
            "arg": f"CURL_PROVIDER:{model_id}|{tag or provider}",
            "subtitle": f"Copy curl test command for {provider}",
        },
    }

    return AlfredItem(title=title, subtitle=subtitle, arg=f"{title}\n{subtitle}", mods=mods)


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


def _build_model_item(model: dict[str, Any]) -> AlfredItem:
    """Build an AlfredItem for a model in search results."""
    model_id = model.get("id", "")
    name = model.get("name", model_id)
    pricing = model.get("pricing") or {}
    context_length = model.get("context_length", 0)

    # New model tag (within configured days)
    created_time = model.get("created", 0)
    is_new = (time.time() - created_time) < (Config.NEW_MODEL_DAYS * 24 * 3600)
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

    subtitle_parts.extend(
        [
            f"Ctx: {Formatter.format_context_length(context_length)}",
            f"In: {Formatter.format_price(pricing.get('prompt'))}/M",
            f"Out: {Formatter.format_price(pricing.get('completion'))}/M",
        ]
    )

    subtitle = " | ".join(subtitle_parts)

    provider = get_provider_from_model(model)
    icon_path = IconManager.get_icon_path(provider)

    return AlfredItem(
        title=display_name,
        subtitle=subtitle,
        arg=Config.MODEL_PAGE_URL.format(model_id=model_id),
        autocomplete=">" + model_id,
        icon=icon_path,
        mods={
            "alt": {
                "valid": True,
                "arg": f"COPY:{model_id}",
                "subtitle": f"Copy Model ID: {model_id}",
            },
            "ctrl": {
                "valid": True,
                "arg": f"CURL:{model_id}",
                "subtitle": "Copy curl test command",
            },
        },
    )


def _build_header_items(model_id: str, model_info: dict[str, Any] | None) -> list[AlfredItem]:
    """Build header items for model detail view (model info + HuggingFace + ModelScope links)."""
    name = model_info.get("name", model_id) if model_info else model_id
    description = model_info.get("description", "") if model_info else ""
    hf_id = model_info.get("hugging_face_id") if model_info else None
    model_url = Config.MODEL_PAGE_URL.format(model_id=model_id)

    provider = get_provider_from_model(model_info) if model_info else ""
    icon_path = IconManager.get_icon_path(provider)

    items = [
        AlfredItem(
            title=f"{name} ({model_id})",
            subtitle=description[:100] + ("..." if len(description) > 100 else ""),
            arg=model_url,
            icon=icon_path,
            mods={
                "alt": {
                    "valid": True,
                    "arg": f"COPY:{model_url}",
                    "subtitle": "Copy OpenRouter URL",
                },
                "ctrl": {
                    "valid": True,
                    "arg": f"CURL:{model_id}",
                    "subtitle": "Copy curl test command",
                },
            },
        )
    ]

    if hf_id:
        hf_url = Config.HF_PAGE_URL.format(hf_id=hf_id)
        items.append(
            AlfredItem(
                title=f"HuggingFace: {hf_id}",
                subtitle="Open HuggingFace page",
                arg=hf_url,
                icon="resources/huggingface.svg",
                mods={
                    "alt": {
                        "valid": True,
                        "arg": f"COPY:{hf_url}",
                        "subtitle": "Copy HuggingFace URL",
                    }
                },
            )
        )
        ms_url = Config.MODELSCOPE_URL.format(hf_id=hf_id)
        items.append(
            AlfredItem(
                title=f"ModelScope: {hf_id}",
                subtitle="Open ModelScope page",
                arg=ms_url,
                icon="resources/modelscope.svg",
                mods={
                    "alt": {
                        "valid": True,
                        "arg": f"COPY:{ms_url}",
                        "subtitle": "Copy ModelScope URL",
                    }
                },
            )
        )

    return items


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

    output_alfred_items([_build_model_item(model) for model in results])


def detail_mode(model_id: str) -> None:
    """Show detailed information for a specific model."""
    model_info = _find_model_by_id(model_id)
    model_url = Config.MODEL_PAGE_URL.format(model_id=model_id)

    items = _build_header_items(model_id, model_info)

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
    active_endpoints.sort(key=lambda x: (-(x.get("status") or 0), -(x.get("uptime_last_30m") or 0)))

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


def show_clearcache_menu() -> None:
    """Show options for clearing cache."""
    icon_path = os.path.join(Config.PROJECT_ROOT, "resources", "openrouter.svg")

    items = [
        AlfredItem(
            title="Clean Models",
            subtitle="Remove cached model list (models.json)",
            arg="models",
            icon=icon_path,
        ),
        AlfredItem(
            title="Clean Endpoints",
            subtitle="Remove cached endpoints (endpoints/)",
            arg="endpoints",
            icon=icon_path,
        ),
        AlfredItem(
            title="Clean Icons",
            subtitle="Remove cached provider icons (icons/)",
            arg="icons",
            icon=icon_path,
        ),
        AlfredItem(
            title="Clean All",
            subtitle="Remove all cached data",
            arg="all",
            icon=icon_path,
        ),
    ]
    output_alfred_items(items)


def _remove_path(path: str, label: str, cleared: list[str]) -> None:
    """Remove a file or directory, appending label to cleared list on success."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
        else:
            return
        cleared.append(label)
    except OSError as e:
        logging.error(f"Failed to remove {label}: {e}")


def execute_clear_cache(target: str) -> None:
    """Execute the cache clearing command."""
    cleared: list[str] = []

    if target in ["models", "all"]:
        _remove_path(os.path.join(Config.CACHE_DIR, "models.json"), "Models", cleared)

    if target in ["endpoints", "all"]:
        _remove_path(Config.ENDPOINTS_DIR, "Endpoints", cleared)

    if target in ["icons", "all"]:
        _remove_path(Config.ICONS_DIR, "Icons", cleared)
        _remove_path(os.path.join(Config.CACHE_DIR, "icons.json"), "Icons Metadata", cleared)

    if not cleared:
        print("No cache cleared (or empty)")
    else:
        print(f"Cleared: {', '.join(cleared)}")


def refresh_all() -> None:
    """Force refresh all cached data (models, icons, endpoints)."""
    # 1. Re-fetch models
    try:
        models = APIClient.get_models(force=True)
        print(f"Models updated: {len(models)} models.")
    except Exception as e:
        print(f"Failed to update models: {e}")
        return

    # 2. Re-fetch icons for all providers
    providers_seen: set[str] = set()
    for model in models:
        provider = get_provider_from_model(model)
        if provider and provider not in providers_seen:
            providers_seen.add(provider)
            IconManager.get_icon_path(provider)
    print(f"Icons triggered: {len(providers_seen)} providers.")

    # 3. Re-fetch only previously cached endpoints
    endpoint_count = 0
    if os.path.isdir(Config.ENDPOINTS_DIR):
        for filename in os.listdir(Config.ENDPOINTS_DIR):
            if filename.endswith(".json"):
                model_id = filename[:-5].replace("_", "/", 1)
                try:
                    APIClient.get_endpoints(model_id, force=True)
                    endpoint_count += 1
                except Exception:
                    pass
    print(f"Endpoints updated: {endpoint_count} models.")


def _copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard using pbcopy."""
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def _build_curl_command(model_id: str, provider: str | None = None) -> str:
    """Build a curl command for testing a model."""
    provider_block = ""
    if provider:
        provider_block = f"""
  "provider": {{
    "order": ["{provider}"],
    "allow_fallbacks": false
  }},"""

    return f"""curl {Config.CHAT_API_URL} \\
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{
  "model": "{model_id}",{provider_block}
  "messages": [
    {{"role": "user", "content": "Hello"}}
  ]
}}'"""


def execute_action(query: str) -> None:
    """Process an action from the Alfred Run Script output.

    Handles: COPY:, CURL:, CURL_PROVIDER:, URL opening, and default copy.
    Prints a description to stdout for notification passthrough.
    """
    if query.startswith("COPY:"):
        content = query[5:]
        _copy_to_clipboard(content)
        print(content)

    elif query.startswith("CURL:"):
        model_id = query[5:]
        _copy_to_clipboard(_build_curl_command(model_id))
        print(f"curl command for {model_id}")

    elif query.startswith("CURL_PROVIDER:"):
        # Format: CURL_PROVIDER:{model_id}|{provider_name}
        args = query[14:]
        model_id, _, provider_name = args.partition("|")
        _copy_to_clipboard(_build_curl_command(model_id, provider_name))
        print(f"curl command for {model_id} ({provider_name})")

    elif query.startswith("http://") or query.startswith("https://"):
        subprocess.Popen(["open", query])  # pylint: disable=consider-using-with

    else:
        _copy_to_clipboard(query)
        print(query)
