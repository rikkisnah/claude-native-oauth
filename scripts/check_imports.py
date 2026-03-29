"""Basic import smoke check for the repository."""

from __future__ import annotations

import importlib


def main() -> int:
    """Import the production module to catch obvious packaging issues."""
    importlib.import_module("main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
