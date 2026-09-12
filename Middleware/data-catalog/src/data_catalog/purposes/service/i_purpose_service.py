from __future__ import annotations

from abc import ABC, abstractmethod

from ..dtos.purpose_dtos import (
    CreatePurposeCtx, CreatePurposeResp, DeletePurposeCtx, DeletePurposeResp,
    ListPurposesCtx, ListPurposesResp, UpdatePurposeCtx, UpdatePurposeResp,
)


class IPurposeService(ABC):
    @abstractmethod
    def list(self, ctx: ListPurposesCtx) -> ListPurposesResp: ...

    @abstractmethod
    def create(self, ctx: CreatePurposeCtx) -> CreatePurposeResp: ...

    @abstractmethod
    def update(self, ctx: UpdatePurposeCtx) -> UpdatePurposeResp: ...

    @abstractmethod
    def delete(self, ctx: DeletePurposeCtx) -> DeletePurposeResp: ...
