# Product Requirements Document

## Enterprise Agentic Knowledge Graph Platform

**Document status:** Implementation-ready draft  
**Version:** 1.0  
**Delivery model:** Local-first, AWS production  
**Repository model:** Modular monorepo  
**Primary implementation users:** Claude Code CLI multi-agent teams, software engineers, data engineers, AI engineers, platform engineers

---

## 1. Executive Summary

The Enterprise Agentic Knowledge Graph Platform is a local-first, cloud-deployable system for ingesting historical and real-time documents, building vector and graph representations, retrieving evidence, generating cited answers, verifying claims, and refusing or escalating answers when calibrated confidence is insufficient.

The platform operationalizes the useful findings and unresolved gaps from the study *Structuring 40 Million Documents into an Agentic Knowledge Graph*. It does not assume that a graph is a superior document retriever or that graph-path existence proves a claim. Dense and hybrid retrieval provide recall; the knowledge graph provides relationships, navigation, provenance, and admissibility evidence; claim verification tests generated statements; calibrated confidence controls abstention and human review.

The system shall run completely on a developer workstation using containers before any AWS deployment. The same application code, Airflow DAGs, event schemas, container images, configuration model, and infrastructure interfaces shall then be deployed to AWS. Cloud-specific behavior shall be implemented behind adapters rather than embedded in domain logic.

The initial reference domain shall use public or synthetic healthcare/diagnostic information. The architecture must remain domain-neutral so that automotive, ecommerce, insurance, technology, and other enterprise datasets can be added through domain packs without changing the core platform.

---

## 2. Product Vision

Build a professionally structured, reproducible knowledge and evidence platform that can answer:

1. What documents are relevant to this question?
2. Which entities, concepts, and relationships connect the question to those documents?
3. What exact evidence supports each generated claim?
4. What evidence conflicts with the proposed answer?
5. How confident is the system, and should it answer, refuse, or request human review?
6. Can the complete decision be reproduced using versioned documents, models, graph snapshots, prompts, policies, and indexes?

The product is not an autonomous clinical diagnostic system, treatment recommendation system, or irreversible decision maker. Healthcare content in the reference implementation is educational and operational unless a future regulated product scope is separately approved.

---

## 3. Goals

### 3.1 Product goals

- Support both bulk historical ingestion and low-latency real-time document updates.
- Provide vector, keyword, hybrid, and graph-assisted evidence retrieval.
- Produce answers composed of atomic, source-linked claims.
- Preserve an explicit evidence and provenance path for every returned claim.
- Detect contradictory or temporally invalid evidence.
- Use calibrated confidence to choose `ANSWER`, `REFUSE`, or `HUMAN_REVIEW`.
- Provide Admin and Customer portals with different permissions and experiences.
- Run locally through one documented bootstrap workflow.
- Deploy the same code and containers to AWS through GitHub Actions and Terraform.
- Provide per-layer and end-to-end evaluations, including negative controls and regression gates.
- Enable multiple coding agents to work safely through stable contracts and non-overlapping module ownership.

### 3.2 Engineering goals

- Modular monorepo with independently buildable and testable components.
- API-first and event-contract-first integration.
- No shared database tables across independently deployable services.
- Configuration-driven local/AWS provider selection.
- Idempotent ingestion and event processing.
- Traceable, versioned and reproducible knowledge artifacts.
- Horizontally scalable stateless query services.
- Explicit failure handling, retry, dead-letter and replay mechanisms.

### 3.3 Research goals

- Measure whether graph enrichment before generation improves answer correctness.
- Measure whether graph expansion improves retrieval recall without unacceptable precision loss.
- Improve natural-language-to-ontology grounding.
- Represent typed, directional, temporal and polarity-bearing relationships.
- Validate claim verifiers outside a single benchmark.
- Test section-aware retrieval without unsafe fixed-character truncation.
- Evaluate bounded two-hop graph traversal.
- Compare deterministic pipelines with agentic loops and retain loops only when metrics improve.

---

## 4. Non-Goals for Version 1

- Reproducing the complete 40-million-document PubMed experiment.
- Building 929 million edges in the first release.
- Replacing every storage engine with a custom memory-mapped implementation.
- Treating every source-code module as a separately deployed microservice.
- Allowing an LLM to execute infrastructure, data mutations, or remediation without approval.
- Making clinical diagnoses, treatment decisions, insurance determinations, or other regulated decisions.
- Training a foundation model from scratch.
- Supporting multiple cloud providers in Version 1.
- Using AWS Lambda. OpenFaaS shall provide the function execution abstraction.
- Assuming graph certification alone is a valid refusal mechanism.

---

## 5. Architecture Principles

1. **Local first:** Every mandatory feature must have a local execution path.
2. **Cloud through adapters:** AWS-specific clients must implement ports defined by domain-facing packages.
3. **Contracts before implementations:** OpenAPI, AsyncAPI, JSON Schema, and Avro/Protobuf contracts are created before producer and consumer implementations.
4. **One deployable per capability, not per class:** Split only for independent scaling, ownership, security, or release needs.
5. **Dense retrieval for recall:** Graph traversal enriches and explains; it is not presumed to replace dense retrieval.
6. **Evidence before generation:** Retrieval, authorization, graph enrichment, deduplication and reranking precede model invocation.
7. **Atomic verification:** Verify each claim against individual sources rather than concatenated evidence blobs.
8. **Confidence controls abstention:** Refusal uses calibrated signals and policy rules, not graph-path existence alone.
9. **Immutable lineage:** Raw documents, normalized documents, embeddings, indexes, graph snapshots, prompts and evaluations are versioned.
10. **Measure components independently:** Improvements must pass grounding, retrieval, graph, verification, calibration and end-to-end tests.
11. **No silent degradation:** Assertions, invariants and reconciliation checks guard alignment, truncation, citations, ordering and cache keys.
12. **Secure by default:** Authentication, authorization, tenant filtering and data classification apply before retrieval.

