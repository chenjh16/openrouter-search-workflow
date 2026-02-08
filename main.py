#!/usr/bin/env python3
"""Alfred Script Filter for searching OpenRouter AI models."""

import logging
import os
import sys

# Add the current directory to sys.path to ensure workflow package is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# pylint: disable=wrong-import-position
from workflow.commands import (
    detail_mode,
    execute_action,
    execute_clear_cache,
    refresh_all,
    search_mode,
    show_clearcache_menu,
)
from workflow.config import Config


def main():
    """Main entry point."""
    # Configure logging - DEBUG only in debug mode to avoid stderr noise in Alfred
    logging.basicConfig(level=logging.DEBUG if Config.DEBUG_MODE else logging.ERROR)

    query = sys.argv[1] if len(sys.argv) > 1 else ""

    if query == "clear":
        show_clearcache_menu()
        return

    if query == "--refresh":
        refresh_all()
        return

    if query.startswith("--clear"):
        # Format: --clear {target}
        parts = query.split(maxsplit=1)
        target = parts[1] if len(parts) > 1 else "all"
        execute_clear_cache(target)
        return

    if query.startswith("--action"):
        parts = query.split(maxsplit=1)
        action_arg = parts[1] if len(parts) > 1 else ""
        execute_action(action_arg)
        return

    if query.startswith(">"):
        detail_mode(query[1:])
        return

    search_mode(query)


if __name__ == "__main__":
    main()
