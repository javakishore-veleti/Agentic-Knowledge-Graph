"""DTO base classes. These are the only types that cross a package boundary (ADR-010)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReqDto(BaseModel):
    """Inbound. Unknown fields are rejected: a misspelled filter that is silently ignored
    returns a plausible wrong answer, which is worse than an error."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RespDto(BaseModel):
    """Outbound. Built from entities inside the DAO; no ORM object ever reaches here."""

    model_config = ConfigDict(extra="forbid")


class ItemDto(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PageDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    limit: int
    next_cursor: str | None = None