---

## 6. Key Architecture Decisions

### 6.1 Event backbone: Apache Kafka

Kafka is selected instead of RabbitMQ because the product requires durable event history, replay, consumer groups, multiple derived views, ordered partitions and equivalent local/AWS behavior.

- **Local:** Apache Kafka-compatible container stack.
- **AWS:** Amazon MSK.
- **Contract:** AsyncAPI plus versioned Avro or Protobuf schemas.
- **Rule:** Business services must not import an Amazon MSK-specific SDK.

RabbitMQ is excluded from the reference implementation to avoid implementing and testing two messaging semantics. A future adapter may be added without changing domain contracts.

### 6.2 Workflow orchestration: Apache Airflow

Airflow owns bulk, scheduled and dependency-oriented data workflows.

- **Local:** Airflow in Docker Compose with the same DAG repository mounted into scheduler and workers.
- **AWS target:** Airflow deployed on Amazon EKS for maximum image and plugin parity.
- **Optional future target:** Amazon MWAA after compatibility validation.
- **Not Airflow's responsibility:** Per-request synchronous query orchestration or millisecond real-time event handling.

### 6.3 Functions: OpenFaaS

OpenFaaS owns short-lived, stateless, event-triggered processing that does not justify a permanent service.

- **Local:** OpenFaaS on local Kubernetes using kind or k3d.
- **AWS:** OpenFaaS on Amazon EKS.
- **Examples:** lightweight file validation, event transformation, notification, metadata extraction dispatch.
- **Exclusions:** GPU embedding, long-running ETL, stateful APIs and core authorization.

### 6.4 Application compute

- Spring Boot microservices run locally as containers and on EKS in AWS.
- Python AI services and workers run locally as containers and on EKS or AWS Batch.
- Long-running/GPU batch workloads use local workers first and AWS Batch in production.
- Angular portals run locally through the development server and in AWS through S3 and CloudFront.

### 6.5 Storage portability

| Capability | Local implementation | AWS implementation | Port/contract |
|---|---|---|---|
| Object store | MinIO | Amazon S3 | S3-compatible object-store port |
| Operational relational data | PostgreSQL | Amazon Aurora PostgreSQL | JDBC/SQL plus migrations |
| Vector retrieval | OpenSearch | Amazon OpenSearch Service | Search repository port |
| Optional vector baseline | pgvector | Aurora PostgreSQL with pgvector | Vector repository port |
| Knowledge graph | JanusGraph/Gremlin-compatible local graph | Amazon Neptune | Graph repository port using constrained Gremlin profile |
| Cache | Redis | Amazon ElastiCache for Redis-compatible engine | Cache port |
| Events | Kafka | Amazon MSK | Kafka protocol |
| Secrets | `.env`/container secrets | AWS Secrets Manager | Secret-provider port |

The graph abstraction shall use only the Gremlin features validated against both the selected local engine and Neptune. Provider-specific optimized queries must live in separate adapters and pass shared contract tests.

---

## 7. System Context

### 7.1 Personas

#### Customer user

- Submits natural-language questions.
- Receives cited answers or explicit refusal/review status.
- Can inspect sources permitted by authorization policy.
- Can provide usefulness and correctness feedback.

#### Knowledge administrator

- Registers sources and ingestion schedules.
- Inspects document, entity, graph and index versions.
- Reprocesses failed records.
- Manages domain packs and ontology releases.

#### AI evaluator

- Creates datasets and experiment definitions.
- Compares retrieval and answering configurations.
- Reviews calibration, refusal and error budgets.
- Approves model/prompt/policy promotion.

#### Operations engineer

- Monitors ingestion, consumer lag, Airflow jobs, indexes and APIs.
- Replays events and drains dead-letter topics.
- Performs rollback and disaster-recovery procedures.

#### Security/compliance reviewer

- Reviews access decisions, data classification, lineage and audit events.
- Verifies that restricted content was excluded before retrieval.

### 7.2 External systems

- Public/synthetic reference datasets
- Enterprise document repositories through future connectors
- Identity provider
- Foundation/embedding/reranking models
- GitHub and GitHub Actions
- AWS platform services

---

## 8. Monorepo Structure

```text
enterprise-agentic-knowledge-platform/
├── README.md
├── PRD.md
├── CLAUDE.md
├── AGENTS.md
├── Makefile
├── compose.yaml
├── .env.example
├── Middleware/
│   ├── api-gateway/
│   ├── identity-access-service/
│   ├── source-registry-service/
│   ├── document-catalog-service/
│   ├── ontology-service/
│   ├── retrieval-service/
│   ├── graph-service/
│   ├── evidence-service/
│   ├── query-orchestrator-service/
│   ├── verification-service/
│   ├── confidence-policy-service/
│   ├── feedback-service/
│   └── audit-service/
├── ETL/
│   ├── airflow/
│   │   ├── dags/
│   │   ├── plugins/
│   │   └── tests/
│   ├── historical/
│   │   ├── source-import/
│   │   ├── normalization/
│   │   ├── ontology-linking/
│   │   ├── graph-build/
│   │   ├── embedding-build/
│   │   └── index-publish/
│   ├── realtime/
│   │   ├── document-event-consumer/
│   │   ├── normalization-consumer/
│   │   ├── graph-update-consumer/
│   │   ├── embedding-consumer/
│   │   └── index-update-consumer/
│   └── shared/
├── Functions/
│   └── openfaas/
│       ├── validate-document/
│       ├── transform-event/
│       ├── extract-file-metadata/
│       └── notify-review/
├── AI/
│   ├── embedding-runtime/
│   ├── reranker-runtime/
│   ├── generation-runtime/
│   ├── claim-verifier-runtime/
│   ├── entity-linker-runtime/
│   └── model-adapters/
├── Portals/
│   ├── KnowledgeAdmin/
│   ├── KnowledgeServices/
│   └── portal-shared/
├── Contracts/
│   ├── openapi/
│   ├── asyncapi/
│   ├── schemas/
│   └── examples/
├── DomainPacks/
│   ├── core/
│   └── diagnostics-reference/
├── DataMgmt/
│   ├── SyntheticDataGen/
│   ├── seed-data/
│   └── migration-tools/
├── Evaluation/
│   ├── datasets/
│   ├── harness/
│   ├── experiments/
│   ├── calibration/
│   └── reports/
├── Platform/
│   ├── local/
│   ├── kubernetes/
│   ├── helm/
│   ├── terraform/
│   │   ├── bootstrap/
│   │   ├── modules/
│   │   └── environments/
│   ├── observability/
│   ├── security/
│   └── scripts/
├── Libraries/
│   ├── java/
│   ├── python/
│   ├── typescript/
│   └── event-contracts/
├── Tests/
│   ├── contract/
│   ├── integration/
│   ├── end-to-end/
│   ├── performance/
│   └── resilience/
└── .github/
    ├── workflows/
    ├── actions/
    └── agents/
```

