"""Redis tier: the cache shared by every replica.

Redis is imported lazily and every operation is guarded. A cache is an optimisation, so a
Redis outage must degrade to cache misses and never to failed requests -- `available()`
going false is the normal, expected path, not an error.
"""

from __future__ import annotations

import json
from typing import Any

from ..dtos.cache_dtos import CacheEntry, CacheStats
from .cache_key import namespace
from .cache_strategies import strategy_for
from .i_app_cache_service import ICacheStore


class RedisCacheStore(ICacheStore):
    def __init__(self, url: str, *, key_prefix: str = "akg") -> None:
        self._url = url
        self._prefix = key_prefix
        self._client: Any = None
        self._connect_failed = False
        self._hits: dict[str, int] = {}
        self._misses: dict[str, int] = {}
        self._evictions: dict[str, int] = {}

    @property
    def tier(self) -> str:
        return "redis"

    def _redis(self) -> Any:
        if self._client is not None or self._connect_failed:
            return self._client
        try:
            import redis  # imported here so the service runs without the package

            self._client = redis.Redis.from_url(self._url, decode_responses=True)
            self._client.ping()
        except Exception:
            self._client = None
            self._connect_failed = True
        return self._client

    def available(self) -> bool:
        client = self._redis()
        if client is None:
            return False
        try:
            client.ping()
            return True
        except Exception:
            return False

    def _full_key(self, cache_name: str, cache_key: str) -> str:
        return f"{self._prefix}:{cache_key}" if cache_key.startswith(cache_name) \
            else f"{self._prefix}:{cache_name}:{cache_key}"

    def get(self, cache_name: str, cache_key: str) -> CacheEntry | None:
        client = self._redis()
        if client is None:
            return None
        try:
            raw = client.get(self._full_key(cache_name, cache_key))
        except Exception:
            return None
        if raw is None:
            self._misses[cache_name] = self._misses.get(cache_name, 0) + 1
            return None
        try:
            entry = CacheEntry.model_validate(json.loads(raw))
        except Exception:
            # A value we cannot parse is a value from an older encoding. Drop it rather
            # than failing the caller; the next write replaces it.
            self.evict(cache_name, cache_key)
            return None
        if entry.is_expired():
            self.evict(cache_name, cache_key)
            return None
        self._hits[cache_name] = self._hits.get(cache_name, 0) + 1
        return entry

    def put(self, entry: CacheEntry) -> None:
        client = self._redis()
        if client is None:
            return
        strategy = strategy_for(entry.cache_strategy, entry.ttl_seconds)
        ttl = strategy.ttl_for(entry)
        try:
            payload = entry.model_dump_json()
            key = self._full_key(entry.cache_name, entry.cache_key)
            if ttl:
                client.setex(key, ttl, payload)
            else:
                client.set(key, payload)
            if entry.category:
                # A set per category, so evict_category is one SMEMBERS plus one DEL
                # rather than a SCAN across the keyspace.
                cat_key = f"{self._prefix}:cat:{entry.cache_name}:{entry.category}"
                client.sadd(cat_key, key)
                if ttl:
                    client.expire(cat_key, ttl)
        except Exception:
            return

    def evict(self, cache_name: str, cache_key: str) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            client.delete(self._full_key(cache_name, cache_key))
            self._evictions[cache_name] = self._evictions.get(cache_name, 0) + 1
        except Exception:
            return

    def evict_category(self, cache_name: str, category: str) -> int:
        client = self._redis()
        if client is None:
            return 0
        try:
            cat_key = f"{self._prefix}:cat:{cache_name}:{category}"
            members = client.smembers(cat_key) or set()
            if members:
                client.delete(*members)
            client.delete(cat_key)
            self._evictions[cache_name] = self._evictions.get(cache_name, 0) + len(members)
            return len(members)
        except Exception:
            return 0

    def clear(self, cache_name: str | None = None) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            pattern = f"{self._prefix}:{cache_name}:*" if cache_name else f"{self._prefix}:*"
            # SCAN, never KEYS: KEYS blocks the server for the length of the keyspace.
            for key in client.scan_iter(match=pattern, count=500):
                client.delete(key)
        except Exception:
            return

    def stats(self) -> list[CacheStats]:
        names = set(self._hits) | set(self._misses) | set(self._evictions)
        return [
            CacheStats(
                cache_name=n,
                tier=self.tier,
                entries=-1,  # counting a Redis keyspace per cache needs a SCAN; not worth it
                hits=self._hits.get(n, 0),
                misses=self._misses.get(n, 0),
                evictions=self._evictions.get(n, 0),
            )
            for n in sorted(names)
        ]
