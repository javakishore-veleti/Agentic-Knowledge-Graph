"""Tasks for the workflow master, MIO writes and invocation (ADR-010)."""

from __future__ import annotations

from ..common.context import BaseCtx
from ..common.errors import NotFoundError, ValidationError
from ..common.object_factory import DAO_FACTORY, SERVICE_FACTORY
from ..common.paging import encode_cursor
from ..common.task import ITask
from ..dao.i_catalog_dao import IMioDao
from ..dao.i_workflow_dao import IInvocationDao, IMioWriteDao, IWorkflowDao
from ..dtos.base_dtos import PageDto
from ..dtos.catalog_dtos import (
    AttachWorkflowResp, CreateMioResp, DeleteMioResp, InvokeMioWorkflowResp,
    ListMioWorkflowsResp, ListWorkflowsResp, UpdateMioResp, DetachWorkflowResp,
)

# ---------------------------------------------------------------- master list


class CountWorkflowsTask(ITask):
    name = "count_workflows"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IWorkflowDao = DAO_FACTORY.get(IWorkflowDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)


class FetchWorkflowsTask(ITask):
    name = "fetch_workflows"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IWorkflowDao = DAO_FACTORY.get(IWorkflowDao)
        ctx.scratch["items"] = dao.find(
            ctx.tenant_id, ctx.req, ctx.scratch["limit"], ctx.scratch["after"]
        )


class BuildWorkflowsRespTask(ITask):
    name = "build_workflows_resp"

    def execute(self, ctx: BaseCtx) -> None:
        items = ctx.scratch["items"]
        limit = ctx.scratch["limit"]
        nxt = encode_cursor({"after": items[-1].code}) if len(items) == limit and items else None
        ctx.resp = ListWorkflowsResp(
            page=PageDto(total=ctx.scratch["total"], limit=limit, next_cursor=nxt), items=items
        )


# ---------------------------------------------------------------- MIO writes


class ValidateCreateMioTask(ITask):
    """Reject an unknown domain here rather than letting a foreign key do it.

    A constraint violation surfaces as a 500 with a driver message; this is a 400 that
    names the problem.
    """

    name = "validate_create_mio"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioWriteDao = DAO_FACTORY.get(IMioWriteDao)
        if dao.domain_id_for_code(ctx.tenant_id, ctx.req.domain_code) is None:
            raise ValidationError(f"unknown domain: {ctx.req.domain_code}", ctx.trace_id)


class CreateMioTask(ITask):
    name = "create_mio"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioWriteDao = DAO_FACTORY.get(IMioWriteDao)
        ctx.scratch["mio_id"] = dao.create(ctx.tenant_id, ctx.req)


class BuildCreateMioRespTask(ITask):
    name = "build_create_mio_resp"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioWriteDao = DAO_FACTORY.get(IMioWriteDao)
        mio = dao.get_overview(ctx.tenant_id, ctx.scratch["mio_id"])
        if mio is None:
            raise NotFoundError("mio", str(ctx.scratch["mio_id"]), ctx.trace_id)
        ctx.resp = CreateMioResp(mio=mio)


class VerifyMioForWriteTask(ITask):
    name = "verify_mio_for_write"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioDao = DAO_FACTORY.get(IMioDao)
        if not dao.exists(ctx.tenant_id, ctx.req.mio_id):
            raise NotFoundError("mio", str(ctx.req.mio_id), ctx.trace_id)


class ValidateMioTransitionTask(ITask):
    """State rules, checked before the write.

    `mio_live_pinned_ck` already stops a live MIO with no pinned version, but a CHECK
    violation surfaces as a 500 with a driver message. The same rule stated here is a 400
    that names what is missing -- and the constraint stays as the backstop for anything
    that writes without going through this service.
    """

    name = "validate_mio_transition"

    def execute(self, ctx: BaseCtx) -> None:
        if ctx.req.state != "live":
            return
        dao: IMioWriteDao = DAO_FACTORY.get(IMioWriteDao)
        current = dao.get_overview(ctx.tenant_id, ctx.req.mio_id)
        pin = ctx.req.pinned_version or (current.pinned_version if current else None)
        if not pin:
            raise ValidationError(
                "a live MIO must name the artifact version being served: "
                "set pinned_version in the same update",
                ctx.trace_id,
            )
        if current is not None and not current.validations_pass:
            # An unvalidated artifact must not become the one every query resolves.
            raise ValidationError(
                "cannot promote a MIO whose validations do not pass "
                f"({current.validations or 'nothing checked'})",
                ctx.trace_id,
            )


class UpdateMioTask(ITask):
    name = "update_mio"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioWriteDao = DAO_FACTORY.get(IMioWriteDao)
        if not dao.update(ctx.tenant_id, ctx.req):
            raise ValidationError("no updatable fields supplied", ctx.trace_id)
        mio = dao.get_overview(ctx.tenant_id, ctx.req.mio_id)
        if mio is None:
            raise NotFoundError("mio", str(ctx.req.mio_id), ctx.trace_id)
        ctx.resp = UpdateMioResp(mio=mio)


class DeleteMioTask(ITask):
    name = "delete_mio"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioWriteDao = DAO_FACTORY.get(IMioWriteDao)
        ctx.resp = DeleteMioResp(
            mio_id=ctx.req.mio_id, deleted=dao.delete(ctx.tenant_id, ctx.req.mio_id)
        )