`KnowledgeAdmin` is the operations portal. `KnowledgeServices` is the customer-facing question and evidence portal. These names avoid exposing technical implementation details as business product names.

---

## 9. Component Responsibilities

### 9.1 Middleware services

#### API Gateway

- Single external API entry point.
- Validates access tokens and propagates subject, tenant, roles, correlation ID and trace context.
- Applies request limits and response streaming policies.
- Contains no retrieval or answering business logic.

#### Identity Access Service

- Resolves roles, attributes, tenants and document access policies.
- Provides batch authorization decisions for candidate document IDs.
- Denied documents must be removed before snippets reach AI services.

#### Source Registry Service

- Registers sources, owners, classifications, schedules and connectors.
- Maintains source configuration versions.
- Emits source-created and source-updated events.

#### Document Catalog Service

- Maintains canonical document identity, version, checksum, location, classification and processing state.
- Does not store full source documents in its relational database.
- Supports idempotency by source ID, external ID, version and checksum.

#### Ontology Service

- Manages entity types, concepts, aliases, taxonomies and ontology releases.
- Resolves stable concept identifiers.
- Provides exact, alias and hierarchy lookup APIs.

#### Retrieval Service

- Executes keyword, dense, hybrid and optional pgvector baseline retrieval.
- Applies authorization filters before returning candidates.
- Produces scored candidate documents with retrieval explanations.
- Supports version-pinned indexes.

#### Graph Service

- Traverses entity, document, citation and ontology relations.
- Supports typed, directional, temporal and polarity-aware edges.
- Returns paths and path explanations, not truth claims.
- Enforces path-length, fan-out, latency and candidate budgets.

#### Evidence Service

- Combines vector candidates and graph-derived context.
- Deduplicates, diversifies and reranks evidence.
- Produces immutable evidence bundles with exact document versions and sections.
- Detects supporting, conflicting and outdated evidence groups.

#### Query Orchestrator Service

- Owns the synchronous/streaming question lifecycle.
- Calls authorization, retrieval, graph, evidence, generation, verification and confidence services in deterministic order.
- Persists state for resumability.
- Emits lifecycle events without delegating correctness to event arrival order.

#### Verification Service

- Decomposes generated answers into atomic claims.
- Tests each claim against individual evidence items.
- Detects entailment, contradiction and insufficient evidence.
- Removes unsupported claims before response composition.

#### Confidence Policy Service

- Combines calibrated generation confidence, verification results, retrieval sufficiency, conflict signals and domain policy.
- Returns `ANSWER`, `REFUSE`, or `HUMAN_REVIEW` plus reason codes.
- Versions all thresholds and policies.
- Does not use graph path existence as the sole confidence signal.

#### Feedback Service

- Captures user ratings, corrections, source challenges and reviewer outcomes.
- Separates product feedback from evaluation ground truth until reviewed.

#### Audit Service

- Writes append-only query decision records.
- Captures actor, policy, document versions, graph version, index version, model version, prompt version and final disposition.
- Exposes authorized audit-search APIs.

### 9.2 ETL responsibilities

#### Historical ETL

Airflow DAGs shall manage:

1. Source snapshot registration
2. Raw ingestion to object storage
3. Validation and quarantine
4. Normalization and section preservation
5. Entity and ontology linking
6. Graph edge generation
7. Embedding generation
8. Vector index creation
9. Graph snapshot creation
10. Reconciliation and quality gates
11. Atomic publication of compatible graph/index/catalog versions

Large processing steps shall execute as containerized jobs. Airflow workers should orchestrate jobs rather than perform all CPU/GPU computation inside scheduler processes.

#### Real-time data management

Real-time consumers shall process document changes through Kafka:

```text
document.received.v1
  -> document.normalized.v1
  -> document.entities-linked.v1
  -> graph.edges-updated.v1
  -> document.embedding-created.v1
  -> search.document-indexed.v1
  -> document.ready.v1
```

Every consumer must:

- Be idempotent.
- Commit offsets only after durable completion.
- Record document and processing versions.
- Retry transient errors with limits.
- Route poison records to a dead-letter topic.
- Support controlled replay.
- Emit trace context and processing metrics.
- Reject incompatible schema versions.

### 9.3 OpenFaaS functions

Functions are permitted only when all conditions apply:

- Stateless execution
- Short bounded duration
- Small resource requirement
- Event or HTTP trigger
- No multi-step transaction ownership
- No GPU requirement

If a function develops durable state, complex retries, long execution or independent scaling policies, promote it into an ETL worker or service.

---

