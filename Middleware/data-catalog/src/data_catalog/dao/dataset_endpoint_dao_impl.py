"""Dataset location persistence. The only SQL for dataset_endpoint."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from ..dtos.catalog_dtos import (
    AddDatasetEndpointReq, DatasetEndpointDto, DatasetOverviewDto, ListDatasetsReq,
)
from .catalog_dao_impl import _BaseDao
from .i_dataset_endpoint_dao import IAcquisitionDao, IDatasetEndpointDao


class DatasetEndpointDaoImpl(_BaseDao, IDatasetEndpointDao):
    def for_dataset(
        self, tenant_id: str, dataset_id: uuid.UUID, role: str | None
    ) -> list[DatasetEndpointDto]:
        sql = ("SELECT * FROM catalog.dataset_endpoint "
               "WHERE dataset_id = :d AND tenant_id = :t")
        params: dict[str, Any] = {"d": dataset_id, "t": tenant_id}
        if role:
            sql += " AND role = :r"
            params["r"] = role
        # source first, then the copies: reading order matches how people think about it.
        sql += (" ORDER BY CASE role WHEN 'source' THEN 0 WHEN 'landing' THEN 1 "
                "WHEN 'curated' THEN 2 ELSE 3 END, is_primary DESC, created_at")
        fields = set(DatasetEndpointDto.model_fields)
        with self._session_factory() as s:
            rows = s.execute(text(sql), params).mappings().all()
            return [
                DatasetEndpointDto.model_validate(
                    {k: v for k, v in dict(r).items() if k in fields}
                )
                for r in rows
            ]

    def add(self, tenant_id: str, req: AddDatasetEndpointReq) -> uuid.UUID:
        new_id = uuid.uuid4()
        with self._session_factory() as s:
            if req.is_primary:
                # One primary per role, enforced by a partial unique index. Demote the
                # incumbent in the same transaction rather than letting the insert fail.
                s.execute(
                    text("UPDATE catalog.dataset_endpoint SET is_primary = false "
                         "WHERE dataset_id = :d AND role = :r AND is_primary"),
                    {"d": req.dataset_id, "r": req.role},
                )
            s.execute(
                text(
                    "INSERT INTO catalog.dataset_endpoint "
                    "  (dataset_endpoint_id, dataset_id, role, app_endpoint_id, "
                    "   location_kind, uri, options, format, is_primary, tenant_id) "
                    "VALUES (:id, :d, :r, :a, :k, :u, CAST(:o AS jsonb), :f, :p, :t)"
                ),
                {"id": new_id, "d": req.dataset_id, "r": req.role,
                 "a": req.app_endpoint_id, "k": req.location_kind, "u": req.uri,
                 "o": json.dumps(req.options), "f": req.format, "p": req.is_primary,
                 "t": tenant_id},
            )
            s.commit()
        return new_id

    def _where(self, tenant_id: str, req: ListDatasetsReq) -> tuple[str, dict[str, Any]]:
        clauses = ["tenant_id = :tenant"]
        params: dict[str, Any] = {"tenant": tenant_id}
        if req.domain:
            clauses.append("domain_code = :domain")
            params["domain"] = req.domain
        if req.adapter:
            clauses.append("adapter = :adapter")
            params["adapter"] = req.adapter
        if req.q:
            clauses.append("(lower(code) LIKE :q OR lower(name) LIKE :q "
                           "OR lower(source_version) LIKE :q)")
            params["q"] = f"%{req.q.lower()}%"
        return " AND ".join(clauses), params

    def overview_count(self, tenant_id: str, req: ListDatasetsReq) -> int:
        clause, params = self._where(tenant_id, req)
        with self._session_factory() as s:
            return s.scalar(
                text(f"SELECT count(*) FROM catalog.dataset_overview WHERE {clause}"), params
            ) or 0

    def overview(
        self, tenant_id: str, req: ListDatasetsReq, limit: int, after: str | None
    ) -> list[DatasetOverviewDto]:
        clause, params = self._where(tenant_id, req)
        if after:
            clause += " AND code > :after"
            params["after"] = after
        params["lim"] = limit
        fields = set(DatasetOverviewDto.model_fields)
        with self._session_factory() as s:
            rows = s.execute(
                text(f"SELECT * FROM catalog.dataset_overview WHERE {clause} "
                     f"ORDER BY code, source_version LIMIT :lim"),
                params,
            ).mappings().all()
            return [
                DatasetOverviewDto.model_validate(
                    {k: v for k, v in dict(r).items() if k in fields}
                )
                for r in rows
            ]


class AcquisitionDaoImpl(_BaseDao, IAcquisitionDao):
    @staticmethod
    def _jsonable(row: Any) -> dict[str, Any]:
        out = {}
        for k, v in dict(row).items():
            if isinstance(v, uuid.UUID):
                out[k] = str(v)
            elif hasattr(v, "isoformat"):
                out[k] = v.isoformat()
            else:
                out[k] = v
        return out

    def get(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict[str, Any] | None:
        """One endpoint, plus the source its dataset is downloaded FROM.

        source_uri is joined in rather than left to the caller: the acquisition DAG is
        told which destination to fill and would otherwise need a second round trip to
        discover where the data comes from -- and two lookups are two chances for the
        pair to disagree about which dataset is being acquired.

        The primary source wins when a dataset declares more than one; is_primary DESC
        makes that explicit instead of relying on insertion order.
        """
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT de.*, "
                     "       (SELECT src.uri FROM catalog.dataset_endpoint src "
                     "         WHERE src.dataset_id = de.dataset_id "
                     "           AND src.tenant_id = de.tenant_id "
                     "           AND src.role = 'source' "
                     "         ORDER BY src.is_primary DESC, src.created_at "
                     "         LIMIT 1) AS source_uri, "
                     # The destination's configuration, so the runner can resolve where
                     # "the local filesystem" actually is. It is not the same directory
                     # on every machine, and a DAG executing in a container resolves the
                     # same endpoint to a different real path than this process would.
                     "       ae.connection_details AS dest_connection_details, "
                     "       ae.code AS dest_endpoint_code "
                     "  FROM catalog.dataset_endpoint de "
                     "  LEFT JOIN catalog.app_endpoint ae "
                     "         ON ae.app_endpoint_id = de.app_endpoint_id "
                     " WHERE de.dataset_endpoint_id = :id AND de.tenant_id = :t"),
                {"id": endpoint_id, "t": tenant_id},
            ).mappings().first()
            return self._jsonable(row) if row else None

    def claim(
        self, tenant_id: str, endpoint_id: uuid.UUID, exec_id: uuid.UUID, force: bool
    ) -> tuple[bool, str]:
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT claimed, reason FROM catalog.claim_dataset_endpoint_sync("
                     ":id, :exec, :tenant, :force)"),
                {"id": endpoint_id, "exec": exec_id, "tenant": tenant_id, "force": force},
            ).mappings().first()
            s.commit()
        return (bool(row["claimed"]), str(row["reason"])) if row else (False, "unknown")

    def complete(
        self, tenant_id: str, endpoint_id: uuid.UUID, status: str,
        bytes_written: int | None, object_count: int | None,
        error: dict[str, Any] | None, wf_ref_id: str | None,
    ) -> dict[str, Any] | None:
        with self._session_factory() as s:
            s.execute(
                text("SELECT catalog.complete_dataset_endpoint_sync("
                     ":id, :tenant, :status, :bytes, :objects, CAST(:error AS jsonb), :ref)"),
                {"id": endpoint_id, "tenant": tenant_id, "status": status,
                 "bytes": bytes_written, "objects": object_count,
                 "error": None if error is None else json.dumps(error), "ref": wf_ref_id},
            )
            s.commit()
            row = s.execute(
                text("SELECT state, sync_wf_status, bytes FROM catalog.dataset_endpoint "
                     "WHERE dataset_endpoint_id = :id"),
                {"id": endpoint_id},
            ).mappings().first()
            return self._jsonable(row) if row else None

    def stuck(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as s:
            rows = s.execute(
                text("SELECT * FROM catalog.dataset_endpoint_stuck_sync")
            ).mappings().all()
            return [self._jsonable(r) for r in rows]
