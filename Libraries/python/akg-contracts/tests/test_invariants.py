"""The study's silent bugs, as schema-level tests (PRD B 5.5).

Each test here corresponds to a failure that shipped once and was found by measurement
rather than by a test. The point of naming them is that they can never regress quietly.
"""

from __future__ import annotations

import pytest
from akg_contracts import (
    STRUCTURAL_GATES,
    Answer,
    Candidate,
    Certification,
    CertificationRoute,
    Disposition,
    Document,
    Grounding,
    Label,
    Posterior,
    RefusalReason,
    ReleaseManifest,
)
from pydantic import ValidationError

PINS = {
    "graph": "g-1",
    "index": "i-1",
    "ontology": "o-1",
    "calibration": "c-1",
}


def test_major_topic_alignment() -> None:
    """A major descriptor that is not among the document's descriptors is a build bug."""
    with pytest.raises(ValidationError, match="major_concepts not in concepts"):
        Document(doc_id="1", title="t", concepts=("D1",), major_concepts=("D2",))


def test_citation_regex_multi_id() -> None:
    """Citations naming anything outside the admitted set are rejected.

    The original bug was a citation regex that captured only the first id in a
    multi-id bracket, letting the rest through unvalidated.
    """
    with pytest.raises(ValidationError, match="citations not in admitted set"):
        Answer(
            disposition=Disposition.ANSWER,
            admitted=("1",),
            citations=("1", "2"),
            pins=PINS,
        )


def test_verifier_scores_single_source() -> None:
    """A claim carries exactly one source, so concatenation is not expressible.

    Running the entailment verifier over concatenated passages returned 0.97 neutral
    and refused true claims.
    """
    from akg_contracts import Claim

    claim = Claim(text="x", source="1", entailment=0.9)
    assert isinstance(claim.source, str)
    with pytest.raises(ValidationError):
        Claim(text="x", source=["1", "2"], entailment=0.9)  # type: ignore[arg-type]


def test_claim_sources_must_be_admitted() -> None:
    with pytest.raises(ValidationError, match="claim sources not in admitted set"):
        Answer(
            disposition=Disposition.ANSWER,
            admitted=("1",),
            citations=("1",),
            claims=({"text": "x", "source": "9"},),
            pins=PINS,
        )


def test_certification_does_not_affect_ranking() -> None:
    """Certification annotates; it must not enter the score.

    Using it as a hard filter halved coverage with no accuracy gain, and it predicts
    correctness at chance (AUROC 0.50).
    """
    plain = Candidate(doc_id="1", dense_score=0.5)
    certified = Candidate(
        doc_id="1",
        dense_score=0.5,
        certification=Certification(route=CertificationRoute.CO_ANNOTATION),
    )
    uncertified = Candidate(
        doc_id="1",
        dense_score=0.5,
        certification=Certification(route=CertificationRoute.UNCERTIFIED),
    )
    assert plain.score == certified.score == uncertified.score


def test_rerank_supersedes_dense_score() -> None:
    assert Candidate(doc_id="1", dense_score=0.1, rerank_score=0.9).score == 0.9


def test_answer_requires_a_citation() -> None:
    with pytest.raises(ValidationError, match="ANSWER requires at least one citation"):
        Answer(disposition=Disposition.ANSWER, admitted=("1",), pins=PINS)


def test_refusal_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="requires a refusal_reason"):
        Answer(disposition=Disposition.REFUSE, admitted=(), pins=PINS)


def test_answer_cannot_also_refuse() -> None:
    with pytest.raises(ValidationError, match="cannot carry a refusal_reason"):
        Answer(
            disposition=Disposition.ANSWER,
            admitted=("1",),
            citations=("1",),
            refusal_reason=RefusalReason.NO_PATH,
            pins=PINS,
        )


def test_low_confidence_is_not_a_structural_gate() -> None:
    """The five structural gates are vetoes before generation; calibration comes after."""
    assert RefusalReason.LOW_CONFIDENCE not in STRUCTURAL_GATES


def test_posterior_must_be_normalised() -> None:
    with pytest.raises(ValidationError, match="does not sum to 1"):
        Posterior(doc_id="1", probabilities={Label.YES: 0.9, Label.NO: 0.9, Label.MAYBE: 0.1})


def test_posterior_must_cover_every_label() -> None:
    with pytest.raises(ValidationError, match="missing labels"):
        Posterior(doc_id="1", probabilities={Label.YES: 1.0})


def test_release_manifest_requires_eval_summary() -> None:
    """No artifact set is promotable without an evaluation result."""
    with pytest.raises(ValidationError, match="requires an eval_summary"):
        ReleaseManifest(release="r1", graph="g", index="i", ontology="o", calibration="c")


def test_grounding_requires_a_role_for_every_concept() -> None:
    with pytest.raises(ValidationError, match="concepts without a role"):
        Grounding(concepts=("D1", "D2"), roles={"D1": "bridge"})


def test_document_without_abstract_is_not_quotable() -> None:
    """The not_quotable gate exists because retrievable and quotable are different."""
    assert not Document(doc_id="1", title="t").quotable
    assert not Document(doc_id="1", title="t", abstract="   ").quotable
    assert Document(doc_id="1", title="t", abstract="text").quotable


# --- orchestration (ADR-008) -------------------------------------------------------

def _exec(**kw):
    from akg_contracts import TechStack, WorkflowExecution

    base = dict(
        domain="corpus",
        sub_domain="ingest",
        workflow="w",
        tech_stack=TechStack.AIRFLOW,
        trace_id="t",
        tenant_id="tn",
        env="local",
    )
    return WorkflowExecution(**(base | kw))


def test_submitted_execution_requires_an_engine_id() -> None:
    """A row past PENDING with no engine id means we lost track of a real execution."""
    from akg_contracts import WorkflowStatus

    with pytest.raises(ValidationError, match="requires wf_ref_id"):
        _exec(status=WorkflowStatus.RUNNING)


def test_pending_execution_needs_no_engine_id() -> None:
    """The row is written before the engine is called, so a failed submit is visible."""
    from akg_contracts import WorkflowStatus

    assert _exec().status is WorkflowStatus.PENDING


def test_terminal_execution_must_be_finished() -> None:
    from akg_contracts import WorkflowStatus

    with pytest.raises(ValidationError, match="requires finished_at"):
        _exec(status=WorkflowStatus.SUCCEEDED, wf_ref_id="r1")


def test_running_execution_cannot_be_finished() -> None:
    from akg_contracts import WorkflowStatus
    from datetime import UTC, datetime

    with pytest.raises(ValidationError, match="cannot have finished_at"):
        _exec(status=WorkflowStatus.RUNNING, wf_ref_id="r1", finished_at=datetime.now(UTC))


def test_failed_execution_carries_an_error() -> None:
    from akg_contracts import WorkflowStatus
    from datetime import UTC, datetime

    with pytest.raises(ValidationError, match="FAILED requires error"):
        _exec(status=WorkflowStatus.FAILED, wf_ref_id="r1", finished_at=datetime.now(UTC))


def test_trigger_names_no_engine() -> None:
    """The portal must not be able to pick an engine; configuration does that."""
    from akg_contracts import WorkflowTrigger

    assert "tech_stack" not in WorkflowTrigger.model_fields
