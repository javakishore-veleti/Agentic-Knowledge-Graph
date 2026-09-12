"""Event envelope and topic catalogue (PRD A 11.4, PRD B 7).

Topic names and the envelope are identical in every environment except for an optional
prefix, so a consumer written against local Redpanda works unchanged against Event Hubs
or MSK (ADR-005).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

from .enums import Classification, Env
from .ids import TenantId, TraceId

SCHEMA_VERSION = 1


class Topic(StrEnum):
    SOURCE_DELTA = "source.delta"
    ARTIFACT_BUILT = "artifact.built"
    ARTIFACT_PROMOTED = "artifact.promoted"
    ARTIFACT_REJECTED = "artifact.rejected"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    ANSWER_PRODUCED = "answer.produced"
    FEEDBACK_RECEIVED = "feedback.received"
    REBUILD_REQUESTED = "rebuild.requested"


class Envelope(BaseModel):
    """Wraps every message on the bus.

    Unknown fields are *allowed* here by design: a producer may run ahead of a consumer,
    and a consumer that rejects an added optional field turns a compatible change into an
    outage (PRD A 11.5).
    """

    model_config = ConfigDict(extra="allow")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: Topic
    schema_version: int = SCHEMA_VERSION
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str
    trace_id: TraceId
    tenant_id: TenantId
    env: Env
    classification: Classification = Classification.PUBLIC
    # Kafka partition key. Ordering is only guaranteed within a partition, so anything
    # that must be processed in order shares a key -- for document flows, the doc id.
    partition_key: str | None = None
    causation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def topic_name(self, prefix: str | None = None) -> str:
        return f"{prefix}.{self.event_type.value}" if prefix else self.event_type.value

    @classmethod
    def wrap(
        cls,
        event_type: Topic,
        payload: BaseModel | dict[str, Any],
        *,
        producer: str,
        trace_id: str,
        tenant_id: str,
        env: Env,
        classification: Classification = Classification.PUBLIC,
        partition_key: str | None = None,
        causation_id: str | None = None,
    ) -> Self:
        body = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        return cls(
            event_type=event_type,
            payload=body,
            producer=producer,
            trace_id=trace_id,
            tenant_id=tenant_id,
            env=env,
            classification=classification,
            partition_key=partition_key,
            causation_id=causation_id,
        )
