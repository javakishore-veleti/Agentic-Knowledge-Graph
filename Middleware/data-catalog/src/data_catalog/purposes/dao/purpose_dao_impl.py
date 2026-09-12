"""The only SQL for purposes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dtos.purpose_dtos import CreatePurposeReq, ListPurposesReq, PurposeDto, UpdatePurposeReq
from .i_purpose_dao import IPurposeDao

SessionFactory = Callable[[], Session]

_SELECT = (
    "SELECT p.purpose_code, p.name, p.description, p.sort_order, p.is_active, "
    "       p.is_system, "
    "       (SELECT count(*) FROM catalog.workflow w WHERE w.purpose = p.purpose_code) "
    "         AS workflow_count "
    "FROM catalog.purpose p"
)


class PurposeDaoImpl(IPurposeDao):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def list(self, req: ListPurposesReq, limit: int) -> tuple[int, list[PurposeDto]]:
        clauses, params = ["true"], {"lim": limit}
        if req.active_only:
            clauses.append("p.is_active")
        if req.q:
            clauses.append("(lower(p.purpose_code) LIKE :q OR lower(p.name) LIKE :q)")
            params["q"] = f"%{req.q.lower()}%"
        where = " AND ".join(clauses)
        with self._session_factory() as s:
            total = s.scalar(
                text(f"SELECT count(*) FROM catalog.purpose p WHERE {where}"), params) or 0
            rows = s.execute(
                text(f"{_SELECT} WHERE {where} ORDER BY p.sort_order, p.name LIMIT :lim"),
                params,
            ).mappings().all()
        return total, [PurposeDto.model_validate(dict(r)) for r in rows]

    def get(self, purpose_code: str) -> PurposeDto | None:
        with self._session_factory() as s:
            row = s.execute(text(f"{_SELECT} WHERE p.purpose_code = :c"),
                            {"c": purpose_code}).mappings().first()
        return PurposeDto.model_validate(dict(row)) if row else None

    def create(self, req: CreatePurposeReq) -> PurposeDto:
        with self._session_factory() as s:
            s.execute(
                text("INSERT INTO catalog.purpose "
                     "  (purpose_code, name, description, sort_order, is_system) "
                     "VALUES (:c, :n, :d, :o, false)"),
                {"c": req.purpose_code, "n": req.name, "d": req.description,
                 "o": req.sort_order},
            )
            s.commit()
        created = self.get(req.purpose_code)
        assert created is not None  # just inserted in the same connection pool
        return created

    def update(self, req: UpdatePurposeReq) -> PurposeDto | None:
        sets, params = [], {"c": req.purpose_code}
        for field in ("name", "description", "sort_order", "is_active"):
            value = getattr(req, field)
            if value is not None:
                sets.append(f"{field} = :{field}")
                params[field] = value
        if not sets:
            return None
        with self._session_factory() as s:
            res = s.execute(
                text(f"UPDATE catalog.purpose SET {', '.join(sets)} WHERE purpose_code = :c"),
                params,
            )
            s.commit()
            if res.rowcount == 0:
                return None
        return self.get(req.purpose_code)

    def delete(self, purpose_code: str) -> bool:
        # A system purpose is refused by a trigger, and a purpose still referenced by a
        # workflow by the foreign key. Both surface as exceptions the service translates.
        with self._session_factory() as s:
            res = s.execute(text("DELETE FROM catalog.purpose WHERE purpose_code = :c"),
                            {"c": purpose_code})
            s.commit()
            return res.rowcount > 0

    def workflow_count(self, purpose_code: str) -> int:
        with self._session_factory() as s:
            return s.scalar(
                text("SELECT count(*) FROM catalog.workflow WHERE purpose = :c"),
                {"c": purpose_code}) or 0
