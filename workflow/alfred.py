"""Alfred workflow item generation and output."""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any


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
    output_alfred_items([AlfredItem(title=title, subtitle=subtitle, arg=arg, valid=False)])
