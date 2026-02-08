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
logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.ERROR)

DOMAIN_MAP = {
    "ai21": "https://ai21.ai",
    "aionlabs": "https://aionlabs.ai",
    "alibaba": "https://alibaba.com",
    "allenai": "https://allen.ai",
    "amazon": "https://amazon.ai",
    "anthropic": "https://anthropic.com",
    "arcee ai": "https://arcee.ai",
    "baidu": "https://baidu.com",
    "bytedance seed": "https://seed.bytedance.com/",
    "cohere": "https://cohere.com",
    "deep cogito": "https://deepcogito.ai",
    "deepseek": "https://deepseek.com",
    "essentialai": "https://essential.ai",
    "google": "https://google.com",
    "gryphe": "https://gryphe.com",
    "ibm": "https://ibm.com",
    "inception": "https://www.inceptionlabs.ai/",
    "inflection": "https://inflection.com",
    "kwaipilot": "https://kwaipilot.ai",
    "liquidai": "https://liquid.ai",
    "mancer": "https://mancer.com",
    "meituan": "https://meituan.com",
    "meta": "https://meta.ai",
    "microsoft": "https://microsoft.com",
    "minimax": "https://minimaxi.com/",
    "mistral": "https://mistral.ai",
    "mistralai": "https://mistral.ai",
    "moonshotai": "https://moonshot.ai",
    "morph": "https://morph.ai",
    "neversleep": "https://neversleep.io",
    "nex agi": "https://nexagi.ai",
    "nous": "https://nous.ai",
    "nousresearch": "https://nousresearch.com",
    "nvidia": "https://nvidia.ai",
    "openai": "https://openai.com",
    "opengvlab": "https://opengvlab.com",
    "openrouter": "https://openrouter.ai",
    "perplexity": "https://perplexity.ai",
    "prime intellect": "https://primeintellect.ai",
    "qwen": "https://qwen.ai",
    "relace": "https://relace.ai",
    "stepfun": "https://stepfun.ai",
    "switchpoint": "https://switchpoint.ai",
    "tencent": "https://tencent.com",
    "tng": "https://tng.ai",
    "upstage": "https://upstage.ai",
    "venice": "https://venice.ai",
    "writer": "https://writer.ai",
    "xai": "https://x.ai",
    "xiaomi": "https://xiaomi.com",
    "z.ai": "https://z.ai",
}

OPENROUTER_MAP = {
    "anthropic": "Anthropic.svg",
    "cohere": "Cohere.png",
    "deepseek": "DeepSeek.png",
    "kwaipilot": "Kwaipilot.png",
    "meta": "Meta.png",
    "microsoft": "Microsoft.svg",
    "mistral": "Mistral.png",
    "openai": "OpenAI.svg",
    "perplexity": "Perplexity.svg",
    "qwen": "Qwen.png",
    "thedrummer": "TheDrummer.png",
}

