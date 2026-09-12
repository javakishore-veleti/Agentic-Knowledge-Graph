# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repo is **specification-only**: there is no implementation yet. What exists is two
competing PRDs for the same product (the Agentic Knowledge Graph platform, "AKG") plus a
bare `uv` Python scaffold (`main.py` prints a hello message; `matplotlib`/`numpy` are the
only dependencies). Everything described in the PRDs — services, Airflow DAGs, contracts,
portals, Makefile, `compose.yaml`, `.github/workflows/` — has still to be created.

Do not treat PRD directory trees or `make` targets as things that exist. When asked to
"run the tests" or "build", there is nothing to run beyond the scaffold below.

```bash
uv sync                 # install/refresh .venv from uv.lock (Python 3.13, pinned in .python-version)
uv run main.py          # run the scaffold entry point
uv add <pkg>            # add a dependency (updates pyproject.toml + uv.lock)
```

## Reference study

Both PRDs derive from *Structuring 40 Million Documents into an Agentic Knowledge Graph*:
https://medium.com/gitconnected/structuring-40-million-documents-into-an-agentic-knowledge-graph-92010e609dfa
(39.99M documents, 929.8M edges, zero model calls to build). This is the system being
implemented here — the PRDs are its productionisation, not a separate design.

`poc/` is that study's pipeline, and its stages map onto the article's offline-build row:

| PoC script | Build stage |
|---|---|
| `poc/pipeline/parse_pubmed.py` | parse 40M XML → 6 tables |
| `poc/pipeline/build_graph4.py` | build MeSH ontology + CSR graph |
| `poc/pipeline/embed_corpus3.py` | embed 28.3M abstracts |
| `poc/pipeline/consolidate_index.py` | consolidate 1,334 shards → 1 index |
| `poc/pipeline/kg_ground3.py` … `kg_ground6.py` | hybrid grounder (lexical + dense agents) |
| `poc/notebook/agentic_kg_40m.ipynb` | end-to-end study notebook |

Two things in the study's architecture are **deliberately dropped** downstream, so do not
port them forward from the diagram or the article: the `refine / broaden` agent loop around
the refusal ladder (measured 2.5 points worse than the plain pipeline) and gate 6, the
entailment verifier (0.97 neutral on concatenated passages — off by default, PRD B open
question Q5). The refusal ladder's structural gates — no entry point, <2 concepts, no path,
not quotable, only retracted — do carry forward into retrieval.

## The two PRDs — read this before implementing anything

Both documents describe the same product and derive from the same reference study
(*Structuring 40 Million Documents into an Agentic Knowledge Graph*), but they are **not
consistent with each other**. Neither is marked superseded, and neither is committed to git
yet. Confirm with the user which is authoritative before generating structure from either.

| | `Agentic-Knowledge-Graph-Platform-PRD.md` (call it **A**) | `PRD-agentic-knowledge-graph-platform.md` (call it **B**) |
|---|---|---|
| Shape | Enterprise PRD: 29 sections, FR-xxx/SEC-xxx requirement IDs, waves, ADRs | Business-case + module briefs: Parts A–D, M0–M17, each a copy-paste agent brief |
| Graph store | JanusGraph/Gremlin locally, **Amazon Neptune** in AWS | **No graph DB** — CSR-on-memmap, in-process; Neptune/Neo4j is an explicit non-goal |
| Directory naming | `Middleware/`, `ETL/`, `Portals/KnowledgeAdmin`, `Contracts/`, `DomainPacks/` (13 middleware services) | `middleware/`, `etl/`, `portals/admin`, `platform/contracts/` (7 middleware services) |
| Kafka locally | Kafka container | Redpanda (Kafka API) |
| Auth | Identity Access Service, pre-retrieval batch authorization | Keycloak local / Cognito AWS at the gateway |
| Airflow in AWS | EKS (MWAA deferred) | Open question Q1, undecided |
| Abstention | Confidence Policy Service: `ANSWER` / `REFUSE` / `HUMAN_REVIEW` | Calibrated posterior + threshold in `middleware/answer` |
| Agent wiring | `.github/agents/` role files + waves 0–8 | `.claude/agents.yaml` + module dependency table (§3, §11) |

They *agree* on: Kafka as the single bus (no RabbitMQ), Airflow for batch, OpenFaaS for
functions (no Lambda), MinIO→S3, OpenSearch for vector search, local-first with
config-selected AWS adapters, immutable versioned artifacts with pinned versions, and
one-agent-per-module ownership.

## The core pattern (agreed by both documents)

Dense vectors retrieve, the provenance graph explains and certifies, calibrated model
confidence decides whether to answer, and the generator only renders from evidence already
admitted. The pipeline is deterministic:

