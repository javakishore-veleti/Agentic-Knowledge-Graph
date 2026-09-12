"""The layering rules of ADR-010, enforced by reading imports.

A convention nobody checks is a convention that erodes. These read the AST rather than
trusting review.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "data_catalog"

# package -> packages it may NOT import
FORBIDDEN = {
    "api": {"dao", "entities"},
    "service": {"entities"},
    "dtos": {"dao", "service", "api", "entities", "integration"},
    "common": {"dao", "service", "api", "entities", "integration", "dtos"},
    "tasks": {"entities"},
    "wf": {"dao", "entities"},
    "integration": {"dao", "entities", "service"},
}


def _imports(path: Path) -> set[str]:
    """Local package names imported by one module, relative or absolute."""
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:  # relative: ..dao.x -> dao
                parts = [p for p in mod.split(".") if p]
                if parts:
                    found.add(parts[0])
            elif mod.startswith("data_catalog."):
                found.add(mod.split(".")[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("data_catalog."):
                    found.add(alias.name.split(".")[1])
    return found


def test_no_package_imports_what_it_must_not() -> None:
    violations: list[str] = []
    for pkg, forbidden in FORBIDDEN.items():
        root = SRC / pkg
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            bad = _imports(path) & forbidden
            if bad:
                violations.append(f"{pkg}/{path.name} imports {sorted(bad)}")
    assert not violations, "layering violations:\n  " + "\n  ".join(violations)


#: Feature packages carry their own api/service/dao/dtos (ADR-018). The same rules apply
#: inside each, so the check runs per feature rather than once over a shared tree.
FEATURES = ("purposes", "domains", "endpoints", "datasets", "workflows")


def _feature_imports(path: Path) -> set[str]:
    """Layer names this module imports from, relative or absolute."""
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parts = [p for p in (node.module or "").split(".") if p]
            found.update(parts)
    return found


def test_feature_packages_keep_the_same_layering() -> None:
    """A feature's api must not reach its own dao, and nothing may touch entities."""
    violations: list[str] = []
    for feature in FEATURES:
        root = SRC / feature
        if not root.exists():
            continue
        for layer, forbidden in (("api", {"dao", "entities"}),
                                 ("service", {"entities"}),
                                 ("dtos", {"dao", "service", "api", "entities"})):
            layer_dir = root / layer
            if not layer_dir.exists():
                continue
            for path in layer_dir.rglob("*.py"):
                bad = _feature_imports(path) & forbidden
                if bad:
                    violations.append(f"{feature}/{layer}/{path.name} imports {sorted(bad)}")
    assert not violations, "feature layering violations:\n  " + "\n  ".join(violations)


def test_every_feature_has_the_four_layers() -> None:
    """A feature package is api + service + dao + dtos. A missing one usually means logic
    landed in a layer that should not hold it."""
    incomplete = []
    for feature in FEATURES:
        root = SRC / feature
        if not root.exists() or not any(root.rglob("*.py")):
            continue
        missing = [layer for layer in ("api", "service", "dao", "dtos")
                   if not (root / layer).exists()]
        if missing:
            incomplete.append(f"{feature} missing {missing}")
    assert not incomplete, f"incomplete feature packages: {incomplete}"


def test_only_dao_touches_the_orm() -> None:
    """entities/ is DAO-private. An ORM object reaching the API layer turns a serializer
    into a query and couples the wire format to the schema."""
    offenders = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC)
        top = rel.parts[0] if len(rel.parts) > 1 else ""
        if top in {"dao", "entities"}:
            continue
        if "entities" in _imports(path):
            offenders.append(str(rel))
    assert not offenders, f"non-DAO modules importing entities: {offenders}"


def test_every_api_operation_has_req_resp_and_ctx() -> None:
    """Three classes per operation, named consistently (ADR-010)."""
    import data_catalog.dtos.catalog_dtos as dtos

    names = set(dir(dtos))
    ops = sorted(n[:-3] for n in names if n.endswith("Req") and not n.startswith("_"))
    assert ops, "expected operations to be defined"
    missing = []
    for op in ops:
        for suffix in ("Resp", "Ctx"):
            if f"{op}{suffix}" not in names:
                missing.append(f"{op}{suffix}")
    assert not missing, f"operations missing their companions: {missing}"


def test_handlers_take_a_req_object_not_loose_params() -> None:
    """Every service interface method takes exactly one argument besides self, and it is
    a Ctx. A new input must change one class, not every signature in the chain."""
    import inspect

    from data_catalog.service import i_catalog_service as svc

    offenders = []
    for _, cls in inspect.getmembers(svc, inspect.isclass):
        if not cls.__name__.startswith("I") or cls.__module__ != svc.__name__:
            continue
        for mname, method in inspect.getmembers(cls, inspect.isfunction):
            if mname.startswith("_") or mname == "probe":
                continue
            params = [p for p in inspect.signature(method).parameters if p != "self"]
            if params != ["ctx"]:
                offenders.append(f"{cls.__name__}.{mname}{tuple(params)}")
    assert not offenders, f"methods not taking a single ctx: {offenders}"


def test_every_service_and_dao_is_an_interface_with_an_impl() -> None:
    import inspect

    from data_catalog.dao import catalog_dao_impl, i_catalog_dao
    from data_catalog.service import catalog_service_impl, i_catalog_service

    for iface_mod, impl_mod in ((i_catalog_service, catalog_service_impl),
                                (i_catalog_dao, catalog_dao_impl)):
        ifaces = [
            c for _, c in inspect.getmembers(iface_mod, inspect.isclass)
            if c.__name__.startswith("I") and c.__module__ == iface_mod.__name__
        ]
        assert ifaces, f"no interfaces in {iface_mod.__name__}"
        impls = [c for _, c in inspect.getmembers(impl_mod, inspect.isclass)]
        for iface in ifaces:
            assert any(
                issubclass(c, iface) and c is not iface for c in impls
            ), f"{iface.__name__} has no implementation in {impl_mod.__name__}"
