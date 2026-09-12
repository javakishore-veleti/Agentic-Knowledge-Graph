"""Cache key construction.

The tenant is part of every key and the builder will not produce one without it. A key of
`mios:state=live` would serve one tenant's rows to another -- a data leak wearing a
performance optimisation's clothes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_key(cache_name: str, tenant_id: str, key_parts: dict[str, Any]) -> str:
    if not tenant_id:
        raise ValueError(
            "tenant_id is required in every cache key: an untenanted key serves one "
            "tenant's data to another"
        )
    if not cache_name:
        raise ValueError("cache_name is required")

    # Sorted so {a:1, b:2} and {b:2, a:1} are one key rather than two.
    canonical = json.dumps(key_parts, sort_keys=True, separators=(",", ":"), default=str)
    if len(canonical) <= 200:
        return f"{cache_name}:{tenant_id}:{canonical}"
    # Long filter sets are hashed to stay inside key length limits, with the prefix kept
    # readable so a key is still recognisable in redis-cli.
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    return f"{cache_name}:{tenant_id}:h:{digest}"


def namespace(cache_name: str, tenant_id: str) -> str:
    return f"{cache_name}:{tenant_id}:"
