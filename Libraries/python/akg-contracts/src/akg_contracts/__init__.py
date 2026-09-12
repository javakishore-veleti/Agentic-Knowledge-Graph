"""akg-contracts: the single source of truth every AKG component compiles against.

Changing anything here is a contract change: it requires a CHANGELOG entry, a semver bump,
and a PR the contracts owner reviews (PRD B 0, M0).
"""

from __future__ import annotations

from .artifacts import ArtifactManifest, ReleaseManifest, ValidationReport
from .enums import (
    ArtifactKind,
    CertificationRoute,
    Classification,
    ConceptRole,
    Disposition,
    Env,
    Label,
    RefusalReason,
)
from .errors import ErrorCode, Problem
from .events import SCHEMA_VERSION, Envelope, Topic
from .ids import ArtifactVersion, ConceptId, DocId, TenantId, TraceId
from .schemas import (
    Answer,
    ArtifactPins,
    Candidate,
    Certification,
    Claim,
    Concept,
    Document,
    Edge,
    Feedback,
    Grounding,
    Posterior,
    Question,
    RetrievalResult,
)

__version__ = "0.1.0"

# The structural gates, in evaluation order. Each is a veto, not a weighted term: a score
# lets a strong signal compensate for irrelevant evidence, a constraint cannot. All five
# are evaluated before the generator is reached, so a structural refusal costs no model
# call. LOW_CONFIDENCE is deliberately absent -- it is the calibrated gate, applied after
# generation by the answer service.
STRUCTURAL_GATES: tuple[RefusalReason, ...] = (
    RefusalReason.NO_ENTRY_POINT,
    RefusalReason.TOO_FEW_CONCEPTS,
    RefusalReason.NO_PATH,
    RefusalReason.NOT_QUOTABLE,
    RefusalReason.ONLY_RETRACTED,
    RefusalReason.NO_EVIDENCE_AS_OF_DATE,
)

__all__ = [
    "SCHEMA_VERSION",
    "STRUCTURAL_GATES",
    "Answer",
    "ArtifactKind",
    "ArtifactManifest",
    "ArtifactPins",
    "ArtifactVersion",
    "Candidate",
    "Certification",
    "CertificationRoute",
    "Claim",
    "Classification",
    "Concept",
    "ConceptId",
    "ConceptRole",
    "Disposition",
    "DocId",
    "Document",
    "Edge",
    "Envelope",
    "Env",
    "ErrorCode",
    "Feedback",
    "Grounding",
    "Label",
    "Posterior",
    "Problem",
    "Question",
    "RefusalReason",
    "ReleaseManifest",
    "RetrievalResult",
    "TenantId",
    "Topic",
    "TraceId",
    "ValidationReport",
    "__version__",
]

# Appended: orchestration contracts (ADR-008).
from .enums import ExecutionModel, TechStack, WorkflowStatus  # noqa: E402
from .workflows import WorkflowBatch, WorkflowExecution, WorkflowTrigger  # noqa: E402

__all__ += [
    "ExecutionModel",
    "TechStack",
    "WorkflowBatch",
    "WorkflowExecution",
    "WorkflowStatus",
    "WorkflowTrigger",
]
