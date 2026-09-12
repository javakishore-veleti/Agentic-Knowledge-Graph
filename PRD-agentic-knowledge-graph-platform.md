# PRD: Agentic Knowledge Graph Platform (AKG)

**Version:** 0.2 draft
**Owner:** Kishore Veleti
**Status:** For agent-driven implementation
**Reference:** Fareed Khan, "Structuring 40 Million Documents into an Agentic Knowledge Graph" (Aug 2026). This PRD adopts the surviving pattern from that study and closes the production gaps it left open.

**Document structure.**
Part A: Business context and requirements — what the business needs and why.
Part B: Business features — what users get, in their language.
Part C: Solution approach — the pattern, the principles, and the architecture that satisfy Part A and B.
Part D: Implementation structure — modules, contracts, agents, and phasing for Claude Code.

Readers deciding whether to fund this need only Parts A and B. Architects need C. Engineers and agents need D.

---

# Part A: Business context and requirements

## A1. Business problem

Enterprises are deploying question-answering over large document corpora (clinical literature, engineering standards, warranty and service records, regulatory filings, contracts). The current generation of RAG systems produces fluent answers with three business defects:

1. **Unexplainable evidence.** A cosine score cannot tell a reviewer, auditor, or regulator *why* a document was allowed to support an answer. In regulated environments this blocks adoption entirely.
2. **Unreliable refusal.** Systems either answer everything (hallucination risk, liability) or refuse conservatively (low coverage, users go back to manual search). Neither refusal behaviour is measured against a control, so nobody knows the false-answer rate.
3. **Unmeasured quality.** Evaluation is a one-time notebook exercise. The reference study showed six separate defects that improved a metric while degrading the system. Without evaluation as an ongoing gate, quality regressions ship silently.

A fourth defect is economic: graph-based approaches that fix defect 1 cost tens of thousands of dollars per corpus in model calls for extraction, which makes them unaffordable above a few thousand documents.

## A2. Business opportunity

The reference study demonstrated that when a corpus ships structured edges, a provenance graph over 40 million documents builds in minutes for zero model calls, and that a correctly separated architecture (vectors retrieve, graph explains, calibrated confidence abstains) reaches 83% accuracy on a hard biomedical benchmark with zero fabricated citations. It also demonstrated exactly which architectural choices fail. That gives a defensible, evidence-backed pattern to productise.

The opportunity is a reusable platform that any business unit can point at a corpus and get:
- cited, explainable answers,
- explicit refusals with reasons,
- an audit trail per answer,
- and a quality gate that blocks regressions before they reach users.

## A3. Stakeholders and personas

| Persona | Needs | Pain today |
|---|---|---|
| **Knowledge worker** (analyst, clinician, engineer, claims adjuster) | Fast answers with sources they can trust and click through | Manual search, or an AI tool they cannot cite in their own work |
| **Domain reviewer / compliance officer** | Prove why each source was admissible; audit any answer after the fact | No trail beyond "the model said so" |
| **Platform operator / SRE** | Promote, roll back, monitor, alert; know which version answered what | Notebook artefacts, no versioning, no telemetry |
| **Data steward** | Control what corpus versions and ontologies are live; manage aliases and blocked terms | Rebuilds are manual and opaque |
| **Business sponsor** | Measured accuracy, coverage, refusal, and cost per answer; confidence to expand to new corpora | No comparable numbers, no way to justify spend |
| **Security / privacy officer** | Tenancy, PHI handling, least-privilege access, audit | Single-box research code with none of it |

## A4. Business requirements

Requirements are stated as outcomes. Each maps to features in Part B and modules in Part D.

| ID | Requirement | Rationale | Priority |
|---|---|---|---|
| BR1 | Every answer cites sources, and every citation is verifiably present in the admitted evidence set | Liability, trust, regulatory defensibility | P0 |
| BR2 | Every cited source carries a human-readable admissibility reason and a traceable path | Audit and compliance; reviewer adoption | P0 |
| BR3 | The system refuses when evidence is insufficient, states the reason, and the false-answer (leak) rate is measured against matched impossible questions | Hallucination containment with a number attached | P0 |
| BR4 | No graph, index, model, or calibration change reaches users without passing an automated quality gate with control arms | Prevent silent regressions | P0 |
| BR5 | Corpus onboarding cost is dominated by parsing, not model calls, when the source provides structure; extraction is a pluggable option otherwise | Economics; scale to tens of millions of documents | P0 |
| BR6 | Identical behaviour locally and in AWS from the same code and images | Developer velocity, reproducibility, lower cloud spend during build | P0 |
| BR7 | New and corrected documents become retrievable without a full rebuild; retractions stop being cited within a minute | Freshness; safety on withdrawn evidence | P0 |
| BR8 | "As of" date answering: the system can answer as the evidence stood on a given date | Regulatory and legal use cases; reproducibility of past decisions | P1 |
| BR9 | Tenant isolation, role-based access, PHI mode with redaction and guardrails | Multi-BU and healthcare deployment | P0 for AWS |
| BR10 | Operators see per-stage latency, refusal reasons, certification routes, confidence distribution, and quality trend | Operability; determinants of effective incident review | P0 |
| BR11 | Cost per answer and cost per corpus build are reported per artifact version | Sponsor visibility; capacity planning | P1 |
| BR12 | End users can give feedback that flows into the quality gate as labelled data | Continuous improvement without a separate labelling programme | P1 |

## A5. Business success criteria

| Criterion | Target (v1) | Stretch |
|---|---|---|
| Answer accuracy on reference benchmark (held-out) | ≥ 82% | ≥ 85% |
| Fabricated citations reaching users | 0 | 0 |
| Leak rate (answers to matched impossible questions) | ≤ 8% | ≤ 5% |
| Coverage (share of real questions answered) | ≥ 55% | ≥ 65% |
| Corpus build cost, 40M-document edge-bearing corpus | < $50 compute, $0 model calls | — |
| Time from delta event to retrievable | < 5 min | < 1 min |
| Reviewer can trace any answer end to end | < 2 s | — |
| Regressions blocked by gate before release | 100% of defined checks | — |

