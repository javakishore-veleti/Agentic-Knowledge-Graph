"""Acquisition tasks (ADR-010, ADR-013). Stateless singletons."""

from __future__ import annotations

import uuid

from akg_service_core import SERVICE_FACTORY, BaseCtx, ITask, NotFoundError

from ..config import settings
from ..dtos.acquisition_dtos import AcquireDatasetResp, AcquisitionStatusResp
from ..integration.i_clients import IAirflowClient, ICatalogClient


class MintExecIdTask(ITask):
    """One id for the whole acquisition, minted before anything is claimed.

    The DAG run id derives from it, so a retried submission produces the same run id and
    Airflow's 409 becomes idempotence rather than a duplicate run.
    """

    name = "mint_exec_id"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.scratch["exec_id"] = uuid.uuid4()
        ctx.scratch["dag_run_id"] = f"akg__{ctx.scratch['exec_id']}"


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


class TriggerAirflowTask(ITask):
    """Start the DAG and return. Never waits: the run reports back to the catalog itself.

    If the submit fails after a successful claim, the claim is released immediately --
    otherwise the endpoint sits RUNNING until the stuck-sync sweeper notices hours later.
    """

    name = "trigger_airflow"

    def should_run(self, ctx: BaseCtx) -> bool:
        return bool(ctx.scratch.get("claimed"))

    def execute(self, ctx: BaseCtx) -> None:
        airflow: IAirflowClient = SERVICE_FACTORY.get(IAirflowClient)
        catalog: ICatalogClient = SERVICE_FACTORY.get(ICatalogClient)

        conf = {
            "dataset_endpoint_id": str(ctx.req.dataset_endpoint_id),
            "exec_id": str(ctx.scratch["exec_id"]),
            "trace_id": ctx.trace_id,
            "tenant_id": ctx.tenant_id,
            # The DAG calls back here. Inside Compose this is a service name: Airflow
            # cannot reach this process's localhost.
            "catalog_callback_url": settings.catalog_callback_url,
            **ctx.req.params,
        }
        run_id = airflow.trigger(
            settings.acquisition_dag_id, ctx.scratch["dag_run_id"], conf, ctx.trace_id
        )
        if run_id is None:
            catalog.release(
                ctx.req.dataset_endpoint_id, "FAILED",
                {"detail": "airflow did not accept the dag run"}, ctx.trace_id,
            )
            ctx.scratch["claimed"] = False
            ctx.scratch["reason"] = "airflow_unavailable"
            ctx.scratch["dag_run_id"] = None
        else:
            ctx.scratch["dag_run_id"] = run_id


class BuildAcquireRespTask(ITask):
    name = "build_acquire_resp"

    def execute(self, ctx: BaseCtx) -> None:
        started = bool(ctx.scratch.get("claimed"))
        ctx.resp = AcquireDatasetResp(
            dataset_endpoint_id=ctx.req.dataset_endpoint_id,
            started=started,
            reason=ctx.scratch.get("reason", "unknown"),
            exec_id=ctx.scratch["exec_id"] if started else None,
            dag_run_id=ctx.scratch.get("dag_run_id") if started else None,
            state="syncing" if started else None,
            sync_wf_status="RUNNING" if started else None,
        )


class FetchStatusTask(ITask):
    """Catalog state first, Airflow second.

    The catalog is authoritative for whether the data is there. Airflow only knows whether
    its run finished, and those answer different questions.
    """

    name = "fetch_status"

    def execute(self, ctx: BaseCtx) -> None:
        catalog: ICatalogClient = SERVICE_FACTORY.get(ICatalogClient)
        ep = catalog.endpoint(ctx.req.dataset_endpoint_id, ctx.trace_id)
        if ep is None:
            raise NotFoundError("dataset_endpoint", str(ctx.req.dataset_endpoint_id), ctx.trace_id)
        ctx.scratch["endpoint"] = ep

        dag_state = None
        exec_id = ep.get("sync_exec_id")
        if ep.get("sync_wf_status") == "RUNNING" and exec_id:
            airflow: IAirflowClient = SERVICE_FACTORY.get(IAirflowClient)
            dag_state = airflow.run_state(settings.acquisition_dag_id, f"akg__{exec_id}")
        ctx.scratch["dag_state"] = dag_state


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
            dag_run_state=ctx.scratch.get("dag_state"),
        )