## 10. Functional Requirements

### FR-001: Source registration

An administrator shall register a data source with name, domain pack, owner, classification, ingestion mode, schedule, connector configuration and retention policy.

**Acceptance criteria**

- Secrets are referenced, never stored in source configuration.
- Every update creates a new configuration version.
- Disabled sources produce no new work.

### FR-002: Historical ingestion

An administrator shall start or schedule a historical ingestion through Airflow.

**Acceptance criteria**

- A failed task can restart without duplicating published records.
- Each run exposes counts for received, accepted, rejected, quarantined and published documents.
- Publication occurs only after reconciliation succeeds.

### FR-003: Real-time ingestion

The platform shall accept document-created, document-updated and document-deleted events.

**Acceptance criteria**

- Events with the same idempotency key produce one effective state transition.
- Updates create a new document version.
- Deletes create tombstones and remove content from future retrieval within a configurable SLO.

### FR-004: Section-aware normalization

The platform shall preserve document structure such as title, abstract, methods, results and conclusions instead of using an arbitrary character cutoff.

**Acceptance criteria**

- Each chunk retains document ID, version, section, offsets and checksum.
- Experiments can vary chunk policy without overwriting earlier artifacts.

### FR-005: Entity and ontology grounding

The platform shall map questions and documents to versioned domain concepts using an ensemble of exact match, aliases, semantic candidates and reranking.

**Acceptance criteria**

- Grounding returns candidate IDs, confidence, method and ontology version.
- Unknown concepts remain unknown; the system cannot invent an ontology identifier.
- Precision and recall are measured independently.

### FR-006: Graph construction

The platform shall construct document, entity, ontology, citation and evidence relationships.

**Acceptance criteria**

- Edges contain type, direction, source, extraction method, validity interval and confidence where applicable.
- Deterministic source metadata edges are distinguishable from model-inferred edges.
- Graph counts reconcile with accepted normalized inputs.

### FR-007: Vector and hybrid retrieval

The platform shall support keyword, dense, hybrid and pgvector baseline retrieval.

**Acceptance criteria**

- Results include score components, index version and applied authorization filters.
- Exact evaluation datasets can calculate recall@k, precision@k, MRR and nDCG.

### FR-008: Graph enrichment

The platform shall enrich dense retrieval results with bounded graph paths.

**Acceptance criteria**

- One-hop and configurable two-hop traversal are supported.
- Traversal enforces maximum fan-out, candidates, execution time and path count.
- Graph expansion results are reranked before evidence assembly.

### FR-009: Evidence bundle

The platform shall create an immutable, versioned bundle containing question, candidates, selected passages, graph paths, conflicts and provenance.

**Acceptance criteria**

- A bundle can be replayed without querying the newest indexes.
- Every passage refers to an immutable document version and offsets.

### FR-010: Cited response generation

The platform shall generate responses using only the authorized evidence bundle.

**Acceptance criteria**

- Each factual claim contains one or more internal evidence references.
- Generated citations are parsed and validated against the bundle.
- Invalid citations are removed and recorded.

### FR-011: Claim verification

The platform shall decompose the response into atomic claims and verify each against individual evidence sources.

**Acceptance criteria**

- Results classify claims as entailed, contradicted or insufficient.
- Unsupported claims are removed or cause review according to policy.
- The verifier cannot evaluate itself as the only ground truth.

### FR-012: Confidence and abstention

The platform shall make a policy-controlled disposition.

**Acceptance criteria**

- Decisions include reason codes and calibrated component scores.
- Coverage, accuracy, selective accuracy and risk-coverage curves are reported.
- Threshold selection uses development data, never the final test set.

### FR-013: Customer portal

KnowledgeServices shall allow authorized users to ask questions, view streamed status, read answers, inspect citations and submit feedback.

### FR-014: Admin portal

KnowledgeAdmin shall show source health, Airflow runs, Kafka lag, failed records, graph/index versions, evaluation results, policy versions and audit trails.

### FR-015: Human review

Reviewers shall receive a queue of escalated questions with evidence, claims, conflicts and reason codes and may approve, revise or reject an answer.

### FR-016: Reproducibility

The platform shall reproduce a prior decision using pinned artifacts where retention policy permits.

---

## 11. API and Event Standards

### 11.1 API conventions

- OpenAPI 3.1 specifications are authoritative.
- APIs use `/api/v1` versioning.
- Errors use RFC 9457 Problem Details.
- Every request accepts or creates a correlation ID.
- Long queries support Server-Sent Events for ordered progress and final output.
- Pagination uses opaque cursors.
- Idempotent commands accept `Idempotency-Key`.

### 11.2 Core query endpoints

```text
POST /api/v1/queries
GET  /api/v1/queries/{queryId}
GET  /api/v1/queries/{queryId}/events
GET  /api/v1/queries/{queryId}/evidence
POST /api/v1/queries/{queryId}/feedback
GET  /api/v1/reviews
POST /api/v1/reviews/{reviewId}/decisions
```

### 11.3 Query disposition

```json
{
  "queryId": "uuid",
  "status": "ANSWERED",
  "disposition": "ANSWER",
  "answer": "...",
  "claims": [],
  "citations": [],
  "confidence": {
    "overall": 0.91,
    "policyVersion": "confidence-policy-1.0.0"
  },
  "artifactVersions": {
    "documentSnapshot": "...",
    "vectorIndex": "...",
    "graphSnapshot": "...",
    "ontology": "...",
    "model": "...",
    "prompt": "..."
  }
}
```

### 11.4 Event envelope

Every Kafka message shall use a common envelope:

```json
{
  "eventId": "uuid",
  "eventType": "document.normalized",
  "eventVersion": 1,
  "occurredAt": "ISO-8601 timestamp",
  "producer": "normalization-consumer",
  "correlationId": "uuid",
  "causationId": "uuid",
  "tenantId": "tenant-or-domain",
  "partitionKey": "canonical-document-id",
  "classification": "PUBLIC",
  "payload": {}
}
```

