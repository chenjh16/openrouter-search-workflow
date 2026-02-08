"""Utility (formatter) module."""

from __future__ import annotations

from typing import Any


def sanitize_name(name: str) -> str:
    """Sanitize a provider name for use as a filename (alphanumeric, dots, underscores, hyphens)."""
    return "".join(c for c in name if c.isalnum() or c in "._-")


# Common provider slug to display name mappings
PROVIDER_SLUG_MAP = {"meta-llama": "Meta", "qwen": "Qwen"}


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
        # Check mapping
        slug_lower = slug.lower()
        if slug_lower in PROVIDER_SLUG_MAP:
            return PROVIDER_SLUG_MAP[slug_lower]
        # Capitalize for display
        return slug.title() if slug.islower() else slug

    return ""