class InvalidateMioCachesTask(ITask):
    """Drop the MIO listings after a write.

    Without this a created MIO is invisible until the TTL expires, because the cached
    listing still holds the pre-write result. Both the filtered and unfiltered listings
    go: an unfiltered listing carries no category, so category eviction alone leaves it
    stale.
    """

    name = "invalidate_mio_caches"

    def execute(self, ctx: BaseCtx) -> None:
        from ..cache.i_app_cache_service import IAppCacheService
        from ..wf.catalog_wf import CACHE_MIOS

        cache: IAppCacheService = SERVICE_FACTORY.get(IAppCacheService)
        ctx.scratch["cache_evicted"] = cache.evict_all(CACHE_MIOS, ctx.tenant_id)


# ---------------------------------------------------------------- association


class FetchMioWorkflowsTask(ITask):
    name = "fetch_mio_workflows"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IWorkflowDao = DAO_FACTORY.get(IWorkflowDao)
        ctx.resp = ListMioWorkflowsResp(
            mio_id=ctx.req.mio_id, items=dao.for_mio(ctx.req.mio_id)
        )


class AttachWorkflowTask(ITask):
    name = "attach_workflow"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IWorkflowDao = DAO_FACTORY.get(IWorkflowDao)
        wf = dao.get(ctx.tenant_id, ctx.req.workflow_id)
        if wf is None:
            raise NotFoundError("workflow", str(ctx.req.workflow_id), ctx.trace_id)
        if not wf.is_active:
            # Attaching a deactivated workflow would put a trigger button in the portal
            # that cannot work.
            raise ValidationError(f"workflow {wf.code} is not active", ctx.trace_id)
        ok = dao.attach(
            ctx.req.mio_id, ctx.req.workflow_id, wf.code, ctx.req.purpose,
            ctx.req.param_overrides,
        )
        ctx.resp = AttachWorkflowResp(
            mio_id=ctx.req.mio_id, workflow_id=ctx.req.workflow_id, attached=ok
        )


class DetachWorkflowTask(ITask):
    name = "detach_workflow"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IWorkflowDao = DAO_FACTORY.get(IWorkflowDao)
        ctx.resp = DetachWorkflowResp(
            mio_id=ctx.req.mio_id,
            workflow_id=ctx.req.workflow_id,
            detached=dao.detach(ctx.req.mio_id, ctx.req.workflow_id),
        )


# ---------------------------------------------------------------- invoke


class ResolveWorkflowForInvokeTask(ITask):
    """The workflow must exist, be active, and actually be attached to this MIO.

    Without the last check, any workflow could be run against any MIO by id.
    """

    name = "resolve_workflow_for_invoke"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IWorkflowDao = DAO_FACTORY.get(IWorkflowDao)
        wf = dao.get(ctx.tenant_id, ctx.req.workflow_id)
        if wf is None:
            raise NotFoundError("workflow", str(ctx.req.workflow_id), ctx.trace_id)
        if not wf.is_active:
            raise ValidationError(f"workflow {wf.code} is not active", ctx.trace_id)
        attached = {w.workflow_id for w in dao.for_mio(ctx.req.mio_id) if w.workflow_id}
        if ctx.req.workflow_id not in attached:
            raise ValidationError(
                f"workflow {wf.code} is not attached to this MIO", ctx.trace_id
            )
        ctx.scratch["workflow"] = wf


class ValidateInvokeParamsTask(ITask):
    """Required parameters are checked before anything is recorded, so a rejected
    invocation leaves no PENDING row behind to be mistaken for a stuck submit."""

    name = "validate_invoke_params"

    def execute(self, ctx: BaseCtx) -> None:
        wf = ctx.scratch["workflow"]
        missing = [
            p.label for p in wf.params_json
            if p.required and ctx.req.input_data.get(p.name) in (None, "")
        ]
        if missing:
            raise ValidationError(f"missing required parameters: {', '.join(missing)}", ctx.trace_id)


class RecordInvocationTask(ITask):
    """Write the execution row BEFORE the engine is called (ADR-008)."""

    name = "record_invocation"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IInvocationDao = DAO_FACTORY.get(IInvocationDao)
        exec_id, status = dao.record_exec(
            ctx.tenant_id, ctx.env, ctx.trace_id, ctx.req.mio_id,
            ctx.scratch["workflow"].code, ctx.req.input_data, ctx.requested_by,
            ctx.req.idempotency_key,
        )
        ctx.scratch["exec_id"] = exec_id
        ctx.scratch["status"] = status


class SubmitToOrchestratorTask(ITask):
    """Hand the run to the orchestrator, which owns the engine choice.

    A submit failure leaves the row PENDING with no wf_ref_id, which is exactly how the
    Executions view surfaces "never acknowledged by an engine".
    """

    name = "submit_to_orchestrator"

    def execute(self, ctx: BaseCtx) -> None:
        from ..integration.i_orchestrator_client import IOrchestratorClient

        client: IOrchestratorClient = SERVICE_FACTORY.get(IOrchestratorClient)
        wf_ref_id = None
        if client.available():
            execs = client.execs_for_data_instance_exec(ctx.trace_id, ctx.scratch["exec_id"])
            wf_ref_id = execs[0].wf_ref_id if execs else None
        ctx.scratch["wf_ref_id"] = wf_ref_id


class BuildInvokeRespTask(ITask):
    name = "build_invoke_resp"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.resp = InvokeMioWorkflowResp(
            mio_id=ctx.req.mio_id,
            workflow_id=ctx.req.workflow_id,
            data_instance_exec_id=ctx.scratch["exec_id"],
            status=ctx.scratch["status"],
            wf_ref_id=ctx.scratch.get("wf_ref_id"),
        )
