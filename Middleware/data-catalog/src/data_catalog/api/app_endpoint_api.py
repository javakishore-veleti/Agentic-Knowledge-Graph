"""Defining endpoints, and checking they are configured where the code is deployed.

An endpoint declares WHICH environment variable supplies each value; the value itself is
never stored, never returned and never logged (ADR-015).
"""

from __future__ import annotations

import uuid
from typing import Any

from akg_service_core import ValidationError, resolve_endpoint
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from ..common.object_factory import SERVICE_FACTORY
from ..config import settings
from ..service.i_app_endpoint_admin_service import IAppEndpointAdminService

router = APIRouter(prefix=settings.api_prefix, tags=["endpoints"])

ENV_NAME_HINT = "AKG_-prefixed, uppercase, e.g. AKG_AWS_S3_BUCKET"


class CreateAppEndpointReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=63)
    name: str
    tech_stack: str
    env: str
    host: str
    port: int | None = None
    database: str | None = None
    options: dict[str, Any] = {}
    secret_ref: str | None = None
    #: logical key -> environment variable NAME. Never a value.
    config_env: dict[str, str] = {}


class UpdateAppEndpointReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    options: dict[str, Any] | None = None
    secret_ref: str | None = None
    config_env: dict[str, str] | None = None
    is_active: bool | None = None


def _tid(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _svc() -> IAppEndpointAdminService:
    return SERVICE_FACTORY.get(IAppEndpointAdminService)


@router.post("/app-endpoints", status_code=201)
def create_app_endpoint(request: Request, body: CreateAppEndpointReq) -> dict[str, Any]:
    new_id = _svc().create(settings.tenant_id, body.model_dump(), _tid(request))
    return {"app_endpoint_id": str(new_id)}


@router.patch("/app-endpoints/{app_endpoint_id}")
def update_app_endpoint(
    request: Request, app_endpoint_id: uuid.UUID, body: UpdateAppEndpointReq
) -> dict[str, Any]:
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise ValidationError("no updatable fields supplied", _tid(request))
    updated = _svc().update(settings.tenant_id, app_endpoint_id, changes, _tid(request))
    return {"app_endpoint_id": str(app_endpoint_id), "updated": updated}


@router.get("/app-endpoints/{app_endpoint_id}/resolve")
def resolve(request: Request, app_endpoint_id: uuid.UUID) -> dict[str, Any]:
    """Report whether this endpoint is configured *here*.

    Presence only — which variables resolved and which are missing, by name. Returning the
    values would put credentials in an HTTP response, which is the thing the whole design
    avoids. This is what makes "it works locally but not in azure-dev" a one-request
    question.
    """
    ep = _svc().get(settings.tenant_id, app_endpoint_id)
    if not ep:
        raise ValidationError(f"app endpoint {app_endpoint_id} not found", _tid(request))
    resolved = resolve_endpoint(ep.get("code", ""), ep.get("config_env") or {})
    return {
        "app_endpoint_id": str(app_endpoint_id),
        "env": ep.get("env"),
        "tech_stack": ep.get("tech_stack"),
        "declared": ep.get("config_env") or {},
        **resolved.describe(),
    }


@router.get("/app-endpoints/unconfigured")
def unconfigured() -> dict[str, Any]:
    """Active endpoints needing credentials that declare no configuration at all.

    These fail at connect time rather than here, which is far from the cause.
    """
    return {"items": _svc().unconfigured(settings.tenant_id)}
