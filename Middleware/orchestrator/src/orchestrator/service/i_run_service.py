from __future__ import annotations

from abc import ABC, abstractmethod

from ..dtos.run_dtos import (
    GetRunCtx, GetRunResp, ListEnginesResp, ListRunsCtx, ListRunsResp, RunTasksCtx,
    RunTasksResp, StartRunCtx, StartRunResp,
)


class IRunService(ABC):
    @abstractmethod
    def start(self, ctx: StartRunCtx) -> StartRunResp: ...
    @abstractmethod
    def get(self, ctx: GetRunCtx) -> GetRunResp: ...
    @abstractmethod
    def list(self, ctx: ListRunsCtx) -> ListRunsResp: ...
    @abstractmethod
    def tasks(self, ctx: RunTasksCtx) -> RunTasksResp: ...
    @abstractmethod
    def engines(self) -> ListEnginesResp: ...