## A6. Constraints and assumptions

- **Constraint:** No AWS Lambda; function workloads run on OpenFaaS for cost and parity.
- **Constraint:** Orchestration is Apache Airflow, run locally first and deployed unchanged to AWS.
- **Constraint:** Event bus is Kafka-compatible on both targets.
- **Constraint:** Build and validate locally before any AWS spend.
- **Assumption:** The first corpus is edge-bearing (PubMed reference). Enterprise corpora without edges are v1.1 via the extraction adapter.
- **Assumption:** A GPU is available for embedding and generation in AWS; local development must degrade gracefully without one.
- **Risk:** Generator backends differ in logprob support; posterior fidelity may vary by model (Open Question Q2).

---

# Part B: Business features

Features are what users experience. Each lists the requirement it satisfies.

## B1. Ask and receive a cited answer (BR1, BR2)
The user asks a question in natural language. The system returns an answer where every sentence ends with the sources it used. Each source is clickable and opens the passage, the reason it was admitted (for example "directly about both concepts in your question", "cited by a document about concept X", "related through the ontology"), and the path that connects it.

## B2. Explicit, explained refusal (BR3)
When the system will not answer, the user sees which of a fixed set of reasons applied: nothing in the question maps to a known concept; too few specific concepts; no connecting evidence; only retracted evidence; no evidence as of the requested date; confidence too low. Refusals are never blank.

## B3. Answer as of a date (BR8)
A date control lets the user ask how the evidence stood on that date. Documents published after the date are excluded from evidence and from citations.

## B4. Source trace explorer (BR2, BR10)
Reviewers open any answer by ID and see the full chain: concepts grounded from the question, candidate documents, admissibility route per candidate, the model's confidence, the decision, and the final citations. The trace is exportable for audit.

## B5. Quality gate and release control (BR4)
Operators see, for each candidate release, accuracy and coverage on the held-out set, leak on control questions, the control arms (oracle, blind, majority-class, shuffled-label), and the error budget split by cause. Promotion requires the gate to pass and a typed confirmation. Rollback is one action.

## B6. Corpus and ontology management (BR5, BR7)
Data stewards see which corpus and ontology versions are live, trigger or schedule rebuilds, watch delta volume, manage concept aliases, and maintain the blocked common-word list that prevents spurious grounding.

## B7. Freshness and retraction handling (BR7)
New documents arrive through an event stream and are searchable within minutes. Retracted or corrected documents are flagged immediately and drop out of citations without waiting for a rebuild.

## B8. Operations dashboard and alerts (BR10, BR11)
Per-stage latency, refusal reasons over time, certification route mix, confidence histogram, cost per answer and per build, and alerts on artifact pin mismatch, gate failure, and abstention drift.

## B9. Tenancy, access, and PHI mode (BR9)
Every request and stored answer is tagged to a tenant. Roles: end user, reviewer, steward, operator, admin. PHI mode routes generation through a guardrail layer and redacts answer logs before they land in the data lake.

## B10. Feedback loop (BR12)
End users mark an answer correct, incorrect, or unsure. Feedback flows into the evaluation harness as labelled samples for the next calibration fit.

## B11. Corpus onboarding (BR5)
A new corpus is onboarded by implementing or selecting an adapter. Edge-bearing sources parse directly. Sources without edges use the extraction adapter, whose cost and quality are reported separately so the business can decide per corpus.

---

# Part C: Solution approach

## C1. The pattern in one sentence

**Dense vectors retrieve, the provenance graph explains and certifies, calibrated model confidence decides whether to answer, and the generator only renders from evidence that has already been admitted.**

## C2. Why this pattern

The reference study tested the alternatives and measured them:

| Alternative | Result | Consequence for AKG |
|---|---|---|
| Graph as the retriever | Gold document in top-8 on 15% of questions vs 95% for dense | Graph never retrieves; it annotates what dense found |
| Graph certification as the abstention gate | Predicts correctness at AUROC 0.50 (chance); refused questions were right as often as answered ones | Abstention uses model confidence (AUROC 0.81, free) |
| Certification as a hard filter on evidence | Halved coverage with no accuracy gain | Certification annotates candidates; it does not drop them |
| Agent loop that broadens or relaxes the query on thin evidence | 2.5 points worse margin than the plain pipeline | No refinement loop in v1 |
| Marginalising the answer over many documents | Accuracy fell from 82% to 45% as k grew | Score the top-1 document; k is a swept option |
| Entailment verifier on concatenated passages | Refused true claims (0.97 neutral) | Verifier, if used, scores the best single source |
| Unswept constants in the data path | One truncation constant was worth 14 accuracy points | Every constant in the path is swept by the harness and referenced from config |

## C3. Design principles

1. **One job per component.** The study's central failure was giving the graph both retrieval and refusal. Each service in AKG owns exactly one decision.
2. **Gates are vetoes, not weighted terms.** A score lets a strong signal compensate for irrelevant evidence; a constraint cannot.
3. **The generator never decides what is true or whether to answer.** It renders from an admitted evidence set, and its citations are validated against that set before anything reaches the user.
4. **Per-layer ground truth.** Every derived structure has an internal invariant plus an independent recount from its source. End-to-end scores cannot say that the thing they improved was the wrong thing.
5. **Reference arms in every evaluation.** Oracle, blind, majority-class, and shuffled-label arms are always run and never selectable as the winner.
6. **Dev chooses, test reports, once.** The split is fixed and enforced in code.
7. **Immutable, versioned artifacts.** Graph, index, ontology, and calibration are pinned; promotion swaps pins; nothing is hot-patched.
8. **Parity by construction.** Storage, bus, functions, orchestration, and auth each have a local and an AWS backend behind the same interface. Code never branches on environment.

