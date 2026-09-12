"""Opaque cursor paging. Offsets shift under concurrent inserts and silently skip rows."""

from __future__ import annotations

import base64
import json
from typing import Any

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        pad = "=" * (-len(cursor) % 4)
        return json.loads(base64.urlsafe_b64decode(cursor + pad))
    except Exception:
        # Not silently treated as "start over": that would re-serve the whole table and
        # look like success.
        raise ValueError("cursor is not a valid pagination token") from None


def clamp_limit(limit: int | None) -> int:
    return DEFAULT_LIMIT if limit is None else max(1, min(limit, MAX_LIMIT))
