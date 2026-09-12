"""Acquisition workflows (ADR-010)."""

from __future__ import annotations

from akg_service_core import ITask, IWorkflow

from ..tasks.acquisition_tasks import (
    BuildAcquireRespTask, BuildStatusRespTask, ClaimEndpointTask, FetchStatusTask,
    MintExecIdTask, TriggerAirflowTask,
)


class AcquireDatasetWf(IWorkflow):
    """Mint, claim, trigger, respond.

    Claiming before triggering is what makes "do not re-download what we already have"
    true under concurrency: the claim is the decision, and only the winner triggers.
    """

    name = "acquire_dataset_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (
            MintExecIdTask(), ClaimEndpointTask(), TriggerAirflowTask(),
            BuildAcquireRespTask(),
        )

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks


class AcquisitionStatusWf(IWorkflow):
    name = "acquisition_status_wf"

    def __init__(self) -> None:
        self._tasks: tuple[ITask, ...] = (FetchStatusTask(), BuildStatusRespTask())

    def tasks(self) -> tuple[ITask, ...]:
        return self._tasks