## C4. Logical architecture

```
                         ┌──────────────────────────────────────────────┐
                         │                  PORTALS                     │
                         │   Customer portal        Admin portal        │
                         └───────────────┬──────────────────┬───────────┘
                                         │                  │
                                    ┌────▼──────────────────▼────┐
                                    │          GATEWAY           │  auth, tenancy, trace-id, rate limit
                                    └────────────┬───────────────┘
                                                 │
   ┌─────────────┐   ┌──────────────┐   ┌────────▼────────┐   ┌───────────────┐   ┌───────────────┐
   │  GROUNDER   │◄──┤              │   │    RETRIEVAL    ├──►│   GENERATOR   │──►│    ANSWER     │
   │ lexical +   │   │              │   │ dense → rerank  │   │ posteriors /  │   │ calibrate,    │
   │ dense spans │   │              │   │ → certify →     │   │ freeform      │   │ abstain,      │
   └─────────────┘   │              │   │ structural gates│   └───────────────┘   │ validate cites│
   ┌─────────────┐   │  MIDDLEWARE  │   └────────┬────────┘                       └───────┬───────┘
   │ GRAPH STORE │◄──┤              │            │                                        │
   │ CSR memmap  │   │              │            │        FUNCTIONS (OpenFaaS)            │
   └─────────────┘   │              │            │        citation-validator, aliases ◄───┘
   ┌─────────────┐   │              │            │
   │VECTOR INDEX │◄──┘              │            │
   │ k-NN + delta│                  │            │
   └──────▲──────┘                  │            ▼
          │                         │      Kafka: retrieval.completed, answer.produced, feedback.received
          │ pinned artifacts        │                              │
   ┌──────┴─────────────────────────┴──────┐              ┌────────▼────────┐
   │              ETL (Airflow)            │              │  EVAL HARNESS   │  gate: promote / reject
   │ historical: acquire→parse→ontology→   │◄─────────────┤  reference arms │
   │   graph→embed→consolidate→manifest    │  artifact.*  │  sweeps, calib  │
   │ realtime: deltas, retractions,        │              └─────────────────┘
   │   rebuild trigger                     │
   └───────────────────────────────────────┘
                   ▲
          adapters: pubmed (edges shipped) | generic-extraction (pluggable)
```

## C5. Runtime flow of one question

1. Gateway authenticates, tags tenant, mints `trace_id`.
2. Grounder maps the question to concepts with roles (bridge / filter / ignore). No model in this path.
3. Retrieval runs dense top-k, cross-encoder rerank, then asks the graph store to certify each candidate (route + reason). Structural gates evaluate: no entry point, too few concepts, no quotable, only retracted, no evidence as of date. A structural refusal returns here without touching the generator.
4. Generator scores the top-1 passage and returns a label posterior (and freeform prose if requested).
5. Answer applies the pinned calibration bias and abstention threshold; optionally runs the verifier against the best single source; passes prose through the citation validator, which strips any ID not in the admitted set.
6. The `answer.produced` event carries the whole chain to the lake, the eval harness, and the admin trace explorer.

## C6. Build flow of one corpus version

Acquire → parse (adapter) → ontology → graph build (single sorted pass, alignment assert, DB recount) → embed → consolidate (uniqueness assert, spot-check, count audit) → manifest → `artifact.built` → eval gate → `artifact.promoted` → pin swap.

## C7. Deployment approach

| Concern | Local | AWS |
|---|---|---|
| Object storage | MinIO | S3 |
| Event bus | Redpanda (Kafka API) | MSK |
| Orchestration | Airflow in Compose | MWAA or Airflow on EKS (Q1) |
| Functions | faasd | OpenFaaS on EKS |
| Vector search | OpenSearch container | OpenSearch Serverless |
| Auth | Keycloak | Cognito |
| Telemetry | OTel → Grafana / Tempo / Loki / Prometheus | ADOT → CloudWatch / X-Ray / Managed Grafana |
| GPU | optional, CPU fallback | EKS GPU node group or SageMaker |
| CI/CD | GitHub Actions → GHCR, self-hosted runner | GitHub Actions → ECR via OIDC, Terraform, DAG sync, faas-cli |

Everything is proven locally on a sample corpus, then deployed to AWS dev with the same images, then promoted to prod behind the eval gate and a manual approval.

## C8. What is deliberately deferred

Graph database, multi-hop bridges, query refinement loops, generator fine-tuning, Lambda, and metering. Each has a measured or economic reason in Part D §2 (non-goals) and can be revisited once the ranker is load-bearing and the corpus set grows.

---

# Part D: Implementation structure


## 0. How to use this document with Claude Code

This PRD is split into **modules**. Each module is self-contained: it names its folder, its owner agent, its inputs, outputs, contracts, and acceptance criteria. Claude Code should run **one agent per module**, in the dependency order given in §3, with the `platform-contracts` module completed first because every other module compiles against it.

Every module folder must contain:

```
<module>/
  CLAUDE.md          # agent brief: scope, contracts consumed/produced, do-not-touch list
  README.md          # human docs
  src/
  tests/
  Dockerfile
  Makefile           # make test | make build | make run-local
```

Agents **must not** edit files outside their module except `platform/contracts/` via a pull request that the `platform-contracts` agent reviews. Contract changes are versioned; breaking changes bump the major version.

Agent orchestration file lives at `/.claude/agents.yaml` (spec in §11).

---

## 1. Problem statement

See Part A. This part assumes Parts A to C are approved and describes only how the solution is built.

## 2. Goals and non-goals

