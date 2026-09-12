"""Cache behaviour, including the parts that are easy to get quietly wrong."""

from __future__ import annotations

import time

import pytest

from data_catalog.cache.app_cache_service_impl import AppCacheServiceImpl
from data_catalog.cache.cache_key import build_key
from data_catalog.cache.memory_lru_cache_store import MemoryLruCacheStore
from data_catalog.dtos.cache_dtos import CacheEntry, CacheStrategyName


def _entry(key: str, value: object, strategy=CacheStrategyName.LRU_COUNT, **kw) -> CacheEntry:
    return CacheEntry(
        cache_strategy=strategy, cache_name="t", cache_key=key, value=value, **kw
    )


class _DeadStore(MemoryLruCacheStore):
    """Stands in for Redis being down."""

    @property
    def tier(self) -> str:
        return "redis"

    def available(self) -> bool:
        return False

    def get(self, cache_name: str, cache_key: str):
        return None

    def put(self, entry: CacheEntry) -> None:
        return None


# ---------------------------------------------------------------- keys


def test_key_requires_a_tenant() -> None:
    """An untenanted key serves one tenant's data to another. That is a leak, not a bug."""
    with pytest.raises(ValueError, match="tenant_id is required"):
        build_key("mios", "", {"state": "live"})


def test_key_is_tenant_scoped() -> None:
    a = build_key("mios", "tenant-a", {"state": "live"})
    b = build_key("mios", "tenant-b", {"state": "live"})
    assert a != b


def test_key_is_order_independent() -> None:
    assert build_key("m", "t", {"a": 1, "b": 2}) == build_key("m", "t", {"b": 2, "a": 1})


def test_long_keys_are_hashed_but_stay_recognisable() -> None:
    key = build_key("mios", "t", {"q": "x" * 400})
    assert key.startswith("mios:t:h:")
    assert len(key) < 120


# ---------------------------------------------------------------- eviction


def test_lru_evicts_the_least_recently_read() -> None:
    store = MemoryLruCacheStore(capacity=2)
    store.put(_entry("a", 1))
    store.put(_entry("b", 2))
    store.get("t", "a")           # 'a' is now the most recently used
    store.put(_entry("c", 3))     # capacity exceeded -> 'b' should go
    assert store.get("t", "a") is not None
    assert store.get("t", "b") is None
    assert store.get("t", "c") is not None


def test_num_objects_ignores_reads() -> None:
    """Unlike LRU, reading does not extend life: the oldest written leaves."""
    store = MemoryLruCacheStore(capacity=2)
    store.put(_entry("a", 1, CacheStrategyName.NUM_OBJECTS))
    time.sleep(0.01)
    store.put(_entry("b", 2, CacheStrategyName.NUM_OBJECTS))
    store.get("t", "a")
    time.sleep(0.01)
    store.put(_entry("c", 3, CacheStrategyName.NUM_OBJECTS))
    assert store.get("t", "a") is None, "oldest written should be evicted despite the read"


def test_ttl_expires_on_read_even_with_no_eviction_pass() -> None:
    """A key nobody touches must not be servable past its TTL just because no eviction
    pass happened to run."""
    store = MemoryLruCacheStore(capacity=10)
    store.put(_entry("a", 1, CacheStrategyName.TTL, ttl_seconds=1))
    assert store.get("t", "a") is not None
    time.sleep(1.05)
    assert store.get("t", "a") is None


def test_category_eviction_drops_the_whole_group() -> None:
    store = MemoryLruCacheStore(capacity=50)
    for i in range(3):
        store.put(_entry(f"bio{i}", i, CacheStrategyName.CATEGORY, category="biomedical"))
    store.put(_entry("ent0", 9, CacheStrategyName.CATEGORY, category="enterprise"))
    removed = store.evict_category("t", "biomedical")
    assert removed == 3
    assert store.get("t", "ent0") is not None


# ---------------------------------------------------------------- tiers


def test_cache_degrades_to_a_miss_when_redis_is_down() -> None:
    """A cache is an optimisation. An outage must produce misses, never failures."""
    svc = AppCacheServiceImpl(_DeadStore(), MemoryLruCacheStore(), mirror_in_memory=True)
    svc.put("mios", "t", {"state": "live"}, [1, 2, 3])
    # Nothing raised; the local mirror answers, and the shared tier simply has nothing.
    assert svc.get("mios", "t", {"state": "live"}) in ([1, 2, 3], None)


def test_mirror_off_means_nothing_is_stored_locally() -> None:
    local = MemoryLruCacheStore()
    svc = AppCacheServiceImpl(_DeadStore(), local, mirror_in_memory=False)
    svc.put("mios", "t", {"state": "live"}, [1])
    assert local.stats() == [] or all(s.entries == 0 for s in local.stats())


def test_evict_clears_the_local_copy_even_when_mirroring_is_off() -> None:
    """A toggle flipped at runtime must not leave a stale local copy behind."""
    local = MemoryLruCacheStore()
    on = AppCacheServiceImpl(_DeadStore(), local, mirror_in_memory=True)
    on.put("mios", "t", {"k": 1}, "v")
    off = AppCacheServiceImpl(_DeadStore(), local, mirror_in_memory=False)
    off.evict("mios", "t", {"k": 1})
    assert local.get("mios", build_key("mios", "t", {"k": 1})) is None


def test_stale_l1_read_is_detected_and_counted() -> None:
    """The one thing the mirror cannot prevent: Redis evicting under its own memory
    pressure while L1 still holds the key. Counted, not hidden (ADR-011)."""
    shared = MemoryLruCacheStore()
    local = MemoryLruCacheStore()
    svc = AppCacheServiceImpl(shared, local, mirror_in_memory=True)
    svc.put("mios", "t", {"k": 1}, "v")
    # Simulate Redis dropping it independently.
    shared.clear()
    assert svc.get("mios", "t", {"k": 1}) is None
    assert any(s.stale_l1_reads == 1 for s in svc.stats() if s.tier == "memory")
