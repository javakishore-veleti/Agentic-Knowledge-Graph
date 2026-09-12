"""Workflow master, MIO writes and invocation recording. The only SQL for these."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from ..dtos.catalog_dtos import (
    CreateMioReq, ListWorkflowsReq, MioDto, MioWorkflowDto, UpdateMioReq, WorkflowDto,
)
from .catalog_dao_impl import _BaseDao
from .i_workflow_dao import IInvocationDao, IMioWriteDao, IWorkflowDao


class WorkflowDaoImpl(_BaseDao, IWorkflowDao):
    def _where(self, tenant_id: str, req: ListWorkflowsReq) -> tuple[str, dict[str, Any]]:
        clauses = ["tenant_id = :tenant"]
        params: dict[str, Any] = {"tenant": tenant_id}
        if req.domain:
            clauses.append("domain = :domain")
            params["domain"] = req.domain
        if req.active_only:
            clauses.append("is_active")
        if req.q:
            clauses.append("(lower(code) LIKE :q OR lower(name) LIKE :q)")
            params["q"] = f"%{req.q.lower()}%"
        return " AND ".join(clauses), params

    def count(self, tenant_id: str, req: ListWorkflowsReq) -> int:
        clause, params = self._where(tenant_id, req)
        with self._session_factory() as s:
            return s.scalar(
                text(f"SELECT count(*) FROM catalog.workflow WHERE {clause}"), params
            ) or 0

    def find(
        self, tenant_id: str, req: ListWorkflowsReq, limit: int, after: str | None
    ) -> list[WorkflowDto]:
        clause, params = self._where(tenant_id, req)
        if after:
            clause += " AND code > :after"
            params["after"] = after
        params["lim"] = limit
        with self._session_factory() as s:
            rows = s.execute(
                text(f"SELECT * FROM catalog.workflow WHERE {clause} ORDER BY code LIMIT :lim"),
                params,
            ).mappings().all()
            fields = set(WorkflowDto.model_fields)
            return [
                WorkflowDto.model_validate({k: v for k, v in dict(r).items() if k in fields})
                for r in rows
            ]

    def get(self, tenant_id: str, workflow_id: uuid.UUID) -> WorkflowDto | None:
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT * FROM catalog.workflow WHERE workflow_id = :id AND tenant_id = :t"),
                {"id": workflow_id, "t": tenant_id},
            ).mappings().first()
            if row is None:
                return None
            fields = set(WorkflowDto.model_fields)
            return WorkflowDto.model_validate({k: v for k, v in dict(row).items() if k in fields})

    def for_mio(self, mio_id: uuid.UUID) -> list[MioWorkflowDto]:
        with self._session_factory() as s:
            rows = s.execute(
                text("SELECT * FROM catalog.mio_workflow_detail WHERE mio_id = :id "
                     "ORDER BY workflow_code"),
                {"id": mio_id},
            ).mappings().all()
            out = []
            for r in rows:
                d = dict(r)
                out.append(MioWorkflowDto.model_validate({
                    "workflow_id": d.get("workflow_id"),
                    "workflow_code": d.get("workflow_code"),
                    "workflow_name": d.get("workflow_name"),
                    "description": d.get("description"),
                    "default_tech_stack": d.get("default_tech_stack"),
                    "purpose": d.get("purpose") or "build",
                    "enabled": bool(d.get("enabled", True)),
                    "params_json": d.get("params_json") or [],
                    "param_overrides_json": d.get("param_overrides_json") or {},
                    "workflow_active": bool(d.get("workflow_active")),
                }))
            return out

    def attach(
        self, mio_id: uuid.UUID, workflow_id: uuid.UUID, workflow_code: str,
        purpose: str, overrides: dict[str, Any],
    ) -> bool:
        import json

        with self._session_factory() as s:
            s.execute(
                text(
                    "INSERT INTO catalog.mio_workflow "
                    "  (mio_id, workflow, purpose, workflow_id, enabled, param_overrides_json) "
                    "VALUES (:m, :code, :p, :w, true, CAST(:o AS jsonb)) "
                    "ON CONFLICT (mio_id, workflow) DO UPDATE "
                    "  SET workflow_id = EXCLUDED.workflow_id, "
                    "      purpose = EXCLUDED.purpose, "
                    "      enabled = true, "
                    "      param_overrides_json = EXCLUDED.param_overrides_json"
                ),
                {"m": mio_id, "code": workflow_code, "p": purpose, "w": workflow_id,
                 "o": json.dumps(overrides)},
            )
            s.commit()
            return True

    def detach(self, mio_id: uuid.UUID, workflow_id: uuid.UUID) -> bool:
        with self._session_factory() as s:
            res = s.execute(
                text("DELETE FROM catalog.mio_workflow WHERE mio_id = :m AND workflow_id = :w"),
                {"m": mio_id, "w": workflow_id},
            )
            s.commit()
            return res.rowcount > 0


class MioWriteDaoImpl(_BaseDao, IMioWriteDao):
    def domain_id_for_code(self, tenant_id: str, domain_code: str) -> uuid.UUID | None:
        with self._session_factory() as s:
            return s.scalar(
                text("SELECT domain_id FROM catalog.domain WHERE code = :c AND tenant_id = :t"),
                {"c": domain_code, "t": tenant_id},
            )

    def create(self, tenant_id: str, req: CreateMioReq) -> uuid.UUID:
        domain_id = self.domain_id_for_code(tenant_id, req.domain_code)
        if domain_id is None:
            raise ValueError(f"unknown domain: {req.domain_code}")
        mio_id = uuid.uuid4()
        with self._session_factory() as s:
            # state defaults to 'draft' and validations to {}: a new MIO has been checked
            # by nothing, and validations_pass is false until something checks it.
            s.execute(
                text(
                    "INSERT INTO catalog.mio "
                    "  (mio_id, domain_id, code, name, description, tech_stack, tenant_id) "
                    "VALUES (:id, :d, :c, :n, :desc, :t, :tenant)"
                ),
                {"id": mio_id, "d": domain_id, "c": req.code, "n": req.name,
                 "desc": req.description, "t": req.tech_stack, "tenant": tenant_id},
            )
            for ds in req.dataset_ids:
                s.execute(
                    text("INSERT INTO catalog.mio_dataset (mio_id, dataset_id, role) "
                         "VALUES (:m, :d, 'input') ON CONFLICT DO NOTHING"),
                    {"m": mio_id, "d": ds},
                )
            s.commit()
        return mio_id

    def update(self, tenant_id: str, req: UpdateMioReq) -> bool:
        sets, params = [], {"id": req.mio_id, "t": tenant_id}
        for field in ("name", "description", "tech_stack", "state", "pinned_version"):
            value = getattr(req, field)
            if value is not None:
                sets.append(f"{field} = :{field}")
                params[field] = value
        if not sets:
            return False
        sets.append("updated_at = now()")
        with self._session_factory() as s:
            res = s.execute(
                text(f"UPDATE catalog.mio SET {', '.join(sets)} "
                     f"WHERE mio_id = :id AND tenant_id = :t"),
                params,
            )
            s.commit()
            return res.rowcount > 0

    def delete(self, tenant_id: str, mio_id: uuid.UUID) -> bool:
        with self._session_factory() as s:
            res = s.execute(
                text("DELETE FROM catalog.mio WHERE mio_id = :id AND tenant_id = :t"),
                {"id": mio_id, "t": tenant_id},
            )
            s.commit()
            return res.rowcount > 0

    def get_overview(self, tenant_id: str, mio_id: uuid.UUID) -> MioDto | None:
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT * FROM catalog.mio_overview WHERE mio_id = :id AND tenant_id = :t"),
                {"id": mio_id, "t": tenant_id},
            ).mappings().first()
            if row is None:
                return None
            fields = set(MioDto.model_fields)
            return MioDto.model_validate({k: v for k, v in dict(row).items() if k in fields})


class InvocationDaoImpl(_BaseDao, IInvocationDao):
    def record_exec(
        self, tenant_id: str, env: str, trace_id: str, mio_id: uuid.UUID,
        workflow_code: str, input_data: dict[str, Any], requested_by: str | None,
        idempotency_key: str | None,
    ) -> tuple[uuid.UUID, str]:
        import json

        with self._session_factory() as s:
            # An invocation needs an instance to hang off. Reuse the MIO's historical
            # instance, or create one: an execution with no instance would be an orphan
            # that no drill-down can reach.
            instance_id = s.scalar(
                text(
                    "SELECT data_instance_id FROM catalog.data_instance "
                    "WHERE mio_id = :m AND kind = 'historical' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"m": mio_id},
            )
            if instance_id is None:
                instance_id = uuid.uuid4()
                s.execute(
                    text(
                        "INSERT INTO catalog.data_instance "
                        "  (data_instance_id, mio_id, kind, label, state, tenant_id) "
                        "VALUES (:i, :m, 'historical', :l, 'active', :t)"
                    ),
                    {"i": instance_id, "m": mio_id, "l": f"{workflow_code} run", "t": tenant_id},
                )

            exec_id = uuid.uuid4()
            s.execute(
                text(
                    "INSERT INTO catalog.data_instance_exec "
                    "  (data_instance_exec_id, data_instance_id, status, input_data_json, "
                    "   wf_execs_json, trace_id, tenant_id, env, requested_by) "
                    "VALUES (:e, :i, 'PENDING', CAST(:in AS jsonb), "
                    "        CAST(:wf AS jsonb), :tr, :t, :env, :by)"
                ),
                {"e": exec_id, "i": instance_id,
                 "in": json.dumps([{"workflow": workflow_code, "input": input_data}]),
                 "wf": json.dumps([]), "tr": trace_id, "t": tenant_id, "env": env,
                 "by": requested_by},
            )
            s.commit()
        return exec_id, "PENDING"
