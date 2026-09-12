"""The only implementations that know SQL or the ORM.

Each returns DTOs, never entities: a lazily-loaded relationship escaping to the API layer
becomes a query inside the serializer, and an entity in a response body couples the wire
format to the schema (ADR-010).

These objects are singletons and stateless. The session factory injected at construction
is immutable wiring; every session is opened and closed inside a single call, so no
connection is held across requests.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..dtos.catalog_dtos import (
    AppEndpointDto, DataInstanceDto, DataInstanceExecDto, DatasetDto, DomainDto,
    ListAppEndpointsReq, ListDataInstanceExecsReq, ListDataInstancesReq, ListDatasetsReq,
    ListDomainsReq, ListMiosReq, MioDto, MioLineageEdgeDto,
)
from ..entities.catalog_entities import (
    AppEndpoint, DataInstance, DataInstanceExec, Dataset, Domain,
)
from .i_catalog_dao import (
    IAppEndpointDao, IDataInstanceDao, IDataInstanceExecDao, IDatasetDao, IDomainDao,
    IHealthDao, IMioDao,
)

SessionFactory = Callable[[], Session]


class _BaseDao:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory


class DomainDaoImpl(_BaseDao, IDomainDao):
    def _stmt(self, tenant_id: str, req: ListDomainsReq):
        stmt = select(Domain).where(Domain.tenant_id == tenant_id)
        if req.q:
            like = f"%{req.q.lower()}%"
            stmt = stmt.where(
                func.lower(Domain.code).like(like) | func.lower(Domain.name).like(like)
            )
        return stmt

    def count(self, tenant_id: str, req: ListDomainsReq) -> int:
        with self._session_factory() as s:
            return s.scalar(
                select(func.count()).select_from(self._stmt(tenant_id, req).subquery())
            ) or 0

    def find(
        self, tenant_id: str, req: ListDomainsReq, limit: int, after: str | None
    ) -> list[DomainDto]:
        stmt = self._stmt(tenant_id, req)
        if after:
            stmt = stmt.where(Domain.code > after)
        with self._session_factory() as s:
            rows = s.scalars(stmt.order_by(Domain.code).limit(limit)).all()
            return [DomainDto.model_validate(r) for r in rows]


class DatasetDaoImpl(_BaseDao, IDatasetDao):
    def _stmt(self, tenant_id: str, req: ListDatasetsReq):
        stmt = select(Dataset).where(Dataset.tenant_id == tenant_id)
        if req.domain:
            stmt = stmt.join(Domain, Domain.domain_id == Dataset.domain_id).where(
                Domain.code == req.domain
            )
        if req.adapter:
            stmt = stmt.where(Dataset.adapter == req.adapter)
        if req.q:
            like = f"%{req.q.lower()}%"
            stmt = stmt.where(
                func.lower(Dataset.code).like(like)
                | func.lower(Dataset.name).like(like)
                | func.lower(Dataset.source_version).like(like)
            )
        return stmt

    def count(self, tenant_id: str, req: ListDatasetsReq) -> int:
        with self._session_factory() as s:
            return s.scalar(
                select(func.count()).select_from(self._stmt(tenant_id, req).subquery())
            ) or 0

    def find(
        self, tenant_id: str, req: ListDatasetsReq, limit: int, after: str | None
    ) -> list[DatasetDto]:
        stmt = self._stmt(tenant_id, req)
        if after:
            stmt = stmt.where(Dataset.code > after)
        with self._session_factory() as s:
            rows = s.scalars(
                stmt.order_by(Dataset.code, Dataset.source_version).limit(limit)
            ).all()
            return [DatasetDto.model_validate(r) for r in rows]


class MioDaoImpl(_BaseDao, IMioDao):
    """Reads catalog.mio_overview.

    The view pre-computes the counts and validations_pass. Doing that once in SQL rather
    than five queries per row is the difference between a list page that loads and one
    that fans out.
    """

    def _where(self, tenant_id: str, req: ListMiosReq) -> tuple[str, dict[str, Any]]:
        clauses = ["tenant_id = :tenant"]
        params: dict[str, Any] = {"tenant": tenant_id}
        if req.domain:
            clauses.append("domain_code = :domain")
            params["domain"] = req.domain
        if req.state:
            clauses.append("state = :state")
            params["state"] = req.state
        if req.tech_stack:
            clauses.append("tech_stack = :tech")
            params["tech"] = req.tech_stack
        if req.has_cdc is not None:
            clauses.append("has_cdc = :has_cdc")
            params["has_cdc"] = req.has_cdc
        if req.q:
            clauses.append("(lower(code) LIKE :q OR lower(name) LIKE :q)")
            params["q"] = f"%{req.q.lower()}%"
        return " AND ".join(clauses), params

    def count(self, tenant_id: str, req: ListMiosReq) -> int:
        clause, params = self._where(tenant_id, req)
        with self._session_factory() as s:
            return s.scalar(
                text(f"SELECT count(*) FROM catalog.mio_overview WHERE {clause}"), params
            ) or 0

    def find(
        self, tenant_id: str, req: ListMiosReq, limit: int, after: str | None
    ) -> list[MioDto]:
        clause, params = self._where(tenant_id, req)
        if after:
            clause += " AND code > :after"
            params["after"] = after
        params["lim"] = limit
        with self._session_factory() as s:
            rows = s.execute(
                text(
                    f"SELECT * FROM catalog.mio_overview WHERE {clause} "
                    f"ORDER BY code LIMIT :lim"
                ),
                params,
            ).mappings().all()
            # Map only the DTO's declared fields. The view carries tenant_id, which a
            # response must not echo, and selecting explicitly also means a column added
            # to the view later cannot break this call.
            fields = set(MioDto.model_fields)
            return [
                MioDto.model_validate({k: v for k, v in dict(r).items() if k in fields})
                for r in rows
            ]

    def exists(self, tenant_id: str, mio_id: uuid.UUID) -> bool:
        with self._session_factory() as s:
            return bool(
                s.scalar(
                    text(
                        "SELECT 1 FROM catalog.mio WHERE mio_id = :id AND tenant_id = :t"
                    ),
                    {"id": mio_id, "t": tenant_id},
                )
            )

    def lineage_parents(self, mio_id: uuid.UUID) -> list[MioLineageEdgeDto]:
        return self._lineage(mio_id, "produced_mio_id", "source_mio_id")

    def lineage_children(self, mio_id: uuid.UUID) -> list[MioLineageEdgeDto]:
        return self._lineage(mio_id, "source_mio_id", "produced_mio_id")

    def _lineage(self, mio_id: uuid.UUID, filter_col: str, join_col: str) -> list[MioLineageEdgeDto]:
        # Column names are from a closed set in this module, never from a request.
        with self._session_factory() as s:
            rows = s.execute(
                text(
                    f"SELECT l.{join_col} AS mio_id, m.code, m.name, l.data_instance_exec_id "
                    f"FROM catalog.mio_lineage l "
                    f"JOIN catalog.mio m ON m.mio_id = l.{join_col} "
                    f"WHERE l.{filter_col} = :id"
                ),
                {"id": mio_id},
            ).mappings().all()
            return [MioLineageEdgeDto.model_validate(dict(r)) for r in rows]


class DataInstanceDaoImpl(_BaseDao, IDataInstanceDao):
    def _stmt(self, tenant_id: str, req: ListDataInstancesReq):
        stmt = select(DataInstance).where(
            DataInstance.mio_id == req.mio_id, DataInstance.tenant_id == tenant_id
        )
        if req.kind:
            stmt = stmt.where(DataInstance.kind == req.kind)
        return stmt

    def count(self, tenant_id: str, req: ListDataInstancesReq) -> int:
        with self._session_factory() as s:
            return s.scalar(
                select(func.count()).select_from(self._stmt(tenant_id, req).subquery())
            ) or 0

    def find(
        self, tenant_id: str, req: ListDataInstancesReq, limit: int
    ) -> list[DataInstanceDto]:
        with self._session_factory() as s:
            rows = s.scalars(
                self._stmt(tenant_id, req)
                .order_by(DataInstance.kind, DataInstance.created_at.desc())
                .limit(limit)
            ).all()
            return [DataInstanceDto.model_validate(r) for r in rows]

    def cdc_instance_id(self, tenant_id: str, mio_id: uuid.UUID) -> uuid.UUID | None:
        """At most one per MIO, enforced by a partial unique index (ADR-009)."""
        with self._session_factory() as s:
            return s.scalar(
                select(DataInstance.data_instance_id).where(
                    DataInstance.mio_id == mio_id,
                    DataInstance.tenant_id == tenant_id,
                    DataInstance.kind == "cdc",
                )
            )


class DataInstanceExecDaoImpl(_BaseDao, IDataInstanceExecDao):
    def _stmt(self, tenant_id: str, req: ListDataInstanceExecsReq):
        stmt = select(DataInstanceExec).where(
            DataInstanceExec.data_instance_id == req.data_instance_id,
            DataInstanceExec.tenant_id == tenant_id,
        )
        if req.status:
            stmt = stmt.where(DataInstanceExec.status == req.status)
        return stmt

    def count(self, tenant_id: str, req: ListDataInstanceExecsReq) -> int:
        with self._session_factory() as s:
            return s.scalar(
                select(func.count()).select_from(self._stmt(tenant_id, req).subquery())
            ) or 0

    def find(
        self, tenant_id: str, req: ListDataInstanceExecsReq, limit: int
    ) -> list[DataInstanceExecDto]:
        with self._session_factory() as s:
            rows = s.scalars(
                self._stmt(tenant_id, req)
                .order_by(DataInstanceExec.created_at.desc())
                .limit(limit)
            ).all()
            return [DataInstanceExecDto.model_validate(r) for r in rows]


class AppEndpointDaoImpl(_BaseDao, IAppEndpointDao):
    def _stmt(self, tenant_id: str, req: ListAppEndpointsReq):
        stmt = select(AppEndpoint).where(AppEndpoint.tenant_id == tenant_id)
        if req.tech_stack:
            stmt = stmt.where(AppEndpoint.tech_stack == req.tech_stack)
        if req.env:
            stmt = stmt.where(AppEndpoint.env == req.env)
        if req.active_only:
            stmt = stmt.where(AppEndpoint.is_active.is_(True))
        return stmt

    def count(self, tenant_id: str, req: ListAppEndpointsReq) -> int:
        with self._session_factory() as s:
            return s.scalar(
                select(func.count()).select_from(self._stmt(tenant_id, req).subquery())
            ) or 0

    def find(
        self, tenant_id: str, req: ListAppEndpointsReq, limit: int
    ) -> list[AppEndpointDto]:
        with self._session_factory() as s:
            rows = s.scalars(
                self._stmt(tenant_id, req)
                .order_by(AppEndpoint.tech_stack, AppEndpoint.code)
                .limit(limit)
            ).all()
            return [AppEndpointDto.model_validate(r) for r in rows]


class HealthDaoImpl(_BaseDao, IHealthDao):
    def probe(self) -> dict[str, Any]:
        """Reports what is true, not merely that the process is up.

        A catalog API answering 200 while the schema is absent makes an empty list look
        like an empty catalog.
        """
        out = {"database": False, "catalog_schema": False, "drift": 0}
        try:
            with self._session_factory() as s:
                out["database"] = s.scalar(text("SELECT 1")) == 1
                out["catalog_schema"] = bool(
                    s.scalar(
                        text(
                            "SELECT count(*) FROM information_schema.views "
                            "WHERE table_schema = 'catalog' "
                            "AND table_name = 'mio_overview'"
                        )
                    )
                )
                if out["catalog_schema"]:
                    out["drift"] = s.scalar(
                        text("SELECT count(*) FROM catalog.data_instance_exec_drift")
                    ) or 0
        except Exception:
            # A probe that raises is a probe that cannot report, which is the one thing
            # health must never do.
            pass
        return out
