"""Cache interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..dtos.cache_dtos import CacheEntry, CacheStats, CacheStrategyName


class ICacheStore(ABC):
    """One tier. Redis is the shared tier; the in-memory LRU is the local mirror."""

    @property
    @abstractmethod
    def tier(self) -> str: ...

    @abstractmethod
    def get(self, cache_name: str, cache_key: str) -> CacheEntry | None: ...

    @abstractmethod
    def put(self, entry: CacheEntry) -> None: ...

    @abstractmethod
    def evict(self, cache_name: str, cache_key: str) -> None: ...

    @abstractmethod
    def evict_category(self, cache_name: str, category: str) -> int: ...

    @abstractmethod
    def clear(self, cache_name: str | None = None) -> None: ...

    @abstractmethod
    def stats(self) -> list[CacheStats]: ...

    @abstractmethod
    def available(self) -> bool:
        """False when the tier cannot serve. A cache is an optimisation: callers must
        keep working when it is down, so this is checked rather than assumed."""


class IAppCacheService(ABC):
    """What the service layer uses. Knows nothing about Redis or memory."""

    @abstractmethod
    def get(self, cache_name: str, tenant_id: str, key_parts: dict[str, Any]) -> Any | None: ...

    @abstractmethod
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
    ) -> None: ...

    @abstractmethod
    def evict(self, cache_name: str, tenant_id: str, key_parts: dict[str, Any]) -> None: ...

    @abstractmethod
    def evict_category(self, cache_name: str, tenant_id: str, category: str) -> int: ...

    @abstractmethod
    def stats(self) -> list[CacheStats]: ...
