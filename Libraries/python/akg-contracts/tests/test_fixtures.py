"""Every fixture validates against its schema (PRD B M0 acceptance criterion 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from akg_contracts import (
    Answer,
    ArtifactManifest,
    Candidate,
    Document,
    Envelope,
    Grounding,
    Posterior,
    ReleaseManifest,
    WorkflowExecution,
    WorkflowTrigger,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

CASES = [
    ("document.json", Document),
    ("grounding.json", Grounding),
    ("candidate.json", Candidate),
    ("posterior.json", Posterior),
    ("answer.json", Answer),
    ("answer-refusal.json", Answer),
    ("artifact-manifest.json", ArtifactManifest),
    ("release-manifest.json", ReleaseManifest),
    ("envelope.json", Envelope),
    ("workflow-execution.json", WorkflowExecution),
    ("workflow-trigger.json", WorkflowTrigger),
]


@pytest.mark.parametrize(("name", "model"), CASES, ids=[c[0] for c in CASES])
def test_fixture_validates(name: str, model: type) -> None:
    payload = json.loads((FIXTURES / name).read_text())
    model.model_validate(payload)


@pytest.mark.parametrize(("name", "model"), CASES, ids=[c[0] for c in CASES])
def test_fixture_roundtrips(name: str, model: type) -> None:
    payload = json.loads((FIXTURES / name).read_text())
    obj = model.model_validate(payload)
    # Re-validating a dump must succeed, or a producer cannot replay what it wrote.
    model.model_validate(json.loads(obj.model_dump_json()))


def test_every_fixture_is_covered() -> None:
    on_disk = {p.name for p in FIXTURES.glob("*.json")}
    covered = {name for name, _ in CASES}
    assert on_disk == covered, f"uncovered fixtures: {sorted(on_disk - covered)}"
