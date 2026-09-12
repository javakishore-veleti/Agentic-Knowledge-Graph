"""In-process mirror of the shared cache.

This is the one deliberately stateful singleton in the service: a cache whose state *is*
its purpose. Because it is shared across concurrent requests, every mutation is under a
lock -- an unsynchronised dict shared by request threads corrupts its own ordering, which
in an LRU means evicting the wrong entries.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, datetime
from threading import RLock

from ..dtos.cache_dtos import CacheEntry, CacheStats, CacheStrategyName
from .cache_strategies import strategy_for
from .i_app_cache_service import ICacheStore


class MemoryLruCacheStore(ICacheStore):
    def __init__(self, capacity: int = 1024) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._lock = RLock()
        self._entries: dict[str, OrderedDict[str, CacheEntry]] = {}
        self._hits: dict[str, int] = {}
        self._misses: dict[str, int] = {}
        self._evictions: dict[str, int] = {}

    @property
    def tier(self) -> str:
        return "memory"

    def available(self) -> bool:
        return True

    def get(self, cache_name: str, cache_key: str) -> CacheEntry | None:
        with self._lock:
            bucket = self._entries.get(cache_name)
            if bucket is None or cache_key not in bucket:
                self._misses[cache_name] = self._misses.get(cache_name, 0) + 1
                return None
            entry = bucket[cache_key]
            if entry.is_expired():
                # Expiry is enforced on read as well as on write: a key nobody touches
                # must not be servable past its TTL just because no eviction pass ran.
                del bucket[cache_key]
                self._evictions[cache_name] = self._evictions.get(cache_name, 0) + 1
                self._misses[cache_name] = self._misses.get(cache_name, 0) + 1
                return None
            # Move to the back: the front of the OrderedDict is least recently used, which
            # is what LruCountStrategy relies on.
            bucket.move_to_end(cache_key)
            entry.last_read_at = datetime.now(UTC)
            entry.hits += 1
            self._hits[cache_name] = self._hits.get(cache_name, 0) + 1
            return entry

    def put(self, entry: CacheEntry) -> None:
        with self._lock:
            bucket = self._entries.setdefault(entry.cache_name, OrderedDict())
            bucket[entry.cache_key] = entry
            bucket.move_to_end(entry.cache_key)

            strategy = strategy_for(entry.cache_strategy, entry.ttl_seconds)
            for key in strategy.evict(bucket, self._capacity):
                bucket.pop(key, None)
                self._evictions[entry.cache_name] = self._evictions.get(entry.cache_name, 0) + 1

    def evict(self, cache_name: str, cache_key: str) -> None:
        with self._lock:
            bucket = self._entries.get(cache_name)
            if bucket and bucket.pop(cache_key, None) is not None:
                self._evictions[cache_name] = self._evictions.get(cache_name, 0) + 1

    def evict_category(self, cache_name: str, category: str) -> int:
        with self._lock:
            bucket = self._entries.get(cache_name)
            if not bucket:
                return 0
            doomed = [k for k, e in bucket.items() if e.category == category]
            for k in doomed:
                del bucket[k]
            self._evictions[cache_name] = self._evictions.get(cache_name, 0) + len(doomed)
            return len(doomed)

    def clear(self, cache_name: str | None = None) -> None:
        with self._lock:
            if cache_name is None:
                self._entries.clear()
            else:
                self._entries.pop(cache_name, None)

    def stats(self) -> list[CacheStats]:
        with self._lock:
            return [
                CacheStats(
                    cache_name=name,
                    tier=self.tier,
                    entries=len(bucket),
                    hits=self._hits.get(name, 0),
                    misses=self._misses.get(name, 0),
                    evictions=self._evictions.get(name, 0),
                )
                for name, bucket in self._entries.items()
            ]
