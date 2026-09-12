"""Purpose rules.

Deletion is the interesting one: a purpose referenced by a workflow, or shipped with the
product, cannot go. Both are enforced in the database -- a foreign key and a trigger -- and
both surface here as a message naming the reason rather than a driver error naming a
constraint.
"""

from __future__ import annotations

from akg_service_core import NotFoundError, ValidationError, clamp_limit

from ...common.object_factory import DAO_FACTORY
from ..dao.i_purpose_dao import IPurposeDao
from ..dtos.purpose_dtos import (
    CreatePurposeCtx, CreatePurposeResp, DeletePurposeCtx, DeletePurposeResp,
    ListPurposesCtx, ListPurposesResp, UpdatePurposeCtx, UpdatePurposeResp,
)
from .i_purpose_service import IPurposeService


class PurposeServiceImpl(IPurposeService):
    def list(self, ctx: ListPurposesCtx) -> ListPurposesResp:
        dao: IPurposeDao = DAO_FACTORY.get(IPurposeDao)
        total, items = dao.list(ctx.req, clamp_limit(ctx.req.limit))
        return ListPurposesResp(total=total, items=items)

    def create(self, ctx: CreatePurposeCtx) -> CreatePurposeResp:
        dao: IPurposeDao = DAO_FACTORY.get(IPurposeDao)
        if dao.get(ctx.req.purpose_code) is not None:
            raise ValidationError(
                f"purpose {ctx.req.purpose_code!r} already exists", ctx.trace_id)
        return CreatePurposeResp(purpose=dao.create(ctx.req))

    def update(self, ctx: UpdatePurposeCtx) -> UpdatePurposeResp:
        dao: IPurposeDao = DAO_FACTORY.get(IPurposeDao)
        existing = dao.get(ctx.req.purpose_code)
        if existing is None:
            raise NotFoundError("purpose", ctx.req.purpose_code, ctx.trace_id)
        updated = dao.update(ctx.req)
        if updated is None:
            raise ValidationError("no updatable fields supplied", ctx.trace_id)
        return UpdatePurposeResp(purpose=updated)

    def delete(self, ctx: DeletePurposeCtx) -> DeletePurposeResp:
        dao: IPurposeDao = DAO_FACTORY.get(IPurposeDao)
        existing = dao.get(ctx.req.purpose_code)
        if existing is None:
            raise NotFoundError("purpose", ctx.req.purpose_code, ctx.trace_id)
        if existing.is_system:
            raise ValidationError(
                f"purpose {ctx.req.purpose_code!r} ships with the product and cannot be "
                f"deleted; deactivate it instead", ctx.trace_id)
        used = dao.workflow_count(ctx.req.purpose_code)
        if used:
            # Checked here so the message names the count. The foreign key would refuse it
            # anyway, as a driver error nobody can act on.
            raise ValidationError(
                f"purpose {ctx.req.purpose_code!r} is used by {used} workflow(s); "
                f"reassign them first or deactivate it", ctx.trace_id)
        return DeletePurposeResp(
            purpose_code=ctx.req.purpose_code, deleted=dao.delete(ctx.req.purpose_code))