### Goals
1. **Same code, two targets.** Every service runs locally under Docker Compose and on AWS from the same image and the same Airflow DAGs. Only `config/<env>.yaml` and secrets differ.
2. **Zero-LLM graph build for edge-bearing corpora.** When the source ships structured edges (PubMed as reference adapter), the graph builds with no model calls. When it does not, extraction is a swappable adapter, not a rewrite.
3. **Provenance on every answer.** Every cited document carries a certification route (co-annotation, ontology ancestry, citation adjacency) and a path the admin portal can render.
4. **Abstention by calibrated confidence**, fitted on a held-out dev split, never on test.
5. **Evaluation as a gate.** No graph, index, model, or calibration artifact is promoted without reference arms (oracle, blind, majority-class, shuffled-label) passing within tolerance.
6. **Full traceability.** One trace ID from portal request through grounding, retrieval, certification, generation, citation validation, and abstention.

### Non-goals (v1)
- Graph database (Neptune, Neo4j). CSR-on-memmap is the store. Reason: fixed-shape traversal, 1000x lower latency, no bulk-load path in graph DBs.
- Multi-hop bridges beyond one hop. Reason: the ranker must be load-bearing first (study finding).
- Agent loop that broadens or relaxes queries. Reason: measured worse than the plain pipeline.
- Lambda. Reason: cost; OpenFaaS covers function-shaped workloads on both targets.
- Fine-tuning the generator. Reason: calibration bias fitting captured most of the gain at far lower cost.
- Multi-tenant billing. Reason: separate initiative; tenancy isolation is in scope, metering is not.

---

## 3. Module map and build order

| # | Module | Folder | Type | Depends on | Agent |
|---|---|---|---|---|---|
| 0 | platform-contracts | `platform/contracts` | library | none | `contracts-agent` |
| 1 | platform-infra-local | `platform/infra/local` | compose | 0 | `infra-local-agent` |
| 2 | platform-infra-aws | `platform/infra/aws` | terraform | 0, 1 | `infra-aws-agent` |
| 3 | platform-observability | `platform/observability` | library + sidecars | 0 | `observability-agent` |
| 4 | etl-historical | `etl/historical` | Airflow DAGs + jobs | 0, 1, 3 | `etl-historical-agent` |
| 5 | etl-realtime | `etl/realtime` | Kafka consumers + Airflow | 0, 1, 3, 4 | `etl-realtime-agent` |
| 6 | functions | `functions/` | OpenFaaS | 0, 3 | `functions-agent` |
| 7 | middleware-grounder | `middleware/grounder` | service | 0, 3, 4 | `grounder-agent` |
| 8 | middleware-graph-store | `middleware/graph-store` | service | 0, 3, 4 | `graph-store-agent` |
| 9 | middleware-vector-index | `middleware/vector-index` | service | 0, 3, 4 | `vector-index-agent` |
| 10 | middleware-retrieval | `middleware/retrieval` | service | 0, 3, 7, 8, 9 | `retrieval-agent` |
| 11 | middleware-generator | `middleware/generator` | service | 0, 3 | `generator-agent` |
| 12 | middleware-answer | `middleware/answer` | service | 0, 3, 10, 11 | `answer-agent` |
| 13 | middleware-gateway | `middleware/gateway` | service | 0, 3, 12 | `gateway-agent` |
| 14 | eval-harness | `eval/` | Airflow DAGs + jobs | 0, 3, 4, 10, 11, 12 | `eval-agent` |
| 15 | portal-admin | `portals/admin` | web app | 0, 13 | `portal-admin-agent` |
| 16 | portal-customer | `portals/customer` | web app | 0, 13 | `portal-customer-agent` |
| 17 | ci-cd | `.github/workflows` | GitHub Actions | all | `cicd-agent` |

Parallelisable groups after module 0: {1, 3} → {4, 6, 11} → {5, 7, 8, 9} → {10} → {12} → {13} → {14, 15, 16} → {17 runs alongside every group}.

---

## 4. Repository layout

```
akg/
  .claude/
    agents.yaml
  .github/workflows/
  platform/
    contracts/            # schemas, event types, API specs, artifact manifests
    infra/
      local/              # docker-compose, faasd, kafka, minio, postgres, opensearch, airflow
      aws/                # terraform: VPC, S3, MSK, EKS, MWAA or Airflow on EKS, OpenSearch, ECR, IAM
    observability/        # otel config, dashboards, alert rules, trace-id propagation lib
  etl/
    historical/           # bulk ingest → parse → ontology → graph build → embed → consolidate
    realtime/             # kafka consumers for deltas, incremental shard append, rebuild trigger
    adapters/             # source adapters: pubmed (reference), generic-extraction
  functions/              # OpenFaaS: citation-validator, checksum, alias-normaliser, small fan-out tasks
  middleware/
    grounder/
    graph-store/
    vector-index/
    retrieval/
    generator/
    answer/
    gateway/
  eval/                   # harness DAGs, reference arms, calibration fit, promotion gate
  portals/
    admin/
    customer/
  config/
    local.yaml
    aws-dev.yaml
    aws-prod.yaml
  docs/
```

---

## 5. Cross-cutting requirements

### 5.1 Environment parity (P0)
- Every service reads `AKG_ENV` and loads `config/<env>.yaml`. No environment-specific code branches.
- Object storage is accessed via an S3-compatible client; local target is MinIO, AWS target is S3.
- Event bus is accessed via a Kafka client; local target is Redpanda or Kafka in Compose, AWS target is MSK. RabbitMQ is **not** used (single bus keeps parity simple).
- Functions run on OpenFaaS: `faasd` locally, OpenFaaS on EKS in AWS. Same `stack.yml`.
- Airflow runs in Compose locally; in AWS either MWAA or Airflow on EKS (decision in Open Questions). DAG code is identical; executors differ by config.

