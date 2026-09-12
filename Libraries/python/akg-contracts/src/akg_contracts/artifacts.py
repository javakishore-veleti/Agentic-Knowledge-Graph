"""Artifact and release manifests.

PRD B 5.2 pins artifacts individually. PRD A 21 additionally requires a *release*
manifest, because a graph, an index and a catalog can each finish at a different time and
nothing otherwise stops a query from mixing incompatible versions. Both are kept
(ADR-001).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ArtifactKind
from .ids import ArtifactVersion


class ValidationReport(BaseModel):
    """Per-layer ground truth: an internal invariant plus a recount from the source.

    An end-to-end score cannot tell you that the thing it improved was the wrong thing,
    which is why every derived structure carries its own recount.
    """

    model_config = ConfigDict(extra="forbid")

    alignment_assert: bool
    source_recount: bool
    notes: str = ""

    @property
    def passed(self) -> bool:
        return self.alignment_assert and self.source_recount


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: ArtifactKind
    version: ArtifactVersion
    source_version: str
    ontology_version: str | None = None
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    checksums: dict[str, str] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    validation: ValidationReport

    @property
    def promotable(self) -> bool:
        return self.validation.passed


class ReleaseManifest(BaseModel):
    """A set of artifact versions proven compatible with each other.

    Serving resolves the active release pointer once per query and carries the resolved
    versions on every downstream call. Promotion sets the pointer atomically; rollback
    sets it back. Nothing is hot-patched.
    """

    model_config = ConfigDict(extra="forbid")

    release: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    graph: ArtifactVersion
    index: ArtifactVersion
    ontology: ArtifactVersion
    calibration: ArtifactVersion
    # Populated by the eval gate. A release with no eval summary must never be pointed at.
    eval_summary: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def gated_by_evaluation(self) -> ReleaseManifest:
        if not self.eval_summary:
            raise ValueError(
                "release manifest requires an eval_summary: promotion is gated on "
                "evaluation (PRD B 5, goal 5)"
            )
        return self
