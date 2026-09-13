"""Run lifecycle. Stateless: every fact comes from the DAO or an adapter."""

from __future__ import annotations

import uuid
from typing import Any

from akg_service_core import DAO_FACTORY, NotFoundError, ValidationError

from ..dao.i_run_dao import IRunDao
from ..dtos.run_dtos import (
    EngineDto, GetRunCtx, GetRunResp, ListEnginesResp, ListRunsCtx, ListRunsResp, RunDto,
    RunTaskDto, RunTasksCtx, RunTasksResp, StartRunCtx, StartRunResp, TERMINAL_STATES,
)
from ..integration.i_engine import EngineError, IEngineAdapter
from .i_run_service import IRunService


class RunServiceImpl(IRunService):
    def __init__(self, adapters: dict[str, IEngineAdapter]) -> None:
        # Injected rather than looked up globally so a test can pass a fake engine
        # without touching a factory.
        self._adapters = adapters

    def _adapter(self, engine: str, trace_id: str) -> IEngineAdapter:
        adapter = self._adapters.get(engine)
        if adapter is None:
            raise ValidationError(
                f"unknown engine {engine!r}. Known engines: "
                f"{', '.join(sorted(self._adapters)) or 'none'}",
                trace_id,
            )
        return adapter

    @staticmethod
    def _to_dto(row: dict[str, Any]) -> RunDto:
        return RunDto(**{k: row.get(k) for k in RunDto.model_fields})

    def start(self, ctx: StartRunCtx) -> StartRunResp:
        req = ctx.req
        adapter = self._adapter(req.engine, ctx.trace_id)
        dao: IRunDao = DAO_FACTORY.get(IRunDao)

        run_id = uuid.uuid4()
        row, inserted = dao.insert_or_get({
            "run_id": run_id,
            "engine": req.engine,
            "workflow_ref": req.workflow_ref,
            "run_key": req.run_key,
            "conf": req.conf,
            "caller_ref": req.caller_ref,
            "trace_id": ctx.trace_id,
            "tenant_id": ctx.tenant_id,
        })

        if not inserted:
            # Same idempotency key, so the caller is retrying. Hand back the run that
            # already exists: starting a second one would duplicate work that moves data.
            if not row:
                raise ValidationError(
                    "the run could not be recorded and no existing run matched the key",
                    ctx.trace_id)
            return StartRunResp(run=self._to_dto(row), started=False,
                                reason="already_started")

        # The row exists before the engine is touched, so a crash between the two leaves a
        # queued run to reconcile rather than a workflow nobody recorded.
        try:
            result = adapter.start(req.workflow_ref, str(run_id), req.conf, ctx.trace_id)
        except EngineError as exc:
            failed = dao.update_engine_run(
                run_id, None, "failed", None,
                {"engine": exc.engine, "reason": exc.reason, "status": exc.status})
            return StartRunResp(
                run=self._to_dto(failed or row), started=False,
                reason=f"engine_refused: {exc.reason}")

        updated = dao.update_engine_run(
            run_id, result.engine_run_id, result.state, result.engine_state, None)
        return StartRunResp(run=self._to_dto(updated or row), started=True,
                            reason="started")

    def get(self, ctx: GetRunCtx) -> GetRunResp:
        dao: IRunDao = DAO_FACTORY.get(IRunDao)
        row = dao.get(ctx.tenant_id, ctx.req.run_id)
        if row is None:
            raise NotFoundError("run", str(ctx.req.run_id), ctx.trace_id)

        # A terminal run never changes again, so asking the engine is pure cost.
        if not ctx.req.refresh or row["state"] in TERMINAL_STATES or not row.get("engine_run_id"):
            return GetRunResp(run=self._to_dto(row))

        adapter = self._adapter(row["engine"], ctx.trace_id)
        try:
            live = adapter.get(row["workflow_ref"], row["engine_run_id"])
        except EngineError:
            # The stored row is still the best answer available; a poll that cannot reach
            # the engine is not evidence the run changed.
            return GetRunResp(run=self._to_dto(row))

        if live.state != row["state"] or live.engine_state != row.get("engine_state"):
            error = live.error
            if live.state == "failed" and not error:
                error = {"engine": adapter.name,
                         "reason": live.engine_state or "the engine reported failure"}
            row = dao.update_engine_run(
                ctx.req.run_id, live.engine_run_id, live.state, live.engine_state, error
            ) or row
        return GetRunResp(run=self._to_dto(row))

    def list(self, ctx: ListRunsCtx) -> ListRunsResp:
        dao: IRunDao = DAO_FACTORY.get(IRunDao)
        rows, cursor = dao.list(
            ctx.tenant_id, ctx.req.engine, ctx.req.workflow_ref, ctx.req.state,
            min(max(ctx.req.limit, 1), 200), ctx.req.cursor,
        )
        return ListRunsResp(items=[self._to_dto(r) for r in rows], next_cursor=cursor)

    def tasks(self, ctx: RunTasksCtx) -> RunTasksResp:
        dao: IRunDao = DAO_FACTORY.get(IRunDao)
        row = dao.get(ctx.tenant_id, ctx.req.run_id)
        if row is None:
            raise NotFoundError("run", str(ctx.req.run_id), ctx.trace_id)
        if not row.get("engine_run_id"):
            return RunTasksResp(run_id=ctx.req.run_id, items=[])

        adapter = self._adapter(row["engine"], ctx.trace_id)
        try:
            tasks = adapter.tasks(row["workflow_ref"], row["engine_run_id"])
        except EngineError as exc:
            raise ValidationError(f"{exc.engine}: {exc.reason}", ctx.trace_id) from exc
        return RunTasksResp(
            run_id=ctx.req.run_id,
            items=[RunTaskDto(**t._asdict()) for t in tasks],
        )

    def engines(self) -> ListEnginesResp:
        items = []
        for name, adapter in sorted(self._adapters.items()):
            ok, detail = adapter.available()
            items.append(EngineDto(
                engine=name, available=ok, supports_tasks=adapter.supports_tasks,
                supports_cancel=adapter.supports_cancel, detail=detail,
            ))
        return ListEnginesResp(items=items)