### 11.5 Schema evolution

- Backward-compatible changes remain in the same event major version.
- Breaking changes produce a new topic/event version.
- Producers and consumers pass contract compatibility tests in CI.
- Consumers must tolerate unknown optional fields.

---

## 12. Local Development Environment

### 12.1 Prerequisites

- Docker and Docker Compose
- Java LTS supported by the selected Spring Boot release
- Node.js LTS and Angular CLI
- Python 3.12 or repository-pinned version
- kind or k3d for OpenFaaS and Kubernetes parity
- Terraform
- Make or Task runner

### 12.2 Local profiles

#### `core`

PostgreSQL/pgvector, Kafka, object storage, Redis, OpenSearch and essential Middleware services.

#### `data`

Adds Airflow, historical workers and real-time consumers.

#### `graph`

Adds local graph database and graph service.

#### `ai`

Adds local embedding, reranker, verifier and generation adapters. Small models or deterministic stubs are allowed for developer machines.

#### `full`

Adds OpenFaaS, both portals, observability and all integration services.

### 12.3 Required developer commands

```text
make doctor
make bootstrap
make up-core
make up-full
make seed
make smoke-test
make test
make evaluate-small
make down
```

`make bootstrap && make up-full && make seed && make smoke-test` shall create a demonstrable local system without manual database editing.

### 12.4 Local/AWS parity rules

- Identical application container images are promoted to AWS.
- Identical Airflow DAG source is used locally and in AWS.
- Kafka topic names and schemas remain identical except environment prefixing.
- Provider selection occurs through configuration.
- Local substitutes must pass the same repository contract tests as AWS adapters.
- No local-only business logic.

---

## 13. AWS Target Architecture

### 13.1 AWS services

- Amazon EKS: Spring Boot services, Python APIs, Airflow and OpenFaaS
- Amazon ECR: immutable container images
- Amazon MSK: Kafka event backbone
- Amazon S3: raw, normalized, evidence, evaluation and model artifacts
- Amazon OpenSearch Service: keyword, vector and hybrid retrieval
- Amazon Neptune: production graph store
- Amazon Aurora PostgreSQL: service-owned relational stores and optional pgvector baseline
- Amazon ElastiCache: distributed cache
- AWS Batch: large historical processing, embedding and evaluation jobs
- AWS Step Functions: optional AWS infrastructure-level batch coordination where Airflow launches or monitors AWS jobs
- AWS Secrets Manager and KMS: secrets and encryption
- CloudFront and S3: Angular portals
- Amazon Cognito or enterprise identity federation: reference authentication
- CloudWatch, X-Ray and managed OpenTelemetry components: observability
- CloudTrail, AWS Config, GuardDuty and Security Hub: audit and security posture

### 13.2 Environment strategy

- Separate AWS accounts for shared-services, dev, QA, staging and production where feasible.
- Separate VPCs and data stores per environment.
- No production data copied to lower environments.
- Synthetic datasets are the default outside production.
- Terraform remote state uses encrypted S3 storage and locking.

### 13.3 Deployment portability

Helm charts shall accept provider configuration without embedding secrets. Terraform provisions AWS services and installs platform charts. Kubernetes manifests shall not contain AWS account IDs, credentials or environment-specific endpoints.

---

## 14. Security, Privacy and Governance Requirements

### SEC-001 Authentication

All non-public APIs require OIDC authentication. Service-to-service identity shall use workload identity and short-lived credentials.

### SEC-002 Authorization before retrieval

Tenant, classification and subject permissions must constrain search and graph access before content is exposed to AI models.

### SEC-003 Encryption

All network traffic uses TLS. All persistent AWS data uses customer-managed or approved KMS keys according to classification.

### SEC-004 Secrets

GitHub and repository files shall contain no long-lived AWS credentials. GitHub Actions shall use OIDC role assumption.

### SEC-005 Audit

Security-relevant and answer-decision actions produce immutable audit events with appropriate retention.

### SEC-006 Sensitive data

The platform shall classify and optionally de-identify PII/PHI before indexing. Raw and de-identified artifacts must use separate locations and permissions.

### SEC-007 Prompt and content defenses

- Retrieved text is treated as untrusted data.
- Instructions contained in documents cannot override system policies.
- Tool access is allowlisted.
- Output passes content, citation and sensitive-data validation.

### SEC-008 Supply chain

- Generate SBOMs.
- Scan source, dependencies, containers and IaC.
- Sign images.
- Pin GitHub Actions to trusted versions or commit SHAs.
- Block promotion on critical unresolved vulnerabilities according to policy.

---

## 15. Non-Functional Requirements

### 15.1 Availability and recovery

- Query plane target: 99.9% monthly availability after production hardening.
- Administrative ingestion may degrade independently of query availability.
- Define RPO and RTO per data class before production release.
- Restore tests are required, not only backup configuration.

### 15.2 Performance targets for initial release

- Query accepted: p95 under 500 ms.
- Initial streaming status: p95 under 1 second.
- Retrieval stage: p95 under 2 seconds for reference scale.
- Graph enrichment: p95 under 1.5 seconds within configured budgets.
- Complete non-generative decision: p95 under 5 seconds.
- Full answer latency: measured separately by model and response length; no fabricated universal SLA.
- Real-time document searchable freshness: target under 5 minutes for normal events.

### 15.3 Scale targets

Version 1 validation tiers:

- Small: 10,000 documents
- Medium: 100,000 documents
- Large reference: 1,000,000 documents

Scale tests must record document count, chunks, entities, edges, index size, processing duration, infrastructure size and cost.

### 15.4 Reliability