### 5.2 Versioned artifacts (P0)
Every build output is an immutable, versioned artifact with a manifest:

```yaml
artifact: graph
version: 2026.09.12-a3f9c1
source_version: pubmed-baseline-2026
ontology_version: mesh-2026
checksums: {...}
counts: {nodes: ..., edges_by_family: {...}}
validation: {alignment_assert: pass, db_recount: pass}
```

Serving services **pin** to artifact versions. Promotion swaps the pin; rollback swaps it back. No hot-patching.

### 5.3 Traceability (P0)
- One `trace_id` generated at gateway, propagated through every service and every emitted event.
- Every answer emits an `answer.produced` event carrying grounding, candidates, certification routes, confidence posterior, abstention decision, and cited IDs.
- OpenTelemetry everywhere; local collector to Grafana Tempo/Loki/Prometheus, AWS to ADOT → X-Ray/CloudWatch.

### 5.4 Security (P0 for AWS, P1 for local)
- Private VPC, KMS on S3 and MSK, IAM per service, OIDC for GitHub Actions.
- Gateway auth via OIDC provider (Cognito in AWS, Keycloak in Compose).
- Tenant ID on every request and every stored answer event.
- PHI mode flag: when on, generator calls route through a guardrail layer and answer events are redacted before landing in the lake.

### 5.5 Testing standard (P0)
- Unit tests per module, contract tests against `platform/contracts` fixtures, integration tests in Compose.
- The reference study's silent bugs become named tests: `test_major_topic_alignment`, `test_ranker_cache_not_keyed_to_first_query`, `test_citation_regex_multi_id`, `test_verifier_scores_single_source`, `test_truncation_constant_swept`, `test_cache_filename_not_overwritten`.

---

## 6. Module specifications

Each module below is written as an agent brief. Copy into that module's `CLAUDE.md`.

---

### M0: platform-contracts

**Scope.** Single source of truth for schemas, event topics, API specs, artifact manifests, and error codes.

**Produces.**
- `schemas/` Pydantic + JSON Schema for: `Document`, `Edge`, `Concept`, `Grounding`, `Candidate`, `Certification`, `Posterior`, `Answer`, `AnswerEvent`, `ArtifactManifest`.
- `events/topics.yaml` (see §7).
- `api/openapi.yaml` for gateway, retrieval, generator, answer, grounder, graph-store, vector-index.
- `fixtures/` golden examples for every schema.
- Python package `akg_contracts` published to the repo's package index.

**Acceptance.**
- [ ] `make test` validates every fixture against its schema.
- [ ] Any schema change requires a `CHANGELOG.md` entry and semver bump.
- [ ] Contract tests generated for consumers (`akg_contracts.testing`).

---

### M1: platform-infra-local

**Scope.** `docker-compose.yaml` bringing up the whole stack on one machine.

**Services.** MinIO, Postgres (Airflow metadata + DuckDB alternative for analytics), Redpanda (Kafka API), Airflow (webserver, scheduler, worker), faasd, OpenSearch (k-NN), Keycloak, OTel collector, Grafana + Tempo + Loki + Prometheus.

**Acceptance.**
- [ ] `make up` brings the stack healthy in under 5 minutes on a 32 GB machine.
- [ ] `make smoke` runs an end-to-end request through gateway → answer on a 10k-document sample and returns a cited answer.
- [ ] GPU optional: embedding and generator fall back to CPU-small models when no CUDA device is present.

---

### M2: platform-infra-aws

**Scope.** Terraform for the AWS target. Mirrors M1 service for service.

| Local | AWS |
|---|---|
| MinIO | S3 |
| Redpanda | MSK |
| Airflow in Compose | MWAA **or** Airflow on EKS (Open Question Q1) |
| faasd | OpenFaaS on EKS |
| OpenSearch container | OpenSearch Serverless (k-NN) |
| Keycloak | Cognito |
| Grafana stack | ADOT → CloudWatch, X-Ray, Managed Grafana |
| Local GPU | EKS GPU node group **or** SageMaker for embed/generate |

**Acceptance.**
- [ ] `terraform plan` clean on dev and prod workspaces.
- [ ] Same images from ECR run unchanged.
- [ ] Airflow DAGs deploy from the same `etl/` folder via S3 sync.

---

### M3: platform-observability

**Scope.** Trace-ID propagation library, OTel instrumentation helpers, dashboards, alert rules, SLOs.

**SLOs (initial).** Gateway p95 < 2.5 s answered, < 300 ms refused-before-generation; graph-store node expansion p99 < 50 µs in-process; vector top-16 p95 < 150 ms.

**Acceptance.**
- [ ] `akg_obs.trace()` decorator used by every middleware handler.
- [ ] Dashboards: per-stage latency, refusal reasons by gate, certification routes, confidence histogram, leak rate from eval.
- [ ] Alerts: artifact pin mismatch, eval gate failure, abstention rate drift > 10 points day over day.

---

### M4: etl-historical

**Scope.** Bulk pipeline as Airflow DAGs. Each task is a containerised job; Airflow orchestrates, never computes.

**DAG `historical_build`:**
1. `acquire` – adapter pulls source files to `raw/<source>/<version>/`, checksums, retries with bounded concurrency (study: 48 concurrent requests got 503s; default 4).
2. `parse` – fan-out one task per file via adapter → Parquet edge tables in `parsed/<version>/`.
3. `ontology` – build descriptors, tree, broader edges, allowable pairs, aliases (supplementary concept mapping) → `ontology/<version>/`.
4. `graph_build` – CSR forward, reverse, concept→doc, doc→concept; major-topic flags derived in the **same** sorted pass; alignment asserts; independent DB recount on sampled descriptors → `graph/<version>/`.
5. `embed` – super-shard, length-sort, persistent worker pool; fp16 vectors → `vectors/<version>/shards/`.
6. `consolidate` – two-pass memmap consolidation, uniqueness assert, spot-check against shards; audit vector count vs quotable count → `vectors/<version>/index/`.
7. `manifest` – write `ArtifactManifest`, emit `artifact.built`.

