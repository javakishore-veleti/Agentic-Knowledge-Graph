"""Singletons must be stateless (the owner's rule, ADR-010).

A singleton that keeps request state corrupts concurrent requests -- the failure appears
under load, in production, as one user seeing another's data. These tests make the rule
mechanical instead of aspirational.
"""

from __future__ import annotations

import copy
import inspect

import pytest

from data_catalog.common.object_factory import DAO_FACTORY, SERVICE_FACTORY
from data_catalog.tasks import catalog_tasks
from data_catalog.wf import catalog_wf


def _state_snapshot(obj: object) -> dict:
    """Mutable instance attributes, excluding immutable wiring."""
    out = {}
    for k, v in vars(obj).items():
        if isinstance(v, (str, int, float, bool, type(None), tuple, frozenset)):
            continue
        out[k] = copy.deepcopy(v) if isinstance(v, (dict, list, set)) else repr(v)
    return out


def test_tasks_hold_no_mutable_state() -> None:
    offenders = []
    for name, cls in inspect.getmembers(catalog_tasks, inspect.isclass):
        if not name.endswith("Task") or inspect.isabstract(cls):
            continue
        try:
            inst = cls() if not inspect.signature(cls).parameters else None
        except Exception:
            inst = None
        if inst is None:
            continue
        mutable = {
            k: v for k, v in vars(inst).items() if isinstance(v, (dict, list, set))
        }
        if mutable:
            offenders.append(f"{name}: {sorted(mutable)}")
    assert not offenders, f"tasks holding mutable state: {offenders}"


def test_workflow_task_lists_are_immutable() -> None:
    """The task sequence is wiring, not state: nothing may append to it at runtime."""
    for name, cls in inspect.getmembers(catalog_wf, inspect.isclass):
        if not name.endswith("Wf") or inspect.isabstract(cls):
            continue
        wf = cls()
        assert isinstance(wf.tasks(), tuple), f"{name}.tasks() must return a tuple"


def test_factories_do_not_share_state() -> None:
    """An earlier version declared the singleton registry at class level, which silently
    shared it between the service and dao factories."""
    assert SERVICE_FACTORY is not DAO_FACTORY
    assert SERVICE_FACTORY._providers is not DAO_FACTORY._providers
    assert SERVICE_FACTORY._instances is not DAO_FACTORY._instances


def test_factory_returns_the_same_instance_every_time() -> None:
    from data_catalog.bootstrap import register_all
    from data_catalog.service.i_catalog_service import IDomainService

    register_all()
    a = SERVICE_FACTORY.get(IDomainService)
    b = SERVICE_FACTORY.get(IDomainService)
    assert a is b, "services must be singletons"


def test_factory_rejects_an_implementation_that_does_not_implement() -> None:
    from data_catalog.common.object_factory import ObjectFactory
    from data_catalog.service.i_catalog_service import IDomainService

    f = ObjectFactory("test")
    f.register(IDomainService, lambda: object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="does not implement"):
        f.get(IDomainService)


def test_unregistered_interface_names_itself_in_the_error() -> None:
    from data_catalog.common.object_factory import ObjectFactory
    from data_catalog.service.i_catalog_service import IMioService

    f = ObjectFactory("test")
    with pytest.raises(LookupError, match="IMioService"):
        f.get(IMioService)


def test_service_state_unchanged_by_handling_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real invariant: running a use case leaves the singleton untouched."""
    from data_catalog.bootstrap import register_all
    from data_catalog.dtos.catalog_dtos import ListDomainsCtx, ListDomainsReq
    from data_catalog.service.i_catalog_service import IDomainService

    register_all()
    svc = SERVICE_FACTORY.get(IDomainService)
    before = _state_snapshot(svc)
    try:
        svc.list_domains(ListDomainsCtx(req=ListDomainsReq(), tenant_id="reference"))
    except Exception:
        # A database may not be present; what matters is that the attempt changed nothing.
        pass
    assert _state_snapshot(svc) == before