- All consumers are idempotent.
- Dead-letter topics are monitored.
- Replay cannot corrupt current state.
- Published graph and vector versions are compatible and atomically selected.
- Partial index builds never become queryable.

### 15.5 Maintainability

- Minimum 80% coverage for domain logic; generated/configuration code may use justified exclusions.
- Architecture tests enforce package and dependency boundaries.
- Every service includes health, readiness and metrics endpoints.
- Every deployable owns README, OpenAPI/AsyncAPI references, Dockerfile, tests and runbook.

---

## 16. Observability Requirements

Every query must be traceable across gateway, retrieval, graph, evidence, generation, verification and confidence services.

### Required metrics

- Request rate, errors, latency and saturation
- Kafka producer errors, consumer lag, retries and DLQ counts
- Airflow run duration, task failures and data-quality outcomes
- Documents/chunks/entities/edges processed
- Retrieval recall proxies and score distributions
- Graph paths produced, pruned and timed out
- Claims entailed, contradicted and unsupported
- Answer/refusal/review distribution by policy version
- Model tokens, latency and estimated cost
- Cache hit rate keyed by complete version context
- Freshness from source event to searchable document

### Required logs

- Structured JSON
- Correlation, causation, query and trace identifiers
- No raw sensitive document text by default
- Explicit reason codes rather than free-text-only failures

### Required dashboards

- Query service health
- Data pipeline health
- Retrieval and graph quality
- Verification and refusal quality
- Cost and capacity
- Security and audit anomalies

---

## 17. Evaluation Framework

### 17.1 Evaluation layers

1. Normalization correctness
2. Entity-linking precision/recall
3. Retrieval recall@k, precision@k, MRR and nDCG
4. Graph candidate recall and path validity
5. Reranking quality
6. Citation validity
7. Claim entailment/contradiction performance
8. Answer correctness
9. Confidence calibration
10. Coverage, selective accuracy and risk-coverage
11. Latency, throughput and cost

### 17.2 Required experiment arms

| Arm | Retrieval | Graph behavior | Generation/refusal |
|---|---|---|---|
| A | Dense | None | Generate + calibrated confidence |
| B | Hybrid | None | Generate + calibrated confidence |
| C | Dense | Provenance only | Generate + calibrated confidence |
| D | Dense | Filter before generation | Generate + calibrated confidence |
| E | Dense | Expand + rerank | Generate + calibrated confidence |
| F | Hybrid | Expand + rerank | Generate + calibrated confidence |
| G | Best deterministic arm | Optional bounded agent loop | Same confidence policy |

Arm G is promoted only if it improves predefined metrics on held-out data without violating latency and cost budgets.

### 17.3 Negative controls

- Questions with unknown ontology concepts
- Questions whose evidence postdates an `asOf` time
- Questions with no supporting documents
- Contradictory evidence
- Adversarial distractor documents
- Incorrect citations
- Shuffled graph/document alignment
- Truncated conclusion sections
- Duplicate and out-of-order events
- Stale cache keys

### 17.4 Dataset discipline

- Development, validation and test splits are immutable after publication.
- Test results cannot choose thresholds.
- Oracle and blind/reference arms cannot be selected for deployment.
- Evaluation reports record code commit and every artifact version.

---

## 18. GitHub Actions and Delivery Requirements

### 18.1 Workflows

```text
.github/workflows/
  pr-contracts.yml
  pr-java.yml
  pr-python.yml
  pr-angular.yml
  pr-infrastructure.yml
  security.yml
  build-images.yml
  local-e2e.yml
  deploy-dev.yml
  evaluate-dev.yml
  promote.yml
  rollback.yml
  drift-detection.yml
```

### 18.2 Pull-request gates

- Formatting and linting
- Unit and architecture tests
- API and event contract compatibility
- Database migration validation
- Container build
- Dependency, secret, SAST and IaC scanning
- Affected integration tests
- Small deterministic evaluation suite

### 18.3 Deployment flow

1. Merge to `develop` builds affected immutable artifacts.
2. Images are tagged with commit SHA and semantic version where applicable.
3. GitHub Actions assumes an environment-specific AWS role through OIDC.
4. Terraform plan is reviewed.
5. Dev deployment installs exact immutable images.
6. Smoke, contract and evaluation suites run.
7. Promotion moves the same artifacts to QA and staging.
8. Production requires protected-environment approval.
9. Canary or blue/green checks determine completion or rollback.

### 18.4 Monorepo affected-build policy

Changes to a deployable rebuild that deployable and its dependent contract tests. Changes to shared libraries rebuild all declared consumers. A machine-readable dependency map is mandatory.

---

## 19. Claude Code Multi-Agent Delivery Model

### 19.1 Coordination rules

- One lead/planning agent owns architecture decisions, integration order and acceptance status.
- Each implementation agent owns a defined directory set.
- Agents must not modify another agent's owned directory without an explicit reassignment.
- Contract agents publish APIs/events before implementation agents start dependent work.
- Shared-library changes require lead approval because they fan out across components.
- Every agent delivers code, tests, documentation and a handoff note.
- Agents use small branches and pull requests; integration occurs by dependency wave.
- No agent may weaken a test or quality gate merely to make a build pass.

### 19.2 Required repository agent files

#### Root `CLAUDE.md`

Defines product goals, commands, architecture principles, forbidden shortcuts, module boundaries and completion rules.

#### Directory `CLAUDE.md` files

Each major directory defines:

- Ownership boundary
- Languages and frameworks
- Allowed dependencies
- Commands
- Contracts consumed and produced
- Testing expectations
- Files that must not be changed

#### `.github/agents/`

Provide role definitions:

- `architecture-agent.md`
- `contracts-agent.md`
- `spring-service-agent.md`
- `etl-airflow-agent.md`
- `realtime-kafka-agent.md`
- `ai-runtime-agent.md`
- `graph-agent.md`
- `angular-portal-agent.md`
- `platform-agent.md`
- `security-agent.md`
- `evaluation-agent.md`
- `integration-agent.md`

