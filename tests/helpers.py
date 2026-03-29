"""Test helpers for synthetic SSE payloads."""

from __future__ import annotations

import json


def sse_data(payload: dict[str, object]) -> bytes:
    """Encode a single SSE data line."""
    return f"data: {json.dumps(payload)}".encode("utf-8")
