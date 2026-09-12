"""Eviction strategies, shared by both tiers.

Both the Redis store and the in-memory mirror apply the *same* declared strategy, so a
value's lifetime does not depend on which tier answered. The one thing the mirror cannot
replicate is Redis evicting under its own memory pressure (`maxmemory-policy`), which no
in-process cache can observe -- see ADR-011.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict

from ..dtos.cache_dtos import CacheEntry, CacheStrategyName


class ICacheEvictionStrategy(ABC):
    """Decides what leaves a cache, and when. Stateless: the entries are passed in."""

    @property
    @abstractmethod
    def name(self) -> CacheStrategyName: ...

    @abstractmethod
    def ttl_for(self, entry: CacheEntry) -> int | None:
        """Seconds to live in Redis, or None for no expiry."""

    @abstractmethod
    def evict(self, entries: OrderedDict[str, CacheEntry], capacity: int) -> list[str]:
        """Keys to remove so the cache fits. Called after an insert."""


class TtlStrategy(ICacheEvictionStrategy):
    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl = ttl_seconds

    @property
    def name(self) -> CacheStrategyName:
        return CacheStrategyName.TTL

    def ttl_for(self, entry: CacheEntry) -> int | None:
        return entry.ttl_seconds or self._ttl

    def evict(self, entries: OrderedDict[str, CacheEntry], capacity: int) -> list[str]:
        # Age is the only criterion; expired entries go regardless of capacity.
        return [k for k, e in entries.items() if e.is_expired()]


class LruCountStrategy(ICacheEvictionStrategy):
    """At most `capacity` entries; the least recently *read* leaves first."""

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = ttl_seconds

    @property
    def name(self) -> CacheStrategyName:
        return CacheStrategyName.LRU_COUNT

    def ttl_for(self, entry: CacheEntry) -> int | None:
        return entry.ttl_seconds or self._ttl

    def evict(self, entries: OrderedDict[str, CacheEntry], capacity: int) -> list[str]:
        doomed = [k for k, e in entries.items() if e.is_expired()]
        # The caller keeps `entries` in read order, so the front is least recently used.
        live = [k for k in entries if k not in doomed]
        overflow = len(live) - capacity
        if overflow > 0:
            doomed.extend(live[:overflow])
        return doomed


class NumObjectsStrategy(ICacheEvictionStrategy):
    """At most `capacity` entries; the oldest *written* leaves first.

    Differs from LRU deliberately: reading an entry does not extend its life. Use it where
    a bounded, predictable working set matters more than keeping hot keys.
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = ttl_seconds

    @property
    def name(self) -> CacheStrategyName:
        return CacheStrategyName.NUM_OBJECTS

    def ttl_for(self, entry: CacheEntry) -> int | None:
        return entry.ttl_seconds or self._ttl

    def evict(self, entries: OrderedDict[str, CacheEntry], capacity: int) -> list[str]:
        doomed = [k for k, e in entries.items() if e.is_expired()]
        live = sorted(
            ((k, e) for k, e in entries.items() if k not in doomed),
            key=lambda kv: kv[1].created_at,
        )
        overflow = len(live) - capacity
        if overflow > 0:
            doomed.extend(k for k, _ in live[:overflow])
        return doomed


class CategoryStrategy(ICacheEvictionStrategy):
    """Entries grouped by category, invalidated as a unit.

    For derived data with a shared trigger: every MIO listing for a domain becomes wrong
    the moment any MIO in that domain is rebuilt, so the domain is the category and one
    rebuild drops all of them. Per-key TTLs cannot express that.
    """

    def __init__(self, ttl_seconds: int | None = None, per_category_capacity: int = 512) -> None:
        self._ttl = ttl_seconds
        self._per_category = per_category_capacity

    @property
    def name(self) -> CacheStrategyName:
        return CacheStrategyName.CATEGORY

    def ttl_for(self, entry: CacheEntry) -> int | None:
        return entry.ttl_seconds or self._ttl

    def evict(self, entries: OrderedDict[str, CacheEntry], capacity: int) -> list[str]:
        doomed = [k for k, e in entries.items() if e.is_expired()]
        by_category: dict[str, list[str]] = {}
        for k, e in entries.items():
            if k in doomed:
                continue
            by_category.setdefault(e.category or "_none", []).append(k)
        for keys in by_category.values():
            overflow = len(keys) - self._per_category
            if overflow > 0:
                doomed.extend(keys[:overflow])
        return doomed


def strategy_for(name: CacheStrategyName, ttl_seconds: int | None = None) -> ICacheEvictionStrategy:
    """Resolve a strategy by name. Both tiers call this, so both get the same behaviour."""
    if name is CacheStrategyName.TTL:
        return TtlStrategy(ttl_seconds or 300)
    if name is CacheStrategyName.LRU_COUNT:
        return LruCountStrategy(ttl_seconds)
    if name is CacheStrategyName.NUM_OBJECTS:
        return NumObjectsStrategy(ttl_seconds)
    if name is CacheStrategyName.CATEGORY:
        return CategoryStrategy(ttl_seconds)
    raise ValueError(f"unknown cache strategy: {name}")
