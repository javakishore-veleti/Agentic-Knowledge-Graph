"""Two-tier cache service: Redis shared, in-memory mirror behind a feature toggle.

Read order is L1 then L2; a write goes to both. Both tiers apply the *same declared*
strategy, so a value's lifetime does not depend on which tier answered.

The honest limit: Redis may evict under its own memory pressure, which this process cannot
observe, so L1 can briefly hold a key Redis has dropped. L1's TTL is therefore capped at
the Redis TTL, `stale_l1_reads` counts the cases detected, and ADR-011 records the
trade-off rather than leaving it to be discovered.
"""

from __future__ import annotations

from typing import Any

from ..dtos.cache_dtos import CacheEntry, CacheStats, CacheStrategyName
from .cache_key import build_key
from .i_app_cache_service import IAppCacheService, ICacheStore


class AppCacheServiceImpl(IAppCacheService):
    def __init__(
        self,
        shared_store: ICacheStore,
        local_store: ICacheStore | None,
        *,
        mirror_in_memory: bool,
        default_strategy: CacheStrategyName = CacheStrategyName.TTL,
        default_ttl_seconds: int = 300,
    ) -> None:
        self._shared = shared_store
        self._local = local_store
        self._mirror = mirror_in_memory and local_store is not None
        self._default_strategy = default_strategy
        self._default_ttl = default_ttl_seconds
        self._stale_l1 = 0

    def get(self, cache_name: str, tenant_id: str, key_parts: dict[str, Any]) -> Any | None:
        key = build_key(cache_name, tenant_id, key_parts)

        if self._mirror and self._local is not None:
            local = self._local.get(cache_name, key)
            if local is not None:
                # Detect the one case the mirror cannot prevent: L1 holding what Redis
                # has already evicted. Counted, not hidden.
                if self._shared.available() and self._shared.get(cache_name, key) is None:
                    self._stale_l1 += 1
                    self._local.evict(cache_name, key)
                else:
                    return local.value

        shared = self._shared.get(cache_name, key)
        if shared is None:
            return None
        if self._mirror and self._local is not None:
            self._local.put(shared)
        return shared.value

    def put(
        self,
        cache_name: str,
        tenant_id: str,
        key_parts: dict[str, Any],
        value: Any,
        *,
        strategy: CacheStrategyName | None = None,
        ttl_seconds: int | None = None,
        category: str | None = None,
    ) -> None:
        entry = CacheEntry(
            cache_strategy=strategy or self._default_strategy,
            cache_name=cache_name,
            cache_key=build_key(cache_name, tenant_id, key_parts),
            value=value,
            category=category,
            ttl_seconds=ttl_seconds or self._default_ttl,
        )
        self._shared.put(entry)
        if self._mirror and self._local is not None:
            self._local.put(entry)

    def evict(self, cache_name: str, tenant_id: str, key_parts: dict[str, Any]) -> None:
        key = build_key(cache_name, tenant_id, key_parts)
        self._shared.evict(cache_name, key)
        if self._local is not None:
            # Evict locally even when mirroring is off: a toggle flipped at runtime must
            # not leave a stale local copy behind.
            self._local.evict(cache_name, key)

    def evict_category(self, cache_name: str, tenant_id: str, category: str) -> int:
        scoped = f"{tenant_id}:{category}"
        removed = self._shared.evict_category(cache_name, scoped)
        if self._local is not None:
            removed += self._local.evict_category(cache_name, scoped)
        return removed

    def evict_all(self, cache_name: str, tenant_id: str) -> int:
        """Every entry of one cache for one tenant, filtered and unfiltered alike."""
        prefix = f"{cache_name}:{tenant_id}:"
        removed = self._shared.evict_prefix(cache_name, prefix)
        if self._local is not None:
            removed += self._local.evict_prefix(cache_name, prefix)
        return removed

    def stats(self) -> list[CacheStats]:
        out = list(self._shared.stats())
        if self._local is not None:
            out.extend(self._local.stats())
        if self._stale_l1:
            for s in out:
                if s.tier == "memory":
                    s.stale_l1_reads = self._stale_l1
        return out
