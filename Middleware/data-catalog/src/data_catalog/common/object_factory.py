"""Lookup by interface, one factory per boundary (ADR-010).

`SERVICE_FACTORY` serves api -> service; `DAO_FACTORY` serves service -> dao. A caller
asks for an interface and receives whatever is registered for it, so no caller names an
implementation class. `bootstrap.py` is the only module that knows both sides.

Everything it hands out is a singleton, and every singleton is stateless: the object holds
immutable wiring only, and all per-request state lives on the Ctx that is passed in. A
singleton that kept request state would corrupt concurrent requests, which is why
`test_statelessness.py` asserts that handling a request leaves these objects unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar

T = TypeVar("T")


class ObjectFactory:
    def __init__(self, boundary: str) -> None:
        # All per-instance. An earlier version declared the singleton flags at class
        # level, which silently shared them between the service and dao factories.
        self.boundary = boundary
        self._providers: dict[type, Callable[[], Any]] = {}
        self._instances: dict[type, Any] = {}
        self._lock = Lock()

    def register(self, interface: type[T], provider: Callable[[], T]) -> None:
        """Bind an interface to a provider. The instance is created on first lookup."""
        if not isinstance(interface, type):
            raise TypeError(f"{self.boundary}: {interface!r} is not a type")
        with self._lock:
            self._providers[interface] = provider
            # A re-registration replaces the live instance too, or the old one would
            # outlive its own binding.
            self._instances.pop(interface, None)

    def get(self, interface: type[T]) -> T:
        with self._lock:
            existing = self._instances.get(interface)
            if existing is not None:
                return existing
            provider = self._providers.get(interface)
            if provider is None:
                raise LookupError(
                    f"{self.boundary}: nothing registered for {interface.__name__}. "
                    f"Register it in bootstrap.py. Registered: {self.registered()}"
                )
            instance = provider()
            if not isinstance(instance, interface):
                raise TypeError(
                    f"{self.boundary}: provider for {interface.__name__} returned "
                    f"{type(instance).__name__}, which does not implement it"
                )
            self._instances[interface] = instance
            return instance

    def registered(self) -> list[str]:
        return sorted(i.__name__ for i in self._providers)

    def clear(self) -> None:
        """Test support only."""
        with self._lock:
            self._providers.clear()
            self._instances.clear()


SERVICE_FACTORY = ObjectFactory("api->service")
DAO_FACTORY = ObjectFactory("service->dao")
