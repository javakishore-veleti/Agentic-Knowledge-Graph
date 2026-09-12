from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from .catalog_dao_impl import _BaseDao
from .i_app_endpoint_admin_dao import IAppEndpointAdminDao

_JSON_COLUMNS = {"options", "config_env"}
_UPDATABLE = {"name", "host", "port", "database", "options", "secret_ref",
              "config_env", "is_active"}


class AppEndpointAdminDaoImpl(_BaseDao, IAppEndpointAdminDao):
    @staticmethod
    def _jsonable(row: Any) -> dict[str, Any]:
        return {
            k: (str(v) if isinstance(v, uuid.UUID)
                else v.isoformat() if hasattr(v, "isoformat") else v)
            for k, v in dict(row).items()
        }

    def create(self, tenant_id: str, data: dict[str, Any]) -> uuid.UUID:
        new_id = uuid.uuid4()
        with self._session_factory() as s:
            s.execute(
                text(
                    "INSERT INTO catalog.app_endpoint "
                    "  (app_endpoint_id, code, name, tech_stack, env, host, port, "
                    "   database, options, secret_ref, config_env, tenant_id) "
                    "VALUES (:id, :code, :name, :tech, :env, :host, :port, :db, "
                    "        CAST(:options AS jsonb), :secret, CAST(:cfg AS jsonb), :t)"
                ),
                {"id": new_id, "code": data["code"], "name": data["name"],
                 "tech": data["tech_stack"], "env": data["env"], "host": data["host"],
                 "port": data.get("port"), "db": data.get("database"),
                 "options": json.dumps(data.get("options") or {}),
                 "secret": data.get("secret_ref"),
                 "cfg": json.dumps(data.get("config_env") or {}), "t": tenant_id},
            )
            s.commit()
        return new_id

    def update(self, tenant_id: str, endpoint_id: uuid.UUID, changes: dict[str, Any]) -> bool:
        sets, params = [], {"id": endpoint_id, "t": tenant_id}
        for key, value in changes.items():
            if key not in _UPDATABLE:
                continue
            if key in _JSON_COLUMNS:
                sets.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value)
            else:
                sets.append(f"{key} = :{key}")
                params[key] = value
        if not sets:
            return False
        with self._session_factory() as s:
            res = s.execute(
                text(f"UPDATE catalog.app_endpoint SET {', '.join(sets)} "
                     f"WHERE app_endpoint_id = :id AND tenant_id = :t"),
                params,
            )
            s.commit()
            return res.rowcount > 0

    def get(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict[str, Any] | None:
        with self._session_factory() as s:
            row = s.execute(
                text("SELECT * FROM catalog.app_endpoint "
                     "WHERE app_endpoint_id = :id AND tenant_id = :t"),
                {"id": endpoint_id, "t": tenant_id},
            ).mappings().first()
            return self._jsonable(row) if row else None

    def unconfigured(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as s:
            rows = s.execute(
                text("SELECT * FROM catalog.app_endpoint_unconfigured")
            ).mappings().all()
            return [self._jsonable(r) for r in rows]
