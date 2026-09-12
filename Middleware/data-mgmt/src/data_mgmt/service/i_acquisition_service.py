from __future__ import annotations

from abc import ABC, abstractmethod

from ..dtos.acquisition_dtos import (
    AcquireDatasetCtx, AcquireDatasetResp, AcquisitionStatusCtx, AcquisitionStatusResp,
)


class IAcquisitionService(ABC):
    @abstractmethod
    def acquire(self, ctx: AcquireDatasetCtx) -> AcquireDatasetResp: ...

    @abstractmethod
    def status(self, ctx: AcquisitionStatusCtx) -> AcquisitionStatusResp: ...
