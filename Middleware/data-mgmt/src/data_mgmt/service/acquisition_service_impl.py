from __future__ import annotations

from akg_service_core import IWorkflow

from ..dtos.acquisition_dtos import (
    AcquireDatasetCtx, AcquireDatasetResp, AcquisitionStatusCtx, AcquisitionStatusResp,
)
from ..wf.acquisition_wf import AcquireDatasetWf, AcquisitionStatusWf
from .i_acquisition_service import IAcquisitionService


class AcquisitionServiceImpl(IAcquisitionService):
    def __init__(self) -> None:
        self._acquire_wf: IWorkflow = AcquireDatasetWf()
        self._status_wf: IWorkflow = AcquisitionStatusWf()

    def acquire(self, ctx: AcquireDatasetCtx) -> AcquireDatasetResp:
        return self._acquire_wf.run(ctx).require_resp()

    def status(self, ctx: AcquisitionStatusCtx) -> AcquisitionStatusResp:
        return self._status_wf.run(ctx).require_resp()