### 19.3 Agent work-package template

Every work package must state:

```text
Work package ID:
Objective:
Owned directories:
Read-only dependencies:
Contracts consumed:
Contracts produced:
Functional requirements:
Non-functional requirements:
Required tests:
Commands to validate:
Artifacts to deliver:
Out of scope:
Blocked by:
Unblocks:
Definition of done:
```

### 19.4 Implementation waves

#### Wave 0: Architecture foundation

- Repository skeleton
- ADR template and initial decisions
- Local bootstrap
- CI foundations
- Coding and testing standards

#### Wave 1: Contracts and shared foundations

- OpenAPI and AsyncAPI specifications
- Event envelope and schemas
- Domain identifiers and error model
- Observability and security libraries
- Testcontainers-based contract-test harness

#### Wave 2: Data foundation

- Source registry
- Document catalog
- Object storage adapters
- PostgreSQL migrations
- Kafka topics and schema governance
- Synthetic/reference data generator

#### Wave 3: Historical and real-time ingestion

- Airflow historical DAGs
- Containerized parsing/normalization jobs
- Real-time Kafka consumers
- Reconciliation, DLQ and replay

#### Wave 4: Retrieval and graph

- Embeddings and index writer
- Keyword/dense/hybrid retrieval
- Ontology service and linker
- Graph builder and traversal
- Version publication protocol

#### Wave 5: Answering and verification

- Evidence assembly
- Query orchestration and streaming
- Model adapters
- Atomic claim verification
- Confidence policy
- Citation validation

#### Wave 6: Portals and operations

- KnowledgeServices portal
- KnowledgeAdmin portal
- Review workflow
- Operational dashboards

#### Wave 7: AWS deployment

- Terraform environments
- EKS platform
- MSK, S3, OpenSearch, Neptune and Aurora adapters
- GitHub OIDC and promotion workflows
- Backup, restore and resilience tests

#### Wave 8: Research extensions

- Evidence filtering before generation
- Two-hop traversal
- Relation polarity and temporal reasoning
- Cross-domain verifier validation
- Deterministic-versus-agent-loop evaluation

### 19.5 Parallel work constraints

Agents may operate in parallel within a wave only after consumed contracts are merged. Recommended parallel groups:

- Spring services with independent databases
- Historical ETL and real-time consumers after event schemas exist
- Graph and vector adapters after canonical document/entity models exist
- Admin and customer portals after API mocks exist
- Terraform modules for independent AWS services

Integration and schema migrations must be serialized through the lead agent.

---

## 20. Data Model

### 20.1 Core entities

- Tenant
- Source
- SourceConfigurationVersion
- IngestionRun
- Document
- DocumentVersion
- Section
- Chunk
- Ontology
- OntologyVersion
- Concept
- EntityMention
- GraphNode
- GraphEdge
- EmbeddingArtifact
- SearchIndexVersion
- GraphSnapshotVersion
- Query
- EvidenceBundle
- EvidenceItem
- GeneratedClaim
- ClaimVerification
- ConfidenceDecision
- Citation
- ReviewCase
- Feedback
- AuditRecord

### 20.2 Required temporal fields

Knowledge artifacts shall distinguish:

- `eventTime`: when the source event happened
- `ingestedAt`: when the platform received it
- `validFrom`/`validTo`: when a claim or relationship is valid
- `publishedAt`: when an artifact became queryable
- `supersededAt`: when replaced

### 20.3 Graph edge minimum model

```text
edgeId
sourceNodeId
targetNodeId
edgeType
direction
polarity: SUPPORTS | CONTRADICTS | NEUTRAL | UNKNOWN
validFrom
validTo
sourceDocumentVersionId
derivation: SOURCE_METADATA | DETERMINISTIC_RULE | MODEL_INFERRED | HUMAN_VERIFIED
confidence
createdByVersion
```

---

## 21. Version Publication Protocol

Vector indexes, graph snapshots and catalogs may finish at different times. The system shall never mix incompatible versions accidentally.

1. Build artifacts under unpublished version IDs.
2. Run reconciliation and evaluation gates.
3. Write a release manifest containing compatible versions.
4. Atomically set the active release-manifest pointer.
5. Query orchestration resolves the pointer once per query.
6. All downstream calls carry resolved versions.
7. Rollback changes the pointer to the prior compatible manifest.

---

## 22. Failure Handling

### 22.1 Pipeline failures

- Transient failures retry with exponential backoff and jitter.
- Validation failures enter quarantine with reason codes.
- Poison events enter a DLQ.
- Operators can replay a selected source, run, partition, document or event range.
- Replays use idempotency and never mutate published historical artifacts.

### 22.2 Query failures

- Failure in graph enrichment may fall back to dense/hybrid evidence only when policy permits and the response declares degraded provenance.
- Verification failure cannot silently return an unverified answer.
- Model timeout produces retry, alternate model or explicit incomplete/refused response according to policy.
- Authorization service failure is fail-closed.

### 22.3 Cache correctness

Cache keys must include tenant, permissions fingerprint, normalized question, document release, vector index, graph snapshot, ontology, model, prompt and confidence-policy versions as applicable.

---

## 23. Product Milestones

### Milestone 1: Local platform foundation

- Monorepo, contracts and development environment
- Kafka, PostgreSQL/pgvector, MinIO, OpenSearch and observability running
- Synthetic/reference source registered

### Milestone 2: Historical ingestion

- Airflow pipeline processes at least 10,000 documents
- Normalized sections, entities, embeddings and graph edges published
- Quality and reconciliation report produced

### Milestone 3: Real-time updates

