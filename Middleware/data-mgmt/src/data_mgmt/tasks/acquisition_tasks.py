"""Acquisition tasks (ADR-010, ADR-013). Stateless singletons."""

from __future__ import annotations

import uuid

from akg_service_core import SERVICE_FACTORY, BaseCtx, ITask, NotFoundError

from ..config import settings
from ..dtos.acquisition_dtos import AcquireDatasetResp, AcquisitionStatusResp
from ..integration.i_clients import ICatalogClient, IOrchestratorClient


class MintExecIdTask(ITask):
    """One id for the whole acquisition, minted before anything is claimed.

    It becomes the orchestrator's idempotency key, so a retried submission returns the
    run that already exists instead of starting a second one over the same data.
    """

    name = "mint_exec_id"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.scratch["exec_id"] = uuid.uuid4()
        ctx.scratch["run_key"] = f"akg__{ctx.scratch['exec_id']}"


class ClaimEndpointTask(ITask):
    """Ask the catalog to claim it. The catalog decides, not this service.

    A claim refused is a normal outcome: `already_available` means the data is there and
    re-downloading it would be waste, which is the entire point of asking first.
    """

    name = "claim_endpoint"

    def execute(self, ctx: BaseCtx) -> None:
        client: ICatalogClient = SERVICE_FACTORY.get(ICatalogClient)
        claimed, reason = client.claim(
            ctx.req.dataset_endpoint_id, ctx.scratch["exec_id"], ctx.req.force, ctx.trace_id
        )
        ctx.scratch["claimed"] = claimed
        ctx.scratch["reason"] = reason
        if not claimed and reason == "not_found":
            raise NotFoundError("dataset_endpoint", str(ctx.req.dataset_endpoint_id), ctx.trace_id)


class TriggerWorkflowTask(ITask):
    """Ask the orchestrator to run it, and return.

    Never waits: the run reports its own outcome to the catalog. If the submit fails after
    a successful claim the claim is released immediately -- otherwise the endpoint sits
    RUNNING until the stuck-sync sweeper notices hours later.
    """

    name = "trigger_workflow"

    def should_run(self, ctx: BaseCtx) -> bool:
        return bool(ctx.scratch.get("claimed"))

    def execute(self, ctx: BaseCtx) -> None:
        orchestrator: IOrchestratorClient = SERVICE_FACTORY.get(IOrchestratorClient)
        catalog: ICatalogClient = SERVICE_FACTORY.get(ICatalogClient)

        conf = {
            "dataset_endpoint_id": str(ctx.req.dataset_endpoint_id),
            "exec_id": str(ctx.scratch["exec_id"]),
            "trace_id": ctx.trace_id,
            "tenant_id": ctx.tenant_id,
            # The run calls back here. Reachable FROM wherever the engine executes, which
            # is not the same as reachable from this process.
            "catalog_callback_url": settings.catalog_callback_url,
            **ctx.req.params,
        }
        handle = orchestrator.start(
            engine=settings.acquisition_engine,
            workflow_ref=settings.acquisition_workflow_ref,
            run_key=ctx.scratch["run_key"],
            conf=conf,
            # Ties the run back to the endpoint without the orchestrator needing to know
            # what a dataset endpoint is.
            caller_ref={"dataset_endpoint_id": str(ctx.req.dataset_endpoint_id),
                        "service": "data-mgmt"},
            trace_id=ctx.trace_id,
        )

        if handle is None or not handle.accepted:
            reason = "orchestrator_unavailable" if handle is None else handle.reason
            catalog.release(
                ctx.req.dataset_endpoint_id, "FAILED",
                {"detail": f"the workflow was not started: {reason}"}, ctx.trace_id,
            )
            ctx.scratch["claimed"] = False
            ctx.scratch["reason"] = reason
            ctx.scratch["run_id"] = None
        else:
            ctx.scratch["run_id"] = handle.run_id


class BuildAcquireRespTask(ITask):
    name = "build_acquire_resp"

    def execute(self, ctx: BaseCtx) -> None:
        started = bool(ctx.scratch.get("claimed"))
        ctx.resp = AcquireDatasetResp(
            dataset_endpoint_id=ctx.req.dataset_endpoint_id,
            started=started,
            reason=ctx.scratch.get("reason", "unknown"),
            exec_id=ctx.scratch["exec_id"] if started else None,
            dag_run_id=ctx.scratch.get("run_id") if started else None,
            state="syncing" if started else None,
            sync_wf_status="RUNNING" if started else None,
        )


class FetchStatusTask(ITask):
    """Catalog state first, the run second.

    The catalog is authoritative for whether the data is there; the run only knows whether
    it finished. Those answer different questions, and a finished run that wrote nothing
    must not read as available.
    """

    name = "fetch_status"

    def execute(self, ctx: BaseCtx) -> None:
        catalog: ICatalogClient = SERVICE_FACTORY.get(ICatalogClient)
        ep = catalog.endpoint(ctx.req.dataset_endpoint_id, ctx.trace_id)
        if ep is None:
            raise NotFoundError("dataset_endpoint", str(ctx.req.dataset_endpoint_id), ctx.trace_id)
        ctx.scratch["endpoint"] = ep

        run_state = None
        run_id = ep.get("sync_wf_ref_id")
        if ep.get("sync_wf_status") == "RUNNING" and run_id:
            orchestrator: IOrchestratorClient = SERVICE_FACTORY.get(IOrchestratorClient)
            run_state = orchestrator.state(str(run_id), ctx.trace_id)
        ctx.scratch["run_state"] = run_state


class BuildStatusRespTask(ITask):
    name = "build_status_resp"

    def execute(self, ctx: BaseCtx) -> None:
        ep = ctx.scratch["endpoint"]
        ctx.resp = AcquisitionStatusResp(
            dataset_endpoint_id=ctx.req.dataset_endpoint_id,
            state=ep.get("state", "unknown"),
            sync_wf_status=ep.get("sync_wf_status"),
            sync_started_at=ep.get("sync_started_at"),
            sync_finished_at=ep.get("sync_finished_at"),
            bytes=int(ep.get("bytes") or 0),
            sync_attempts=int(ep.get("sync_attempts") or 0),
            dag_run_state=ctx.scratch.get("run_state"),
        )