```
gateway (auth, tenant, trace_id)
  → grounder (question → concepts with roles; no model in this path)
  → retrieval (dense top-k → rerank → graph certify → structural gates)
  → generator (renders from admitted evidence only)
  → answer (calibration bias, abstention threshold, citation validation)
  → answer.produced event → lake, eval harness, admin trace explorer
```

Build side: acquire → parse (source adapter) → ontology → graph build → embed →
consolidate → manifest → `artifact.built` → eval gate → `artifact.promoted` → atomic pin
swap. Serving pins artifact versions; promotion swaps the pin, rollback swaps it back.
Nothing is hot-patched, and incompatible graph/index/catalog versions must never be mixed
(A §21 release manifest, B §5.2 artifact manifest).

## Design constraints that are easy to violate

These come from measured failures in the reference study, so they override intuition about
what "should" work. B §C2 has the numbers.

- **The graph never retrieves.** Gold-in-top-8 was 15% for graph vs 95% for dense. Graph
  traversal annotates, explains and provides provenance; it does not rank or replace dense
  retrieval.
- **Certification annotates, never filters.** Using it as a hard evidence filter halved
  coverage with no accuracy gain. Graph-path existence is never the abstention signal
  (AUROC 0.50 — chance).
- **No query-refinement / broadening agent loop in v1.** Measured 2.5 points worse than the
  plain pipeline.
- **Score the top-1 passage**; marginalising over many documents dropped accuracy 82% → 45%.
- **The entailment verifier, if used, scores a single best source**, never concatenated
  passages (concatenation produced 0.97 neutral — refusing true claims). Off by default.
- **Every constant in the data path is swept by the eval harness and referenced from
  config.** One unswept truncation constant was worth 14 accuracy points.
- **Calibration is fitted on a held-out dev split, never on test.** Enforce the split in
  code, not convention.
- **Reference arms (oracle, blind, majority-class, shuffled-label) run on every evaluation**
  and are never selectable as the winner.
- Authorization/tenant filtering happens **before** snippets reach any AI service.
- Never weaken a test or quality gate to make a build pass.

The study's silent bugs are required named regression tests (B §5.5):
`test_major_topic_alignment`, `test_ranker_cache_not_keyed_to_first_query`,
`test_citation_regex_multi_id`, `test_verifier_scores_single_source`,
`test_truncation_constant_swept`, `test_cache_filename_not_overwritten`.

## Architecture rules for new code

- **Contracts before implementations.** Schemas, OpenAPI/AsyncAPI specs, event topics and
  artifact manifests land first, in one contracts module, and every other module compiles
  against them. Breaking changes bump a major version and go through a contract-change PR.
- **No environment branches in code.** Services read the env var and load
  `config/<env>.yaml`; AWS specifics live behind ports/adapters that pass the same contract
  tests as the local substitute. No local-only business logic.
- **One decision per component.** The study's central failure was giving the graph both
  retrieval and refusal. Gates are vetoes, not weighted terms.
- **No shared database tables across independently deployable services.**
- Every event carries the common envelope (`trace_id`/correlation, `tenant_id`, `env`,
  `schema_version`, event version, partition key, classification). Consumers are idempotent,
  commit offsets only after durable completion, dead-letter poison records, and tolerate
  unknown optional fields.
- OpenFaaS functions only when stateless, short, small, event/HTTP-triggered, no GPU, no
  multi-step transaction ownership — otherwise promote to an ETL worker or service.
- Forbidden in v1: AWS Lambda, RabbitMQ, a second frontend framework, a graph database if
  PRD B wins, multi-hop bridges beyond one hop, generator fine-tuning.

## Working as a multi-agent team

Both PRDs assume one agent per module with non-overlapping directory ownership. An agent
edits only its own module; changes to the shared contracts module go through a PR the
contracts owner reviews. Contracts must be merged before dependent modules start. Every
module ships `CLAUDE.md` (scope, contracts consumed/produced, do-not-touch list),
`README.md`, `src/`, `tests/`, `Dockerfile`, `Makefile`, and a handoff note. Integration and
schema migrations are serialised through the lead agent. Build order and parallelisable
groups: PRD B §3; the equivalent wave plan is PRD A §19.4.

PRD A §28 contains the intended first execution prompt (Wave 0: skeleton, ADR-001…010,
scoped `CLAUDE.md` files, agent role files, dependency map, CI stubs — no business features).

## Unresolved decisions

PRD B §10 lists six open questions owned by the user, three of them blocking: MWAA vs
Airflow on EKS (Q1), generator backend and whether it exposes logprobs (Q2), and the tenancy
model — shared graph with tenant-scoped answers vs per-tenant graph artifacts (Q6). Record
ambiguities as explicit decisions required; do not silently invent product behaviour.
