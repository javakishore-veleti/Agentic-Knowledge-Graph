"""DataCatalog read API.

Every list endpoint is tenant-scoped, cursor-paginated, and filtered before it reaches
the database rather than after.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import schemas
from .config import settings
from .db import get_session
from .models import AppEndpoint, DataInstance, DataInstanceExec, Dataset, Domain, Mio
from .pagination import clamp_limit, decode_cursor, encode_cursor

router = APIRouter(prefix=settings.api_prefix)

SessionDep = Annotated[Session, Depends(get_session)]


def _page(total: int, limit: int, rows: list[Any], key: str) -> schemas.Page:
    nxt = None
    if len(rows) == limit and rows:
        last = rows[-1]
        nxt = encode_cursor({"after": str(getattr(last, key)),
                             "created_at": str(getattr(last, "created_at", ""))})
    return schemas.Page(total=total, limit=limit, next_cursor=nxt)


def _cursor(raw: str | None) -> dict[str, Any] | None:
    try:
        return decode_cursor(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/domains", response_model=schemas.DomainList, tags=["catalog"])
def list_domains(
    session: SessionDep,
    limit: int | None = None,
    cursor: str | None = None,
    q: str | None = Query(default=None, description="match code or name"),
) -> schemas.DomainList:
    lim = clamp_limit(limit)
    cur = _cursor(cursor)

    stmt = select(Domain).where(Domain.tenant_id == settings.tenant_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Domain.code).like(like) | func.lower(Domain.name).like(like))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if cur:
        stmt = stmt.where(Domain.code > cur["after"])
    rows = list(session.scalars(stmt.order_by(Domain.code).limit(lim)))
    return schemas.DomainList(
        page=_page(total, lim, rows, "code"),
        items=[schemas.DomainOut.model_validate(r) for r in rows],
    )


@router.get("/datasets", response_model=schemas.DatasetList, tags=["catalog"])
def list_datasets(
    session: SessionDep,
    limit: int | None = None,
    cursor: str | None = None,
    domain: str | None = Query(default=None, description="domain code"),
    adapter: str | None = None,
    q: str | None = None,
) -> schemas.DatasetList:
    lim = clamp_limit(limit)
    cur = _cursor(cursor)

    stmt = select(Dataset).where(Dataset.tenant_id == settings.tenant_id)
    if domain:
        stmt = stmt.join(Domain, Domain.domain_id == Dataset.domain_id).where(Domain.code == domain)
    if adapter:
        stmt = stmt.where(Dataset.adapter == adapter)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Dataset.code).like(like)
            | func.lower(Dataset.name).like(like)
            | func.lower(Dataset.source_version).like(like)
        )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if cur:
        stmt = stmt.where(Dataset.code > cur["after"])
    rows = list(session.scalars(stmt.order_by(Dataset.code, Dataset.source_version).limit(lim)))
    return schemas.DatasetList(
        page=_page(total, lim, rows, "code"),
        items=[schemas.DatasetOut.model_validate(r) for r in rows],
    )


@router.get("/mios", response_model=schemas.MioList, tags=["catalog"])
def list_mios(
    session: SessionDep,
    limit: int | None = None,
    cursor: str | None = None,
    domain: str | None = Query(default=None, description="domain code"),
    state: str | None = None,
    tech_stack: str | None = None,
    has_cdc: bool | None = None,
    q: str | None = None,
) -> schemas.MioList:
    """Reads catalog.mio_overview, which pre-computes the counts and validations_pass.

    Doing this in one view rather than five per-row queries is the difference between a
    list page that loads and one that fans out.
    """
    lim = clamp_limit(limit)
    cur = _cursor(cursor)

    where = ["tenant_id = :tenant"]
    params: dict[str, Any] = {"tenant": settings.tenant_id, "lim": lim}
    if domain:
        where.append("domain_code = :domain")
        params["domain"] = domain
    if state:
        where.append("state = :state")
        params["state"] = state
    if tech_stack:
        where.append("tech_stack = :tech")
        params["tech"] = tech_stack
    if has_cdc is not None:
        where.append("coalesce(has_cdc, false) = :has_cdc")
        params["has_cdc"] = has_cdc
    if q:
        where.append("(lower(code) LIKE :q OR lower(name) LIKE :q)")
        params["q"] = f"%{q.lower()}%"

    clause = " AND ".join(where)
    total = session.scalar(
        text(f"SELECT count(*) FROM catalog.mio_overview WHERE {clause}"), params
    ) or 0
    if cur:
        clause += " AND code > :after"
        params["after"] = cur["after"]
    rows = session.execute(
        text(f"SELECT * FROM catalog.mio_overview WHERE {clause} ORDER BY code LIMIT :lim"),
        params,
    ).mappings().all()

    nxt = encode_cursor({"after": rows[-1]["code"]}) if len(rows) == lim and rows else None
    return schemas.MioList(
        page=schemas.Page(total=total, limit=lim, next_cursor=nxt),
        items=[schemas.MioOut.model_validate(dict(r)) for r in rows],
    )


@router.get("/mios/{mio_id}/instances", response_model=schemas.DataInstanceList, tags=["catalog"])
def list_instances(
    session: SessionDep,
    mio_id: uuid.UUID,
    kind: str | None = Query(default=None, description="historical | realtime | cdc"),
    limit: int | None = None,
) -> schemas.DataInstanceList:
    lim = clamp_limit(limit)
    stmt = select(DataInstance).where(
        DataInstance.mio_id == mio_id, DataInstance.tenant_id == settings.tenant_id
    )
    if kind:
        stmt = stmt.where(DataInstance.kind == kind)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(session.scalars(stmt.order_by(DataInstance.created_at.desc()).limit(lim)))
    return schemas.DataInstanceList(
        page=schemas.Page(total=total, limit=lim),
        items=[schemas.DataInstanceOut.model_validate(r) for r in rows],
    )


@router.get(
    "/instances/{data_instance_id}/execs", response_model=schemas.ExecList, tags=["catalog"]
)
def list_execs(
    session: SessionDep,
    data_instance_id: uuid.UUID,
    status: str | None = None,
    limit: int | None = None,
) -> schemas.ExecList:
    lim = clamp_limit(limit)
    stmt = select(DataInstanceExec).where(
        DataInstanceExec.data_instance_id == data_instance_id,
        DataInstanceExec.tenant_id == settings.tenant_id,
    )
    if status:
        stmt = stmt.where(DataInstanceExec.status == status)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(session.scalars(stmt.order_by(DataInstanceExec.created_at.desc()).limit(lim)))
    return schemas.ExecList(
        page=schemas.Page(total=total, limit=lim),
        items=[schemas.DataInstanceExecOut.model_validate(r) for r in rows],
    )


@router.get("/app-endpoints", response_model=schemas.AppEndpointList, tags=["catalog"])
def list_app_endpoints(
    session: SessionDep,
    tech_stack: str | None = None,
    env: str | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> schemas.AppEndpointList:
    """Several endpoints may exist per technology, so results are never collapsed by
    tech_stack. Credentials are not present in the response model at all."""
    lim = clamp_limit(limit)
    stmt = select(AppEndpoint).where(AppEndpoint.tenant_id == settings.tenant_id)
    if tech_stack:
        stmt = stmt.where(AppEndpoint.tech_stack == tech_stack)
    if env:
        stmt = stmt.where(AppEndpoint.env == env)
    if active_only:
        stmt = stmt.where(AppEndpoint.is_active.is_(True))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(session.scalars(stmt.order_by(AppEndpoint.tech_stack, AppEndpoint.code).limit(lim)))
    return schemas.AppEndpointList(
        page=schemas.Page(total=total, limit=lim),
        items=[schemas.AppEndpointOut.model_validate(r) for r in rows],
    )


@router.get("/mios/{mio_id}/lineage", tags=["catalog"])
def mio_lineage(session: SessionDep, mio_id: uuid.UUID) -> dict[str, Any]:
    """What produced this MIO, and what it went on to produce."""
    parents = session.execute(
        text(
            "SELECT l.source_mio_id, m.code, m.name, l.data_instance_exec_id "
            "FROM catalog.mio_lineage l JOIN catalog.mio m ON m.mio_id = l.source_mio_id "
            "WHERE l.produced_mio_id = :id"
        ),
        {"id": mio_id},
    ).mappings().all()
    children = session.execute(
        text(
            "SELECT l.produced_mio_id, m.code, m.name, l.data_instance_exec_id "
            "FROM catalog.mio_lineage l JOIN catalog.mio m ON m.mio_id = l.produced_mio_id "
            "WHERE l.source_mio_id = :id"
        ),
        {"id": mio_id},
    ).mappings().all()
    return {
        "mio_id": str(mio_id),
        "produced_from": [dict(r) for r in parents],
        "generated": [dict(r) for r in children],
    }
