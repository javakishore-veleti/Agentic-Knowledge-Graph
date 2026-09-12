"""Cache DTOs.

Every cached thing carries four attributes: its strategy, its cache name, its key and its
value. Strategy and name travel with the entry rather than living only in configuration,
so an entry can be reasoned about -- and evicted correctly -- wherever it is found.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CacheStrategyName(StrEnum):
    """Eviction strategies.

    TTL             expire after a fixed age
    LRU_COUNT       keep at most N entries, discard least recently used
    NUM_OBJECTS     keep at most N entries, discard oldest written (insertion order)
    CATEGORY        grouped by category; a category is invalidated as a unit
    """

    TTL = "ttl"
    LRU_COUNT = "lru_count"
    NUM_OBJECTS = "num_objects"
    CATEGORY = "category"


class CacheEntry(BaseModel):
    """One cached value plus everything needed to evict it correctly."""

    model_config = ConfigDict(extra="forbid")

    cache_strategy: CacheStrategyName
    cache_name: str = Field(min_length=1, max_length=64)
    cache_key: str = Field(min_length=1, max_length=512)
    value: Any

    # Category strategy only: the unit of bulk invalidation.
    category: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int | None = None
    last_read_at: datetime | None = None
    hits: int = 0

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.ttl_seconds is None:
            return False
        now = now or datetime.now(UTC)
        return now >= self.created_at + timedelta(seconds=self.ttl_seconds)


class CacheStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cache_name: str
    tier: str
    entries: int
    hits: int
    misses: int
    evictions: int
    # Entries served from L1 that Redis had already dropped. Non-zero means the tiers
    # disagreed and a caller may have seen a stale value.
    stale_l1_reads: int = 0