**Adapters (`etl/adapters/`).**
- `pubmed` – reference adapter, edges parsed not extracted.
- `generic-extraction` – interface only in v1: `extract(doc) -> list[Edge]` with a stub that raises `NotImplemented`. P1 implementation may call Bedrock batch or Comprehend.

**Acceptance.**
- [ ] DAG completes on the 10k sample locally; on a 1M sample in AWS dev.
- [ ] `graph_build` fails the DAG if alignment assert or DB recount fails.
- [ ] Parse rate ≥ 40k records/s on 26 cores for the PubMed adapter.
- [ ] Manifest counts match parsed row counts to the row.

---

### M5: etl-realtime

**Scope.** Delta ingest without full rebuild.

- Kafka consumer on `source.delta` receives new or updated document references.
- Adapter parses deltas into an append shard; embeds them; appends to a **delta index** that serving queries alongside the pinned index.
- Airflow DAG `rebuild_trigger` watches delta volume; when > configurable threshold (default 2% of corpus) it triggers `historical_build` for a new version.
- Retractions and corrections update the supersession table immediately (no rebuild needed for the retraction gate).

**Acceptance.**
- [ ] A delta document is retrievable within 5 minutes of the event locally.
- [ ] Retraction event flips `retracted=true` within 60 s and the answer service stops citing it.
- [ ] Delta index and pinned index results merge deterministically.

---

### M6: functions (OpenFaaS)

**Scope.** Small, stateless, function-shaped workloads. Same `stack.yml` for faasd and EKS.

- `citation-validator` – bracket-aware regex, split multi-ID brackets, keep only IDs in the admitted set. Rewrites the answer text.
- `alias-normaliser` – orthography rules, de-inversion, common-word guard.
- `checksum` – file integrity for acquire.
- `manifest-writer` – builds `ArtifactManifest` from stage outputs.

**Acceptance.**
- [ ] `test_citation_regex_multi_id`: `[1, 2, 99999999]` with admitted `{1, 2}` → `[1, 2]`; a bracket with no valid IDs is removed entirely.
- [ ] Functions deploy identically via `faas-cli up` on both targets.

---

### M7: middleware-grounder

**Scope.** Question → concepts. No LLM in the path.

- Lexical: longest-match against normalised surface forms (descriptors, de-inverted forms, aliases ≥ 8 chars), common-word guard.
- Dense: span-based, edge stop-words excluded, `scatter_reduce` onto descriptors, admitted only above calibrated τ (default 0.90), never overrides a lexical hit.
- Role assignment: `BRIDGE | FILTER | IGNORE` by category, depth, and article count (check-tag exclusion by count, not category).

**API.** `POST /ground {question} -> Grounding{concepts:[{ui, name, surface, role, source: lexical|dense, score}]}`

**Acceptance.**
- [ ] Coverage and precision reported against gold-document MeSH headings on the eval set; both numbers in the artifact manifest.
- [ ] τ is a config value swept by M14, never hard-coded.
- [ ] p95 < 40 ms on CPU for lexical-only, < 120 ms with dense on GPU.

---

### M8: middleware-graph-store

**Scope.** Serve the pinned CSR graph in-process from memmap.

**API.**
- `GET /expand/{doc_id}?dir=cites|cited_by`
- `POST /coannotate {concept_ids, major_only}` → sorted doc list
- `POST /certify {doc_id, concept_ids}` → `Certification{route, reason}`
- `POST /ancestry {ui, depth}`

**Acceptance.**
- [ ] Node expansion ≤ 10 µs mean in-process on the reference graph.
- [ ] `test_major_topic_alignment`: for 100 sampled descriptors, CSR count and major count equal DB recount.
- [ ] Load from pinned artifact < 100 ms; pin swap is atomic.

---

### M9: middleware-vector-index

**Scope.** Dense retrieval over the pinned consolidated index plus the delta index.

**Backends.** OpenSearch k-NN (both targets) as default; a `memmap-exact` backend for eval oracle runs.

**API.** `POST /search {query_vector | query_text, k, filters}` → `[Candidate{doc_id, score}]`

**Acceptance.**
- [ ] Gold-in-top-16 ≥ 95% on the eval set with the pinned index.
- [ ] Delta index merged on every query with a stable tie-break.

---

### M10: middleware-retrieval

**Scope.** The pipeline stage that owns candidate assembly. **Dense retrieves, graph certifies, ranker re-orders and never adds.**

1. Ground (M7).
2. Dense top-k (M9), k configurable, default 16.
3. Cross-encoder rerank (local model; read length is a swept constant, not a fixed 900).
4. Certify every candidate (M8): route and reason attached; **certification does not drop candidates in v1**, it annotates them (study: certification as a filter halved coverage at no accuracy gain).
5. Structural gates run before generation: `no_entry_point`, `too_few_concepts`, `no_quotable`, `only_retracted`, `no_evidence_as_of_date`.
6. Emit `retrieval.completed` with full candidate set and gate verdicts.

**API.** `POST /retrieve {question, as_of?, tenant}` → `RetrievalResult{grounding, candidates[], gates}`

**Acceptance.**
- [ ] `test_ranker_cache_not_keyed_to_first_query`.
- [ ] Every candidate has a `Certification`.
- [ ] Gate verdicts carry the gate name and the counts that fired it.

---

### M11: middleware-generator

**Scope.** Constrained answer generation with label posteriors.

