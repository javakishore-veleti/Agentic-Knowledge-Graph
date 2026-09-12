"""Domain schemas (PRD B M0).

The invariants enforced here are the ones the reference study broke silently:
citations that named documents outside the admitted set, and certification used as a
filter. A validator is cheaper than a postmortem.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import CertificationRoute, ConceptRole, Disposition, Label, RefusalReason
from .ids import ArtifactVersion, ConceptId, DocId


class Strict(BaseModel):
    """Reject unknown fields on *inbound* domain objects.

    Note the asymmetry with events: consumers must tolerate unknown optional fields
    (PRD A 11.5) because a producer may be ahead of them. Domain objects inside one
    service have no such excuse.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class Concept(Strict):
    concept_id: ConceptId
    name: str
    # MeSH check tags (Humans, Female, Adult, ...) annotate almost everything and
    # destroy co-annotation precision. The grounder excludes them; the flag has to
    # live on the concept so every consumer applies the same rule.
    is_check_tag: bool = False
    ancestors: tuple[ConceptId, ...] = ()


class Document(Strict):
    doc_id: DocId
    title: str
    # Absent when the source ships metadata without an abstract. Such a document is
    # retrievable but not quotable, which is what the not_quotable gate detects.
    abstract: str | None = None
    published: date | None = None
    retracted: bool = False
    concepts: tuple[ConceptId, ...] = ()
    major_concepts: tuple[ConceptId, ...] = ()

    @property
    def quotable(self) -> bool:
        return bool(self.abstract and self.abstract.strip())

    @model_validator(mode="after")
    def major_concepts_are_concepts(self) -> Document:
        # The alignment assert. In the study a major-topic misalignment went unnoticed
        # and was worth real accuracy; test_major_topic_alignment recounts it from the
        # source, and this catches the in-memory case.
        stray = set(self.major_concepts) - set(self.concepts)
        if stray:
            raise ValueError(f"major_concepts not in concepts: {sorted(stray)}")
        return self


class Edge(Strict):
    """A directed, typed edge. Built from publisher-supplied structure, zero model calls."""

    src: DocId
    dst: DocId
    family: str = Field(min_length=1)


class Grounding(Strict):
    """Question -> concepts with roles. Deterministic; no model in this path."""

    concepts: tuple[ConceptId, ...]
    roles: dict[ConceptId, ConceptRole]
    as_of: date | None = None

    @model_validator(mode="after")
    def every_concept_has_a_role(self) -> Grounding:
        missing = set(self.concepts) - set(self.roles)
        if missing:
            raise ValueError(f"concepts without a role: {sorted(missing)}")
        return self

    @property
    def bridges(self) -> tuple[ConceptId, ...]:
        return tuple(c for c in self.concepts if self.roles[c] is ConceptRole.BRIDGE)


class Certification(Strict):
    """Graph annotation on a candidate. Never an admission decision."""

    route: CertificationRoute
    reason: str = ""
    path: tuple[DocId, ...] = ()


class Candidate(Strict):
    """A retrieved document with its scores and its graph annotation."""

    doc_id: DocId
    dense_score: float
    rerank_score: float | None = None
    certification: Certification | None = None

    @property
    def score(self) -> float:
        # Rerank wins when present. Certification is deliberately absent from this
        # expression: it annotates, it does not rank.
        return self.rerank_score if self.rerank_score is not None else self.dense_score


class Posterior(Strict):
    """The generator's label distribution over a single passage.

    Scored against the top-1 document. Marginalising over many documents dropped
    accuracy from 82% to 45%, so k is a swept option, never a default behaviour.
    """

    doc_id: DocId
    probabilities: dict[Label, float]

    @model_validator(mode="after")
    def normalised_and_complete(self) -> Posterior:
        missing = set(Label) - set(self.probabilities)
        if missing:
            raise ValueError(f"posterior missing labels: {sorted(m.value for m in missing)}")
        total = sum(self.probabilities.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"posterior does not sum to 1: {total}")
        return self

    @property
    def argmax(self) -> Label:
        return max(self.probabilities, key=lambda k: self.probabilities[k])

    @property
    def confidence(self) -> float:
        return max(self.probabilities.values())


class Claim(Strict):
    """One atomic assertion and the single source it was verified against.

    Verification scores a claim against one best source. Concatenating passages made
    the verifier return 0.97 neutral and refuse true claims.
    """

    text: str = Field(min_length=1)
    source: DocId
    entailment: float | None = None


class ArtifactPins(Strict):
    """Exactly which immutable artifacts produced this answer."""

    graph: ArtifactVersion
    index: ArtifactVersion
    ontology: ArtifactVersion
    calibration: ArtifactVersion


class Answer(Strict):
    """The rendered result, admitted evidence, and the disposition.

    Two invariants are enforced rather than tested downstream:
      1. Every citation names a document in the admitted set.
      2. ANSWER requires cited evidence; REFUSE requires a reason.
    """

    disposition: Disposition
    admitted: tuple[DocId, ...]
    prose: str | None = None
    label: Label | None = None
    claims: tuple[Claim, ...] = ()
    citations: tuple[DocId, ...] = ()
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    refusal_reason: RefusalReason | None = None
    pins: ArtifactPins | None = None

    @model_validator(mode="after")
    def citations_are_admitted(self) -> Answer:
        unadmitted = set(self.citations) - set(self.admitted)
        if unadmitted:
            raise ValueError(f"citations not in admitted set: {sorted(unadmitted)}")
        stray = {c.source for c in self.claims} - set(self.admitted)
        if stray:
            raise ValueError(f"claim sources not in admitted set: {sorted(stray)}")
        return self

    @model_validator(mode="after")
    def disposition_is_coherent(self) -> Answer:
        if self.disposition is Disposition.ANSWER:
            if not self.citations:
                raise ValueError("ANSWER requires at least one citation")
            if self.refusal_reason is not None:
                raise ValueError("ANSWER cannot carry a refusal_reason")
        else:
            if self.refusal_reason is None:
                raise ValueError(f"{self.disposition} requires a refusal_reason")
        return self


class RetrievalResult(Strict):
    """Emitted on `retrieval.completed`, and the input the answer service scores."""

    grounding: Grounding
    candidates: tuple[Candidate, ...]
    gates_failed: tuple[RefusalReason, ...] = ()
    took_ms: float | None = None

    @property
    def structurally_refused(self) -> bool:
        return bool(self.gates_failed)


class Question(Strict):
    text: str = Field(min_length=1)
    as_of: date | None = None
    k: int = Field(default=16, ge=1, le=256)
    want_prose: bool = False


class Feedback(Strict):
    answer_id: str
    correct: bool | None = None
    note: str = ""
    submitted_at: datetime | None = None
