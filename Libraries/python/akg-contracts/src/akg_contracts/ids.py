"""Identifier types. Stringly-typed ids are how provenance chains silently break."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

# A document's stable identity within a corpus version. For the PubMed reference
# adapter this is the PMID; other adapters mint their own, but it must be stable
# across rebuilds or pinned artifacts stop being comparable.
DocId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]

# An ontology concept's stable identifier (MeSH descriptor UI for the reference
# ontology, e.g. "D000818").
ConceptId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]

# Correlates every hop of one question, from gateway through to the answer event.
TraceId = Annotated[str, Field(min_length=1, max_length=128)]

TenantId = Annotated[str, Field(min_length=1, max_length=128)]

# Artifact version, e.g. "2026.09.12-a3f9c1" (PRD B 5.2).
ArtifactVersion = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