- Backend adapter: `bedrock` (Claude / Nova), `sagemaker`, `local-vllm`, `local-transformers`. Backend must return logprobs for label tokens; if it cannot, the service falls back to a self-consistency estimate and flags `posterior_source=sampled`.
- Two modes: `label` (yes/no/maybe posterior over summed lower/upper-case tokens, `logits_to_keep=1`) and `freeform` (cited prose with `[id]` brackets and an `INSUFFICIENT_EVIDENCE` sentinel).
- Truncation is a config value with a documented sweep result attached; default 3000 chars.

**API.** `POST /posterior {question, passage}` and `POST /generate {question, passages[]}`

**Acceptance.**
- [ ] `test_truncation_constant_swept`: config must reference a sweep artifact ID from M14.
- [ ] Backend swap is config-only.
- [ ] Fallback chain and rate limiting per backend.

---

### M12: middleware-answer

**Scope.** Decision and rendering.

1. Score top-1 (default; marginalisation over k is a swept option that lost in the study).
2. Apply calibration bias vector from the pinned `calibration` artifact (fitted on dev by M14).
3. Abstain if `max P(y)` < threshold from the same artifact. **Graph certification is not used for abstention.**
4. Optional gate 6 (entailment verifier) scored against the **best single source**, never a concatenation; off by default, on for PHI mode.
5. Freeform render → `citation-validator` function (M6) → strip unadmitted IDs.
6. Emit `answer.produced` with everything.

**Acceptance.**
- [ ] `test_verifier_scores_single_source`.
- [ ] Zero unadmitted IDs reach the response (test with poisoned generator output).
- [ ] Abstention reason is one of: structural gate name, `low_confidence`, `verifier_neutral`.

---

### M13: middleware-gateway

**Scope.** Public API, auth, tenancy, rate limits, trace-ID origin.

**API.** `POST /v1/ask`, `GET /v1/answers/{id}`, `GET /v1/answers/{id}/trace`, `GET /v1/artifacts/current`, admin endpoints under `/v1/admin/*` (RBAC).

**Acceptance.**
- [ ] OIDC (Keycloak local, Cognito AWS) with role claims.
- [ ] Per-tenant rate limits; 429 with retry-after.
- [ ] Trace endpoint returns the full path for any answer ID.

---

### M14: eval-harness

**Scope.** Evaluation as a release gate. Airflow DAG `eval_gate` runs on every new artifact and nightly on logged traffic.

**Reference arms (always run, never selectable):** oracle (gold passage), blind (no evidence), majority-class, shuffled-label.

**Split discipline.** Fixed seed; dev 40% chooses config and fits bias; test 60% scored once per artifact; DEV→TEST correlation reported.

**Sweeps.** Truncation, k, τ (grounder), min_paths, cross-encoder read length, calibration bias grid (grid edges must not be optima; assert).

**Controls.** Matched impossible questions (one concept swapped) for leak measurement; coverage minus leak is the headline margin.

**Outputs.** `calibration` artifact, `eval` artifact with error budget (retrieval / distraction / both-wrong by gold label), promotion decision event `artifact.promoted` or `artifact.rejected`.

**Acceptance.**
- [ ] Promotion blocked if test accuracy drops > 2 points vs current, leak rises > 1 point, or any reference arm fails sanity (e.g. blind ≥ majority).
- [ ] `test_cache_filename_not_overwritten`: every run writes to a versioned path.
- [ ] Shuffled-label best-of-N spread reported alongside the winner.

---

### M15: portal-admin

**Scope.** Operator view.

- Artifact registry and pins; promote / rollback with reason.
- Eval dashboard: accuracy, coverage, leak, error budget, reference arms, sweep curves.
- Answer trace explorer: grounding → candidates → certification route → posterior → decision, rendered as a path.
- Refusal analytics by gate and by tenant.
- Ontology and alias management: view, propose alias, blocked common-word list.

**Stack.** Next.js or React + Vite, calls gateway admin API. Auth via OIDC.

**Acceptance.**
- [ ] Any answer ID resolves to a full visual trace in < 2 s.
- [ ] Promotion requires a typed confirmation and writes an audit event.

---

### M16: portal-customer

**Scope.** End-user view.

- Ask, receive cited answer or an explicit refusal with a plain-language reason.
- Click a citation → source passage, certification reason, path.
- "As of" date control.
- Feedback (correct / incorrect / unsure) → `feedback.received` event consumed by M14 as a labelled sample.

**Acceptance.**
- [ ] Refusal shows the reason class, never a blank.
- [ ] Every cited ID is clickable and resolves.

---

### M17: ci-cd (GitHub Actions)

**Workflows.**
- `contracts.yml` – validate fixtures, publish package on tag.
- `module-<name>.yml` (one per module, path-filtered) – lint, unit, contract tests, build image → GHCR locally / ECR in AWS via OIDC.
- `integration.yml` – Compose up, smoke, tear down; on PR to `main`.
- `deploy-local.yml` – manual dispatch, deploys to a self-hosted runner's Compose.
- `deploy-aws.yml` – on tag; terraform apply (dev auto, prod manual approval), sync DAGs to S3, `faas-cli up`, rolling ECS/EKS deploy, then triggers `eval_gate` and waits for `artifact.promoted` before flipping pins.

**Acceptance.**
- [ ] No long-lived AWS keys anywhere; OIDC only.
- [ ] A PR touching only `middleware/grounder` runs only that module's workflow plus integration.
- [ ] Prod deploy cannot complete without the eval gate event.

---

## 7. Event catalogue (Kafka topics)

