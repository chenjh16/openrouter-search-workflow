#!/usr/bin/env python3
"""Script to download provider icons for Alfred OpenRouter Workflow."""

from __future__ import annotations

import sys
import os
import json
import time
import fcntl
import urllib.request
import urllib.error
import ssl
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


# Configure logging - DEBUG only when explicitly enabled
DEBUG_MODE = os.environ.get("ALFRED_WORKFLOW_DEBUG") == "1"
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.ERROR
)

DOMAIN_MAP = {
    "AI21": "https://ai21.ai",
    "AionLabs": "https://aionlabs.ai",
    "Alibaba": "https://alibaba.com",
    "AllenAI": "https://allen.ai",
    "Amazon": "https://amazon.ai",
    "Anthropic": "https://anthropic.com",
    "Arcee AI": "https://arcee.ai",
    "Baidu": "https://baidu.com",
    "ByteDance Seed": "https://seed.bytedance.com/",
    "Cohere": "https://cohere.com",
    "Deep Cogito": "https://deepcogito.ai",
    "DeepSeek": "https://deepseek.com",
    "EssentialAI": "https://essential.ai",
    "Google": "https://google.com",
    "Gryphe": "https://gryphe.com",
    "IBM": "https://ibm.com",
    "Inception": "https://www.inceptionlabs.ai/",
    "Inflection": "https://inflection.com",
    "Kwaipilot": "https://kwaipilot.ai",
    "LiquidAI": "https://liquid.ai",
    "Mancer": "https://mancer.com",
    "Meituan": "https://meituan.com",
    "Meta": "https://meta.ai",
    "Microsoft": "https://microsoft.com",
    "MiniMax": "https://minimaxi.com/",
    "Mistral": "https://mistral.ai",
    "Mistralai": "https://mistral.ai",
    "MoonshotAI": "https://moonshot.ai",
    "Morph": "https://morph.ai",
    "NeverSleep": "https://neversleep.io",
    "Neversleep": "https://neversleep.io",
    "Nex AGI": "https://nexagi.ai",
    "Nous": "https://nous.ai",
    "NousResearch": "https://nousresearch.com",
    "NVIDIA": "https://nvidia.ai",
    "OpenAI": "https://openai.com",
    "OpenGVLab": "https://opengvlab.com",
    "Openrouter": "https://openrouter.ai",
    "Perplexity": "https://perplexity.ai",
    "Prime Intellect": "https://primeintellect.ai",
    "Qwen": "https://qwen.ai",
    "Relace": "https://relace.ai",
    "StepFun": "https://stepfun.ai",
    "Switchpoint": "https://switchpoint.ai",
    "Tencent": "https://tencent.com",
    "TNG": "https://tng.ai",
    "Upstage": "https://upstage.ai",
    "Venice": "https://venice.ai",
    "Writer": "https://writer.ai",
    "xAI": "https://x.ai",
    "Xiaomi": "https://xiaomi.com",
    "Z.AI": "https://z.ai",
}

OPENROUTER_MAP = {
    "Anthropic": "Anthropic.svg",
    "Cohere": "Cohere.png",
    "DeepSeek": "DeepSeek.png",
    "Kwaipilot": "Kwaipilot.png",
    "Meta": "Meta.png",
    "Microsoft": "Microsoft.svg",
    "Mistral": "Mistral.png",
    "OpenAI": "OpenAI.svg",
    "Perplexity": "Perplexity.svg",
    "Qwen": "Qwen.png",
    "TheDrummer": "TheDrummer.png",
}

ICON_BASE_URL = "https://openrouter.ai/images/icons/{provider}.svg"
FAVICON_BASE_URL = (
    "https://t0.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
    "&fallback_opts=TYPE,SIZE,URL&url={domain}&size=256"
)
METADATA_FILE = "icons.json"

# Module-level constants for download logic
SUPPORTED_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg", ".webp")
PRIORITY_MAP = {
    "openrouter-mapped": 0,
    "mapped": 1,
    "openrouter": 2,
    "heuristic": 3,
}
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def load_metadata(cache_dir: str) -> dict[str, Any]:
    """Load metadata from the cache directory."""
    path = os.path.join(cache_dir, METADATA_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_metadata(cache_dir: str, metadata: dict[str, Any]) -> None:
    """Save metadata to the cache directory."""
    path = os.path.join(cache_dir, METADATA_FILE)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)
        os.replace(temp_path, path)
    except Exception as e:
        logging.error(f"Failed to save metadata: {e}")


