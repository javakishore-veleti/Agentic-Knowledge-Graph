"""Opaque cursor helpers.

Offset pagination shifts rows under concurrent inserts, so a client paging a growing
table silently skips records. The cursor encodes the sort key of the last row seen.
"""

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
        # A malformed cursor is the client's problem to see, not something to silently
        # treat as "start from the beginning" -- that would re-serve the whole table.
        raise ValueError("cursor is not a valid pagination token") from None


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))
