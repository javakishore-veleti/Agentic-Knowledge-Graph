"""RFC 9457 Problem Details, plus the closed set of error codes (PRD A 11.1)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ErrorCode(StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    TENANT_MISMATCH = "tenant_mismatch"
    ARTIFACT_PIN_UNAVAILABLE = "artifact_pin_unavailable"
    ARTIFACT_VERSION_MISMATCH = "artifact_version_mismatch"
    GROUNDING_FAILED = "grounding_failed"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"
    GENERATOR_UNAVAILABLE = "generator_unavailable"
    SCHEMA_INCOMPATIBLE = "schema_incompatible"
    INVALID_REQUEST = "invalid_request"


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int
    code: ErrorCode
    detail: str | None = None
    instance: str | None = None
    trace_id: str | None = None
