"""Repository smoke tests."""

from __future__ import annotations

import main


def test_module_exposes_client() -> None:
    """The root module should expose the production client."""
    assert main.ClaudeNativeOAuthClient.__name__ == "ClaudeNativeOAuthClient"