| Topic | Producer | Consumers | Payload |
|---|---|---|---|
| `source.delta` | external / adapter | etl-realtime | doc reference, op: upsert / retract |
| `artifact.built` | etl-historical | eval-harness, portal-admin | ArtifactManifest |
| `artifact.promoted` / `artifact.rejected` | eval-harness | ci-cd, middleware (pin swap), portal-admin | version, eval summary |
| `retrieval.completed` | retrieval | answer, observability | RetrievalResult |
| `answer.produced` | answer | lake sink, eval-harness, portal-admin | AnswerEvent |
| `feedback.received` | portal-customer | eval-harness | answer_id, label |
| `rebuild.requested` | etl-realtime | etl-historical | reason, delta stats |

All events carry `trace_id`, `tenant_id`, `env`, `schema_version`.

---

## 8. Success metrics

**Leading (per artifact promotion).**
- Test accuracy ≥ current pin (target: match study's 83.2% on the reference benchmark; stretch 85%).
- Coverage minus leak (margin) ≥ current pin.
- Gold-in-top-16 ≥ 95%.
- Zero unadmitted citations in eval and in sampled production traffic.

**Lagging (monthly).**
- Customer feedback "incorrect" rate < 8% on answered questions.
- Refusal rate stable within ±5 points month over month absent corpus change.
- p95 latency within SLO 99.5% of the month.
- Mean time from delta event to retrievable < 5 minutes.

---

## 9. Gaps closed relative to the reference study

| Gap in study | Closed by |
|---|---|
| Single-box, no service boundary | M8 to M13 as services with APIs and pins |
| No incremental ingest | M5 delta index + rebuild trigger |
| No observability | M3, trace on every hop, dashboards, alerts |
| No tests, asserts inside scripts | §5.5 named tests, contract tests, integration workflow |
| Silent cache overwrite | Versioned artifact paths, `test_cache_filename_not_overwritten` |
| Truncation constant never swept | M14 sweeps; M11 config must cite a sweep |
| Graph used for abstention | M12 abstains on calibrated confidence only |
| Certification as filter halved coverage | M10 annotates, does not drop |
| No auth, tenancy, audit | M13, §5.4, admin audit events |
| Corpus-specific parse | Adapter interface in `etl/adapters/` |
| Oracle arm never re-run | M14 re-runs all reference arms per artifact |

---

## 10. Open questions

| # | Question | Owner | Blocking |
|---|---|---|---|
| Q1 | MWAA vs Airflow on EKS in AWS? MWAA is managed but costs more idle; EKS reuses the OpenFaaS cluster. | Kishore / infra-aws-agent | Yes, for M2 |
| Q2 | Generator backend for v1: Bedrock (logprob support varies by model) or self-hosted open-weights on EKS GPU? Affects M11 posterior fidelity. | Kishore | Yes, for M11 |
| Q3 | Reference corpus for local development: PubMed 10k sample, or an internal sample through the generic adapter? | Kishore | No |
| Q4 | Cross-encoder model and its read length; run the sweep before fixing. | eval-agent | No |
| Q5 | Is gate 6 (entailment verifier) required for v1 in any target environment? Off by default per study result. | Kishore / compliance | No |
| Q6 | Tenancy model: shared graph with tenant-scoped answers, or per-tenant graph artifacts? | Kishore | Yes, for M8, M13 |

---

## 11. Agent orchestration spec (`.claude/agents.yaml`)

```yaml
version: 1
defaults:
  read: [platform/contracts, docs/PRD.md]
  rules:
    - Do not modify files outside your module folder.
    - Contract changes go through a PR labelled contract-change.
    - Every module ships CLAUDE.md, README.md, Makefile, Dockerfile, tests/.
    - Run `make test` before declaring done.
agents:
  contracts-agent:        {module: platform/contracts,      deps: []}
  infra-local-agent:      {module: platform/infra/local,    deps: [contracts-agent]}
  observability-agent:    {module: platform/observability,  deps: [contracts-agent]}
  infra-aws-agent:        {module: platform/infra/aws,      deps: [infra-local-agent]}
  etl-historical-agent:   {module: etl/historical,          deps: [infra-local-agent, observability-agent]}
  functions-agent:        {module: functions,               deps: [observability-agent]}
  generator-agent:        {module: middleware/generator,    deps: [observability-agent]}
  etl-realtime-agent:     {module: etl/realtime,            deps: [etl-historical-agent]}
  grounder-agent:         {module: middleware/grounder,     deps: [etl-historical-agent]}
  graph-store-agent:      {module: middleware/graph-store,  deps: [etl-historical-agent]}
  vector-index-agent:     {module: middleware/vector-index, deps: [etl-historical-agent]}
  retrieval-agent:        {module: middleware/retrieval,    deps: [grounder-agent, graph-store-agent, vector-index-agent]}
  answer-agent:           {module: middleware/answer,       deps: [retrieval-agent, generator-agent, functions-agent]}
  gateway-agent:          {module: middleware/gateway,      deps: [answer-agent]}
  eval-agent:             {module: eval,                    deps: [answer-agent]}
  portal-admin-agent:     {module: portals/admin,           deps: [gateway-agent]}
  portal-customer-agent:  {module: portals/customer,        deps: [gateway-agent]}
  cicd-agent:             {module: .github/workflows,       deps: [], runs: continuous}
```

Suggested invocation: `claude "Read docs/PRD.md and .claude/agents.yaml. Execute agents in dependency order, parallelising where deps allow. Stop and report after each group."`

---

## 12. Phasing

- **Phase 1 (local, weeks 1 to 4):** M0, M1, M3, M4 (PubMed adapter, 10k sample), M6, M7, M8, M9, M10, M11 (local backend), M12, M13. Smoke test passes.
- **Phase 2 (local, weeks 5 to 7):** M14 with all reference arms and sweeps; M5 delta path; M15 and M16 minimal.
- **Phase 3 (AWS dev, weeks 8 to 10):** M2, M17 full, 1M-document run, eval gate wired to deploy.
- **Phase 4 (AWS prod hardening):** PHI mode, tenancy decision, SLO alerts, generic extraction adapter (P1).