ICON_BASE_URL = "https://openrouter.ai/images/icons/{filename}"
FAVICON_BASE_URL = (
    "https://t0.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url={domain}&size=256"
)
METADATA_FILE = "icons.json"

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def _sanitize_name(name: str) -> str:
    """Sanitize a provider name for use as a filename."""
    return "".join(c for c in name if c.isalnum() or c in "._-")


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
    lock_path = os.path.join(cache_dir, METADATA_FILE + ".lock")

    try:
        # "a" mode creates atomically if missing, avoids TOCTOU race
        with open(lock_path, "a", encoding="utf-8") as lockfile:
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

    # Binary format magic byte validation
    signatures = {".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}
    for ext, sig in signatures.items():
        if lower_name.endswith(ext):
            return data.startswith(sig)

    return True


def _try_download(url: str, path: str, context: ssl.SSLContext | None) -> bool:
    """Attempt to download a file from a URL to a path."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Alfred-OpenRouter-Workflow"})
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


def get_candidate_domains(provider_name: str) -> list[str]:
    """
    Heuristics to find the provider's official domain:
    1. Normalize: lowercase, remove spaces and dots.
    2. Suffix removal: 'ai', 'lab', 'labs', 'research', 'tech'.
    3. TLDs: .ai (primary), .com, .io.
    Returns: List of candidate domain URLs
    """
    candidates = []
    # Normalize: lowercase, remove spaces and dots
    clean_name = provider_name.lower().replace(" ", "").replace(".", "")

    # Common AI-related suffixes to try stripping
    suffixes = ["ai", "lab", "labs", "research", "tech"]
    roots = {clean_name}
    for s in suffixes:
        if clean_name.endswith(s) and len(clean_name) > len(s):
            roots.add(clean_name[: -len(s)])

    # TLD priority: .ai is most likely for this context, followed by .com, .io
    tlds = ["ai", "com", "io"]

    # Generate candidates: roots x tlds
    for root in sorted(list(roots), key=len, reverse=True):
        for tld in tlds:
            candidates.append(f"https://{root}.{tld}")

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _candidate(url: str, filename: str, icons_dir: str, category: str) -> dict[str, str]:
    """Build a single candidate dict."""
    return {"url": url, "filename": filename, "path": os.path.join(icons_dir, filename), "category": category}


def _build_candidates(provider_name: str, icons_dir: str) -> list[dict[str, str]]:
    """Build prioritized list of icon download candidates."""
    safe_name = _sanitize_name(provider_name)
    key = provider_name.lower()
    candidates: list[dict[str, str]] = []

    # 1. OpenRouter mapped icons (highest priority)
    if key in OPENROUTER_MAP:
        mapped = OPENROUTER_MAP[key]
        ext = os.path.splitext(mapped)[1] or ".svg"
        candidates.append(
            _candidate(ICON_BASE_URL.format(filename=mapped), f"{safe_name}{ext}", icons_dir, "openrouter-mapped")
        )

    # 2. Domain map → favicon
    if key in DOMAIN_MAP:
        candidates.append(
            _candidate(FAVICON_BASE_URL.format(domain=DOMAIN_MAP[key]), f"{safe_name}.png", icons_dir, "domain-mapped")
        )

    # 3. OpenRouter heuristic filenames
    clean = provider_name.replace(" ", "")
    for ext in [".svg", ".png", ".jpg", ".jpeg"]:
        candidates.append(
            _candidate(
                ICON_BASE_URL.format(filename=f"{clean}{ext}"), f"{safe_name}{ext}", icons_dir, "openrouter-heuristic"
            )
        )

    # 4. Domain heuristics
    for domain in get_candidate_domains(provider_name):
        candidates.append(
            _candidate(FAVICON_BASE_URL.format(domain=domain), f"{safe_name}.png", icons_dir, "domain-heuristic")
        )

    return candidates


def _deduplicate(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deduplicate candidates by URL, preserving priority order."""
    seen: set[str] = set()
    result = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            result.append(c)
    return result


def download_provider_icon(provider_name: str, cache_dir: str) -> dict[str, Any] | None:
    """Download an icon for a specific provider."""
    icons_dir = os.path.join(cache_dir, "icons")
    ensure_dir(icons_dir)

    candidates = _deduplicate(_build_candidates(provider_name, icons_dir))

    # Sequential download
    logging.debug(
        "Downloading icon for %s:\n%s",
        provider_name,
        "\n".join(c["url"] for c in candidates),
    )
    for candidate in candidates:
        if _try_download(candidate["url"], candidate["path"], SSL_CONTEXT):
            if candidate["category"] in ("domain-heuristic", "openrouter-heuristic"):
                logging.info(f"{candidate['category'].title()} URL success for {provider_name}: {candidate['url']}")

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
            futures = {executor.submit(download_provider_icon, p, cache_dir): p for p in providers}
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
