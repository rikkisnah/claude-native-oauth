"""Shared pytest fixtures for claude-native-oauth."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def credentials_path(tmp_path: Path) -> Path:
    """Provide a temporary Claude credentials file path."""
    return tmp_path / ".credentials.json"