- Created, updated and deleted documents flow through Kafka
- Search and graph state converge within freshness target
- Replay and DLQ demonstrated

### Milestone 4: Evidence question answering

- Hybrid retrieval, graph enrichment, evidence bundle and cited answer
- Atomic claim verification
- Answer/refuse/review decision

### Milestone 5: Portals

- Customer question/evidence experience
- Admin source, pipeline, version and review experience

### Milestone 6: Evaluation study

- Arms A–F executed on fixed held-out dataset
- Report explicitly states where graph features help, hurt or do not change outcomes

### Milestone 7: AWS dev deployment

- GitHub Actions OIDC deployment
- EKS, MSK, S3, OpenSearch, Neptune and Aurora adapters
- Same reference scenario passes locally and in AWS dev

### Milestone 8: Production hardening

- Threat model
- Performance/resilience tests
- Backup/restore
- Operational runbooks
- Security and governance approval checklist

---

## 24. Release Acceptance Criteria

Version 1 is complete only when:

1. A clean workstation can launch the full local reference system using documented commands.
2. Historical Airflow ingestion publishes a consistent graph/vector release.
3. Real-time create, update and delete events update queryable state idempotently.
4. The customer portal can submit a question and inspect cited evidence.
5. Every returned claim has validated evidence or is removed.
6. Unsupported questions result in a reasoned refusal or human review.
7. A prior answer can be reproduced from recorded artifact versions.
8. All required evaluation arms run on fixed development/test splits.
9. Graph contributions are reported independently from dense/hybrid retrieval.
10. GitHub Actions deploys immutable artifacts to AWS dev using OIDC.
11. Local and AWS adapter contract suites both pass.
12. Kafka replay, DLQ recovery, index rollback and authorization failure are demonstrated.
13. No critical security findings remain open under the release policy.
14. Runbooks cover deployment, rollback, replay, restore, secret rotation and incident triage.

---

## 25. Success Metrics

### Product

- Percentage of questions answered, refused and routed to review
- Citation inspection rate and user feedback
- Reviewer agreement and correction rate
- Time to reproduce an answer decision

### Knowledge quality

- Grounding precision and recall
- Gold-document recall@k
- Valid provenance-path rate
- Citation correctness
- Claim entailment and contradiction accuracy
- Expected calibration error
- Selective accuracy and risk-coverage curve

### Platform

- Ingestion throughput and freshness
- Query-stage p50/p95/p99 latency
- Kafka lag and DLQ rate
- Airflow success/recovery rate
- Availability and error budget
- Cost per 1,000 documents processed
- Cost per answered question

---

## 26. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Too many microservices slow delivery | Deploy by capability; allow modular monoliths initially where scaling/security boundaries do not require separation |
| Local stack overwhelms developer machines | Compose profiles, small models, deterministic AI stubs and reduced datasets |
| Local graph behavior differs from Neptune | Constrained Gremlin profile and shared adapter contract tests |
| Airflow used for real-time requests | Keep Kafka consumers and query orchestrator separate |
| OpenFaaS becomes a second microservice platform | Strict function eligibility rules and promotion path |
| Graph paths mistaken for truth | Typed/polarity edges plus independent claim verification |
| Evaluation metrics improve incorrectly | Layer-specific ground truth, negative controls and invariant tests |
| Agent-generated code creates inconsistency | Contract-first waves, directory ownership and lead-agent integration |
| AWS cost grows before value is demonstrated | Local-first milestones, scale tiers, budgets and automatic non-production shutdown |
| Sensitive content reaches models | Authorization and classification before retrieval; de-identification and audit |

---

## 27. Initial Architecture Decision Records

The implementation must create these ADRs before feature development:

1. ADR-001 Modular monorepo and deployable boundaries
2. ADR-002 Kafka/MSK event backbone
3. ADR-003 Airflow responsibility boundary
4. ADR-004 OpenFaaS function eligibility
5. ADR-005 Local/AWS storage adapter strategy
6. ADR-006 Dense retrieval plus graph provenance
7. ADR-007 Claim verification and calibrated abstention
8. ADR-008 Versioned release-manifest publication
9. ADR-009 Authentication and pre-retrieval authorization
10. ADR-010 Evaluation and promotion gates

---

## 28. First Claude Code Execution Prompt

Use the following after placing this PRD in the repository:

```text
Read PRD.md completely. Do not generate the entire system in one pass.

Act as the lead architecture agent. For Wave 0 only:
1. Propose the exact repository skeleton without implementing business features.
2. Create ADR-001 through ADR-010 as concise decision drafts consistent with the PRD.
3. Create root CLAUDE.md and scoped CLAUDE.md files for each major directory.
4. Create agent role files and work packages for Waves 1 and 2.
5. Define the module dependency map and directory ownership table.
6. Create local bootstrap and CI foundation stubs with tests that fail clearly where implementation is intentionally pending.
7. Do not introduce AWS Lambda, RabbitMQ, a second frontend framework, or shared service database tables.
8. Record ambiguities as explicit decisions required; do not silently invent product behavior.

Before editing, show the proposed work packages, owned directories, dependencies,
parallelizable groups and integration order. After implementation, run the Wave 0
validation commands and produce a handoff report containing completed items,
failures, assumptions and the exact next work packages that can run in parallel.
```

---

## 29. Final Product Positioning

This project is an enterprise-oriented experimental platform, not a claim of completed clinical or autonomous intelligence. Its professional value comes from making every layer measurable and deployable:

- Historical and real-time knowledge ingestion
- Dense and hybrid retrieval
- Graph relationships and provenance
- Claim-level verification
- Calibrated refusal and human review
- Local-to-AWS portability
- Security, audit and operational controls
- Reproducible research comparing where graphs help and where they do not

The project shall report negative results as first-class outcomes. A simpler deterministic pipeline that outperforms an agentic loop is the preferred production result.