def update_metadata_atomic(cache_dir: str, new_entries: dict[str, Any]) -> None:
    """Update metadata atomically using file locking."""
    # Use a separate lock file
    lock_path = os.path.join(cache_dir, METADATA_FILE + ".lock")

    # Ensure lock file exists
    if not os.path.exists(lock_path):
        try:
            with open(lock_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    try:
        # Open lock file to acquire lock
        with open(lock_path, "w", encoding="utf-8") as lockfile:
            # Acquire exclusive lock (blocking)
            fcntl.flock(lockfile, fcntl.LOCK_EX)
            try:
                # Critical section: Read -> Update -> Write
                current = load_metadata(cache_dir)

                for provider, new_data in new_entries.items():
                    # Smart merge logic
                    status = new_data.get("status")
                    if status == "failed":
                        # If existing entry was success, keep it but update timestamp
                        old_data = current.get(provider)
                        if old_data and old_data.get("status") == "success":
                            old_data["timestamp"] = new_data["timestamp"]
                            current[provider] = old_data
                        else:
                            current[provider] = new_data
                    elif status == "cached":
                        # Preserve URL from old_data if present
                        old_data = current.get(provider)
                        if old_data and old_data.get("url"):
                            new_data["url"] = old_data["url"]
                        current[provider] = new_data
                    else:
                        current[provider] = new_data

                save_metadata(cache_dir, current)
            finally:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
    except Exception as e:
        logging.error(f"Failed to update metadata atomically: {e}")


def ensure_dir(directory: str) -> None:
    """Ensure that a directory exists."""
    os.makedirs(directory, exist_ok=True)


def validate_image_content(data: bytes, filename: str) -> bool:
    """Validate that the downloaded content is an image."""
    if not data:
        return False

    # Check for HTML signature first (e.g. 404 pages)
    head = data[:1000].lower()
    if b"<!doctype html" in head or b"<html" in head:
        return False

    lower_name = filename.lower()
    if lower_name.endswith(".svg"):
        try:
            content = data.decode("utf-8", errors="ignore").strip().lower()
            return "<svg" in content and "</svg>" in content
        except Exception:
            return False

    elif lower_name.endswith(".png"):
        return data.startswith(b"\x89PNG\r\n\x1a\n")

    return True


def _try_download(url: str, path: str, context: ssl.SSLContext | None) -> bool:
    """Attempt to download a file from a URL to a path."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Alfred-OpenRouter-Workflow"}
        )
        with urllib.request.urlopen(req, context=context, timeout=10) as resp:
            data = resp.read()
            if validate_image_content(data, path):
                with open(path, "wb") as f:
                    f.write(data)
                return True
    except urllib.error.HTTPError:
        # Expected for 404s
        return False
    except Exception as e:
        # Logging to stderr might be useful if debugging manual run
        logging.debug(f"Failed to download {url}: {e}")
        return False

    return False


def get_candidate_domains(provider_name: str) -> list[tuple[str, str]]:
    """
    Heuristics to find the provider's official domain:
    1. Check explicit map.
    2. Normalize: lowercase, remove spaces and dots.
    3. Suffix removal: 'ai', 'lab', 'labs', 'research', 'tech'.
    4. TLDs: .ai (primary), .com, .io.
    Returns: List of (url, category) tuples
    """
    # Check explicit map first
    if provider_name in DOMAIN_MAP:
        return [(DOMAIN_MAP[provider_name], "mapped")]

    candidates = []
    # Normalize: lowercase, remove spaces, remove dots (e.g. Z.AI -> zai)
    clean_name = provider_name.lower().replace(" ", "").replace(".", "")

    # Common AI-related suffixes to try stripping
    suffixes = ["ai", "lab", "labs", "research", "tech"]
    roots = {clean_name}
    for s in suffixes:
        if clean_name.endswith(s) and len(clean_name) > len(s):
            roots.add(clean_name[:-len(s)])

    # TLD priority: .ai is most likely for this context, followed by .com, .io
    tlds = ["ai", "com", "io"]

    # Generate candidates: roots x tlds
    for root in sorted(list(roots), key=len, reverse=True):
        for tld in tlds:
            candidates.append((f"https://{root}.{tld}", "heuristic"))

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for url, cat in candidates:
        if url not in seen:
            seen.add(url)
            result.append((url, cat))
    return result


def download_provider_icon(
    provider_name: str, cache_dir: str
) -> dict[str, Any] | None:
    """Download an icon for a specific provider."""
    safe_name = "".join(c for c in provider_name if c.isalnum() or c in "._-")
    icons_dir = os.path.join(cache_dir, "icons")
    ensure_dir(icons_dir)

    # Pre-calculate all candidates
    candidates = []

    # 1. OpenRouter Icons
    if provider_name in OPENROUTER_MAP:
        mapped_filename = OPENROUTER_MAP[provider_name]
        url = ICON_BASE_URL.rsplit("/", 1)[0] + "/" + mapped_filename
        ext = os.path.splitext(mapped_filename)[1] or ".svg"
        filename = f"{safe_name}{ext}"
        path = os.path.join(icons_dir, filename)
        candidates.append({
            "url": url,
            "filename": filename,
            "path": path,
            "category": "openrouter-mapped"
        })
    else:
        for ext in [".svg", ".png", ".jpg", ".jpeg", ".webp"]:
            url = ICON_BASE_URL.format(provider=provider_name.replace(" ", "")).replace(".svg", ext)
            filename = f"{safe_name}{ext}"
            path = os.path.join(icons_dir, filename)
            candidates.append({
                "url": url,
                "filename": filename,
                "path": path,
                "category": "openrouter"
            })

    # 2. Google Favicon as fallback
    favicon_filename = f"{safe_name}.png"
    favicon_path = os.path.join(icons_dir, favicon_filename)
    for domain, category in get_candidate_domains(provider_name):
        favicon_url = FAVICON_BASE_URL.format(domain=domain)
        candidates.append({
            "url": favicon_url,
            "filename": favicon_filename,
            "path": favicon_path,
            "category": category
        })

    # Deduplicate and sort candidates
    # Priority: openrouter-mapped > mapped > openrouter > heuristic
    seen_urls = set()
    unique_candidates = []
    for c in candidates:
        if c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            unique_candidates.append(c)

    candidates = sorted(
        unique_candidates,
        key=lambda x: PRIORITY_MAP.get(x["category"], 99)
    )

    # Check cache first
    for candidate in candidates:
        if os.path.exists(candidate["path"]):
            return {
                "provider": provider_name,
                "filename": candidate["filename"],
                "url": candidate["url"],
                "timestamp": int(os.path.getmtime(candidate["path"])),
                "status": "cached",
            }

    # Parallel download
    # We use a large enough pool to start all attempts at once
    max_workers = min(4, len(candidates))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_candidate = {
            executor.submit(_try_download, c["url"], c["path"], SSL_CONTEXT): c
            for c in candidates
        }

        # return the first one that succeeds
        for future in as_completed(future_to_candidate):
            if future.result():
                candidate = future_to_candidate[future]
                if candidate["category"] == "heuristic":
                    logging.info(f"Heuristic URL success for {provider_name}: {candidate['url']}")
                elif candidate["category"] == "openrouter":
                    logging.info(f"OpenRouter icon success for {provider_name}: {candidate['url']}")

                # Shutdown the executor without waiting for other threads to finish
                # to return to the caller as soon as possible.
                executor.shutdown(wait=False)

                return {
                    "provider": provider_name,
                    "filename": candidate["filename"],
                    "url": candidate["url"],
                    "timestamp": int(time.time()),
                    "status": "success",
                }

    return {
        "provider": provider_name,
        "timestamp": int(time.time()),
        "status": "failed",
    }


def main() -> None:
    """Main entry point for the script."""
    if len(sys.argv) < 3:
        return

    cache_dir = sys.argv[1]
    providers = sys.argv[2:]
    new_results: dict[str, Any] = {}

    if len(providers) < 2:
        # Single provider: process sequentially to avoid overhead
        for provider in providers:
            try:
                result = download_provider_icon(provider, cache_dir)
                if result:
                    new_results[provider] = result
            except Exception as e:
                logging.error(f"Error downloading icon for {provider}: {e}")
    else:
        # Multiple providers: use ThreadPoolExecutor for concurrent I/O
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            futures = {
                executor.submit(download_provider_icon, p, cache_dir): p for p in providers
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        p = result.get("provider")
                        if p:
                            new_results[p] = result
                except Exception as e:
                    logging.error(f"Error downloading icon: {e}")

    if new_results:
        update_metadata_atomic(cache_dir, new_results)


if __name__ == "__main__":
    main()
