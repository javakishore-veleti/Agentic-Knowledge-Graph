from __future__ import annotations

from abc import ABC, abstractmethod

from ..dtos.purpose_dtos import CreatePurposeReq, ListPurposesReq, PurposeDto, UpdatePurposeReq


class IPurposeDao(ABC):
    @abstractmethod
    def list(self, req: ListPurposesReq, limit: int) -> tuple[int, list[PurposeDto]]: ...

    @abstractmethod
    def get(self, purpose_code: str) -> PurposeDto | None: ...

    @abstractmethod
    def create(self, req: CreatePurposeReq) -> PurposeDto: ...

    @abstractmethod
    def update(self, req: UpdatePurposeReq) -> PurposeDto | None: ...

    @abstractmethod
    def delete(self, purpose_code: str) -> bool: ...

    @abstractmethod
    def workflow_count(self, purpose_code: str) -> int: ...
