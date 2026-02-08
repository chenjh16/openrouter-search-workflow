"""Configuration module for the workflow."""

from __future__ import annotations

import os


class Config:
    """Configuration constants for the workflow."""

    # API
    USER_AGENT = "Alfred-OpenRouter-Workflow"
    MODELS_URL = "https://openrouter.ai/api/v1/models"
    ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model_id}/endpoints"
    CHAT_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL_PAGE_URL = "https://openrouter.ai/models/{model_id}"
    HF_PAGE_URL = "https://huggingface.co/{hf_id}"
    MODELSCOPE_URL = "https://modelscope.cn/models/{hf_id}"

    # Cache TTL (in seconds)
    MODELS_TTL = int(os.environ.get("MODELS_TTL") or 1440) * 60
    ENDPOINTS_TTL = int(os.environ.get("ENDPOINTS_TTL") or 30) * 60
    ICONS_TTL = int(os.environ.get("ICONS_TTL") or 43200) * 60

    # Display constants
    NEW_MODEL_DAYS = 14
    ICON_REFRESH_SECONDS = 180 * 24 * 60 * 60  # 180 days
    IMAGE_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg")

    # Paths
    DEBUG_MODE = os.environ.get("ALFRED_WORKFLOW_DEBUG") == "1"
    # Project root directory (assuming this file is in workflow/ subdirectory)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DEBUG_CACHE_DIR = os.path.join(PROJECT_ROOT, ".temp", "alfred-openrouter")
    CACHE_DIR = os.environ.get("alfred_workflow_cache") or DEBUG_CACHE_DIR
    ICONS_DIR = os.path.join(CACHE_DIR, "icons")
    ENDPOINTS_DIR = os.path.join(CACHE_DIR, "endpoints")
    API_KEY = os.environ.get("OPENROUTER_API_KEY") or ""
