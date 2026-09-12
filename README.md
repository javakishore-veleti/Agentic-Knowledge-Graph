# Agentic Knowledge Graph

**A platform that answers questions from a document corpus, shows its evidence for every
sentence, and refuses when it cannot support an answer.**

The interesting problem with retrieval over a large corpus is not accuracy — it is
*entitlement*. A system that answers 90% of questions well and invents the other 10%
without signalling which is which cannot be used where the answer matters. This platform
is built so that every claim resolves to a traceable path in a curated graph, and anything
that cannot is refused rather than generated. Hallucination becomes abstention: a safe,
measurable failure mode.

---

## What it does

**Ask a question, get a cited answer.** Every sentence ends with the sources it used. Each
source opens to show the passage, *why* it was admitted — "directly about both concepts in
your question", "cited by a document about X", "related through the ontology" — and the
path connecting it to the question.

**Refuse, with a reason.** When the system will not answer, it says which of a fixed set
applied: nothing in the question mapped to a known concept; too few specific concepts; no
connecting evidence; only retracted evidence; no evidence as of the date asked for;
confidence too low. Refusals are never blank, and five of the six cost no model call
because they are evaluated before generation.

**Answer as of a date.** Ask how the evidence stood on a past date. Documents published
after it are excluded from both evidence and citations.

**Trace any answer.** Reviewers open an answer by id and see the whole chain: concepts
grounded from the question, every candidate document with its admissibility route, the
model's raw and calibrated confidence against the abstention threshold, and the decision
that followed. Exportable for audit.

**Gate every release.** No graph, index, or calibration is promoted without passing a
held-out evaluation *and* its reference arms — oracle, blind, majority-class and
shuffled-label. Promotion needs the release id typed; rollback is one action. A candidate
with the best accuracy of the batch is still rejected if its shuffled-label arm scores
above chance, because that means the measurement is broken and the headline is meaningless.

**Manage the corpus.** Register datasets and where they live, build artifacts from them,
watch delta volume, and flag retractions so they drop out of citations without waiting for
a rebuild.

---

## How the pieces fit

```
        ask a question                          manage the corpus
              │                                        │
     ┌────────▼────────┐                      ┌─────────▼─────────┐
     │ Customer portal │                      │   Admin portal    │
     └────────┬────────┘                      └─────────┬─────────┘
              │                                         │
     ┌────────▼────────────────────────┐       ┌────────▼─────────┐
     │ grounder → retrieval → generator│       │  DataCatalog API │
     │          → answer               │       │  Data Mgmt API   │
     └────────┬────────────────────────┘       └────────┬─────────┘
              │                                         │
        pinned artifacts  ◄──── eval gate ────  build workflows
        graph · index · ontology · calibration   (Airflow today)
```

Dense vectors retrieve. The provenance graph explains and certifies — it never ranks and
never filters. Calibrated confidence decides whether to answer. The generator only renders
from evidence already admitted, and its citations are validated against that set before
anything reaches a user.

## The catalog model

| | |
|---|---|
| **Domain** | biomedical, enterprise — the top of the hierarchy |
| **Dataset** | source data at an immutable version, plus where it came from and every place it is stored |
| **MIO** | *Managed Informational Object*: the produced artifact — a graph, an index — built from datasets, owning the workflows that maintain it, and able to generate further MIOs |
| **Data instance** | historical, realtime, or CDC (exactly one CDC per MIO) |
| **Execution** | one run, with its inputs, outputs and workflows |

Workflows run on whichever engine configuration chooses — Airflow, Step Functions, EMR,
Data Factory, Kinesis, Camunda — and the portal only offers "invoke" for engines that
actually have a discrete run.

---

## Status

Honest about what exists:

| Working | Designed, not built |
|---|---|
| DataCatalog API · Data Management API | Grounder, retrieval, generator, answer services |
| Admin portal: domains, datasets, MIOs with CRUD, workflow association and invoke, traces, releases, endpoints | Customer portal (bare scaffold) |
| Postgres schema with the invariants enforced as constraints | Azure deployment |
| Local Docker stack · Airflow DAG structure | AWS deployment (phase 2) |

The Traces and Releases screens run on representative data, not a live pipeline.

## Running it

```bash
npm run local:docker:up-all      # Postgres+pgvector, Redpanda, Azurite, Redis, OTel, Airflow
npm run local:catalog:test       # schema + API against a throwaway Postgres
npm run local:ui:start-all       # Admin on :9003, Customer on :9004
npm run local:ui:status-all
```

Decisions and their reasons are in [`docs/adr/`](docs/adr/) — fourteen records covering
why there is no graph database, why Azure comes before AWS, why caching has two tiers, and
why acquisition is claimed rather than checked.

---

## Credit

The research this platform productionises is **[Structuring 40 Million Documents into an
Agentic Knowledge Graph](https://medium.com/gitconnected/structuring-40-million-documents-into-an-agentic-knowledge-graph-92010e609dfa)**
by [FareedKhan-dev](https://github.com/FareedKhan-dev/agentic-knowledge-graph) — 39.99M
documents, 929,824,202 edges, zero model calls to build, 83.2% on held-out PubMedQA. The
study in `poc/notebook/` is that work, MIT licensed, © 2026 Fareed Khan.

Several of this platform's rules exist because that study measured the alternatives and
they lost: the graph retrieves at 15% where dense retrieval reaches 95%; graph
certification predicts correctness at chance; using it as a filter halved coverage for no
gain; an agent loop that broadened thin queries scored worse than the plain pipeline. Those
findings are encoded here as constraints and named tests rather than as advice.
