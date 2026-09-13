"""The reference content itself, and how it is inserted.

Every statement is conflict-tolerant. The tracker already refuses a second load, but the
inserts do not depend on that being true: a loader that only works when called exactly
once is a loader that corrupts data the first time something retries it.

Each function returns (inserted, skipped) so the Administration screen can distinguish
"loaded 13" from "loaded 0, 13 already present" — different facts that look identical if
you only report success.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

# Deterministic ids: re-running produces the same rows rather than duplicates under
# different keys, and a fixture can reference them.
_NS = uuid.UUID("6f2a1c40-0000-4000-8000-000000000000")


def _det(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"{kind}:{key}")


def _count_inserted(session: Session, statements: list[tuple[str, dict[str, Any]]]) -> tuple[int, int]:
    inserted = 0
    for sql, params in statements:
        result = session.execute(text(sql), params)
        # rowcount is 0 when ON CONFLICT DO NOTHING skipped the row.
        inserted += result.rowcount or 0
    return inserted, len(statements) - inserted


# ---------------------------------------------------------------- purposes


# The thirteen purposes the platform itself names. These used to be INSERTs in migration
# 012, which was wrong twice over: a blank database is supposed to hold schema only until
# an admin presses Load, and a workflow row carries a foreign key to purpose_code -- so
# with the migration stripped, seeding workflows failed on workflow_purpose_fk with
# nothing in the message to say the purposes had simply never been loaded.
#
# is_system is what a trigger reads to refuse deletion: these describe what the platform
# does, so a deployment extends the list rather than editing it.
_SYSTEM_PURPOSES = [
    ("initial_dataset_load", "Initial dataset loading",
     "First acquisition of a dataset from its source into a destination", 10),
    ("incremental_load", "Incremental load",
     "Deltas since the last acquisition rather than the whole corpus", 20),
    ("parsing", "Parsing", "Turn acquired files into columnar tables", 30),
    ("ontology_linking", "Ontology linking",
     "Resolve text to stable concept identifiers", 40),
    ("graph_build", "Graph build",
     "Construct the CSR graph from publisher-supplied edges", 50),
    ("indexing", "Indexing",
     "Embed and consolidate shards into one pinnable index", 60),
    ("validation", "Validation",
     "Alignment asserts and independent recounts against the source", 70),
    ("calibration", "Calibration",
     "Fit the abstention threshold on the held-out dev split", 80),
    ("evaluation", "Evaluation",
     "Run the reference arms and the promotion gate", 90),
    ("retraction", "Retraction handling",
     "Flag retracted documents so they drop out of citations", 100),
    ("export", "Export", "Publish a curated copy for downstream consumers", 110),
    ("reconciliation", "Reconciliation",
     "Recount caches against their source of truth", 120),
    ("maintenance", "Maintenance",
     "Housekeeping: release stuck runs, vacuum, prune", 130),
]

# The ones a deployment is expected to keep adding to. Not system: these are examples.
_EXTRA_PURPOSES = [
    ("dataset_profiling", "Dataset profiling",
     "Measure shape, nulls and cardinality before anything is built", 140),
    ("quality_audit", "Quality audit",
     "Sample and compare derived structures against their source", 150),
    ("backfill", "Backfill", "Re-run a stage over history after a fix", 160),
]


def seed_purposes(session: Session, tenant_id: str) -> tuple[int, int]:
    """The purpose vocabulary. Load this first: workflows reference it by foreign key."""
    stmts = [
        ("INSERT INTO catalog.purpose "
         "  (purpose_code, name, description, sort_order, is_system) "
         "VALUES (:c, :n, :d, :o, :sys) ON CONFLICT (purpose_code) DO NOTHING",
         {"c": c, "n": n, "d": d, "o": o, "sys": sys_})
        for rows, sys_ in ((_SYSTEM_PURPOSES, True), (_EXTRA_PURPOSES, False))
        for c, n, d, o in rows
    ]
    return _count_inserted(session, stmts)


# ---------------------------------------------------------------- domains


def seed_domains(session: Session, tenant_id: str) -> tuple[int, int]:
    rows = [
        ("biomedical", "Biomedical", "Literature, trials and ontologies"),
        ("enterprise", "Enterprise", "Internal documentation and knowledge bases"),
    ]
    stmts = [
        ("INSERT INTO catalog.domain (domain_id, code, name, description, tenant_id) "
         "VALUES (:id, :c, :n, :d, :t) ON CONFLICT (tenant_id, code) DO NOTHING",
         {"id": _det("domain", f"{tenant_id}:{c}"), "c": c, "n": n, "d": d, "t": tenant_id})
        for c, n, d in rows
    ]
    return _count_inserted(session, stmts)


# ---------------------------------------------------------------- endpoints


# The eleven system endpoints, in the provider model migration 011 introduced. Like the
# purposes above these were INSERTs in migration 010; they describe how the platform
# reaches storage, so is_system keeps them undeletable and a deployment adds its own
# alongside rather than editing these.
#
# connection_details keeps plain facts at the top level and variable NAMES under "env".
# A CHECK depends on that split: flattened, `"password": "AKG_PG_PASSWORD"` is
# indistinguishable from `"password": "hunter2"` to any rule that only reads keys.
_SYSTEM_ENDPOINTS = [
    # (id_suffix, code, name, description, tech_stack, provider, provider_service,
    #  connection_type, auth_mode, auth_ref, env, host, connection_details)
    ("01", "local-fs", "Local filesystem", "Files on the machine running the code",
     "local_fs", "local", "filesystem", "anonymous", "anonymous", None,
     "local", "localhost",
     '{"env": {"root": "AKG_LOCAL_DATA_ROOT"},'
     ' "defaults": {"root": "~/runtime_data/AKG/Local/FileSystem"}}'),

    ("02", "aws-s3-profile", "AWS S3 (named profile)",
     "Uses a profile from ~/.aws/credentials on this machine",
     "s3", "aws", "s3", "profile", "aws_profile", "default",
     "local", "s3.amazonaws.com",
     '{"profile": "default",'
     ' "env": {"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION"}}'),

    ("03", "aws-s3-keys", "AWS S3 (access keys)",
     "Access key and secret supplied by the environment",
     "s3", "aws", "s3", "env_vars", "env_vars", None,
     "local", "s3.amazonaws.com",
     '{"env": {"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION",'
     '         "access_key_id": "AKG_AWS_ACCESS_KEY_ID",'
     '         "secret_access_key": "AKG_AWS_SECRET_ACCESS_KEY"}}'),

    ("04", "aws-s3-role", "AWS S3 (attached role)",
     "Instance profile, ECS task role or EKS IRSA",
     "s3", "aws", "s3", "ambient", "aws_role", None,
     "aws-dev", "s3.amazonaws.com",
     '{"env": {"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION"}}'),

    ("05", "azure-blob-cli", "Azure Blob (az login)",
     "Uses the token az login left on this machine",
     "azure_blob", "azure", "blob_storage", "command", "azure_cli", None,
     "local", "blob.core.windows.net",
     # The allowlist requires a named helper; az_cli_token is what azure_cli meant.
     '{"command": "az_cli_token",'
     ' "env": {"account": "AKG_AZURE_STORAGE_ACCOUNT",'
     '         "container": "AKG_AZURE_STORAGE_CONTAINER"}}'),

    ("06", "azure-blob-sp", "Azure Blob (service principal)",
     "Client id and secret supplied by the environment",
     "azure_blob", "azure", "blob_storage", "client_credentials",
     "azure_client_secret", None, "azure-dev", "blob.core.windows.net",
     '{"env": {"account": "AKG_AZURE_STORAGE_ACCOUNT",'
     '         "container": "AKG_AZURE_STORAGE_CONTAINER",'
     '         "tenant_id": "AKG_AZURE_TENANT_ID",'
     '         "client_id": "AKG_AZURE_CLIENT_ID",'
     '         "client_secret": "AKG_AZURE_CLIENT_SECRET"}}'),

    ("07", "azure-blob-msi", "Azure Blob (managed identity)",
     "Workload identity inside Azure; no secret at all",
     "azure_blob", "azure", "blob_storage", "ambient",
     "azure_managed_identity", None, "azure-prod", "blob.core.windows.net",
     '{"env": {"account": "AKG_AZURE_STORAGE_ACCOUNT",'
     '         "container": "AKG_AZURE_STORAGE_CONTAINER"}}'),

    ("11", "pg-local", "PostgreSQL (local)", "Postgres in the local Docker stack",
     "postgres", "local", "postgres", "env_vars", "env_vars", None,
     "local", "localhost",
     '{"host": "localhost", "port": 5432, "database": "akg", "username": "akg",'
     ' "sslmode": "disable",'
     ' "env": {"host": "AKG_PG_HOST", "port": "AKG_PG_PORT",'
     '         "database": "AKG_PG_DATABASE", "username": "AKG_PG_USERNAME",'
     '         "password": "AKG_PG_PASSWORD"}}'),

    ("12", "pg-aws-rds", "PostgreSQL (AWS RDS)", "Amazon RDS for PostgreSQL",
     "postgres", "aws", "rds_postgres", "env_vars", "env_vars", None,
     "aws-dev", "CHANGE-ME.rds.amazonaws.com",
     '{"port": 5432, "database": "akg", "username": "akg", "sslmode": "require",'
     ' "env": {"host": "AKG_RDS_PG_HOST", "port": "AKG_RDS_PG_PORT",'
     '         "database": "AKG_RDS_PG_DATABASE", "username": "AKG_RDS_PG_USERNAME",'
     '         "password": "AKG_RDS_PG_PASSWORD"}}'),

    ("13", "pg-azure", "PostgreSQL (Azure Flexible Server)",
     "Azure Database for PostgreSQL",
     "postgres", "azure", "postgres_flexible_server", "env_vars", "env_vars", None,
     "azure-dev", "CHANGE-ME.postgres.database.azure.com",
     '{"port": 5432, "database": "akg", "username": "akg", "sslmode": "require",'
     ' "env": {"host": "AKG_AZURE_PG_HOST", "port": "AKG_AZURE_PG_PORT",'
     '         "database": "AKG_AZURE_PG_DATABASE",'
     '         "username": "AKG_AZURE_PG_USERNAME",'
     '         "password": "AKG_AZURE_PG_PASSWORD"}}'),

    ("21", "pubmed-ftp", "PubMed baseline (NCBI)",
     "Public FTP origin of the annual baseline",
     "ftp", "other", "ftp", "anonymous", "anonymous", None,
     "local", "ftp.ncbi.nlm.nih.gov",
     '{"path": "/pubmed/baseline/",'
     ' "env": {"base_url": "AKG_PUBMED_BASELINE_URL"}}'),
]

# Not system: the kind of endpoint a deployment adds for itself.
_EXTRA_ENDPOINTS = [
    ("local-fs-scratch", "Local scratch space", "A second local path for experiments",
     "local", "filesystem", "anonymous", "localhost",
     '{"root": "~/runtime_data/AKG/Local/Scratch"}'),
    ("nas-corpus", "NAS corpus mount", "An on-premises mount, path supplied per machine",
     "on_prem", "filesystem", "anonymous", "files.internal",
     '{"env": {"root": "AKG_NAS_CORPUS_ROOT"}, "defaults": {"root": "/mnt/nas/corpus"}}'),
]


def seed_endpoints(session: Session, tenant_id: str) -> tuple[int, int]:
    """The eleven system endpoints plus a couple of examples."""
    stmts = [
        ("INSERT INTO catalog.app_endpoint "
         "  (app_endpoint_id, code, name, description, tech_stack, provider, "
         "   provider_service, connection_type, connection_details, auth_mode, "
         "   auth_ref, env, host, is_system, tenant_id) "
         "VALUES (:id, :c, :n, :d, :tech, :p, :svc, :ct, CAST(:cd AS jsonb), :am, "
         "        :ar, :e, :h, true, :t) "
         # Conflict on the real identity (tenant, env, code), not the primary key: a
         # fixed id that collides on the code index errors instead of skipping.
         "ON CONFLICT (tenant_id, env, code) DO NOTHING",
         {"id": f"00000000-0000-4000-8000-0000000000{sfx}", "c": c, "n": n, "d": desc,
          "tech": tech, "p": prov, "svc": svc, "ct": ct, "cd": cd, "am": am, "ar": ar,
          "e": env, "h": host, "t": tenant_id})
        for sfx, c, n, desc, tech, prov, svc, ct, am, ar, env, host, cd
        in _SYSTEM_ENDPOINTS
    ] + [
        ("INSERT INTO catalog.app_endpoint "
         "  (app_endpoint_id, code, name, description, tech_stack, provider, "
         "   provider_service, connection_type, connection_details, env, host, "
         "   is_system, tenant_id) "
         "VALUES (:id, :c, :n, :d, 'local_fs', :p, :svc, :ct, CAST(:cd AS jsonb), "
         "        'local', :h, false, :t) "
         "ON CONFLICT (tenant_id, env, code) DO NOTHING",
         {"id": _det("endpoint", f"{tenant_id}:{c}"), "c": c, "n": n, "d": d,
          "p": prov, "svc": svc, "ct": ct, "cd": cd, "h": host, "t": tenant_id})
        for c, n, d, prov, svc, ct, host, cd in _EXTRA_ENDPOINTS
    ]
    return _count_inserted(session, stmts)


# ---------------------------------------------------------------- datasets


def seed_datasets(session: Session, tenant_id: str) -> tuple[int, int]:
    """Reference datasets and their source locations.

    Requires domains: the foreign key is the reason the tracker refuses this first.
    """
    rows = [
        ("biomedical", "pubmed", "PubMed baseline",
         "Annual baseline; the publisher ships citation edges, so the graph builds with "
         "no model calls", "pubmed-baseline-2026", "pubmed", "literature",
         "ftp", "ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/"),
        ("biomedical", "pubmed", "PubMed baseline", "Weekly delta",
         "pubmed-delta-2026w37", "pubmed", "literature",
         "ftp", "ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/"),
        ("biomedical", "ctgov", "ClinicalTrials registry",
         "No shipped edges; the extraction adapter is required and its cost is reported "
         "separately", "ctgov-2026-09", "generic-extraction", "trials",
         "http_url", "https://clinicaltrials.gov/api/v2/studies"),
        ("enterprise", "kb", "Engineering knowledge base", "Internal documentation",
         "kb-2026-09-04", "generic-extraction", "documentation",
         "file_server", "smb://files.internal/kb/"),
    ]
    stmts: list[tuple[str, dict[str, Any]]] = []
    for domain, code, name, desc, version, adapter, sub, kind, uri in rows:
        dataset_id = _det("dataset", f"{tenant_id}:{code}:{version}")
        stmts.append((
            "INSERT INTO catalog.dataset "
            "  (dataset_id, domain_id, code, name, description, source_version, adapter, "
            "   sub_domain, tenant_id) "
            "SELECT :id, d.domain_id, :c, :n, :desc, :v, :a, :sub, :t "
            "FROM catalog.domain d WHERE d.code = :dom AND d.tenant_id = :t "
            "ON CONFLICT (domain_id, code, source_version) DO NOTHING",
            {"id": dataset_id, "c": code, "n": name, "desc": desc, "v": version,
             "a": adapter, "sub": sub, "t": tenant_id, "dom": domain},
        ))
        # Every dataset gets its source location, so none is left unrebuildable.
        stmts.append((
            "INSERT INTO catalog.dataset_endpoint "
            "  (dataset_endpoint_id, dataset_id, role, location_kind, uri, is_primary, "
            "   tenant_id) "
            "VALUES (:eid, :did, 'source', :k, :u, true, :t) "
            "ON CONFLICT (dataset_endpoint_id) DO NOTHING",
            {"eid": _det("dsep", f"{tenant_id}:{code}:{version}:source"),
             "did": dataset_id, "k": kind, "u": uri, "t": tenant_id},
        ))
    return _count_inserted(session, stmts)


# ---------------------------------------------------------------- workflows


def seed_workflows(session: Session, tenant_id: str) -> tuple[int, int]:
    """The master workflow list. Requires purposes: every workflow declares one."""
    rows = [
        ("historical_ingest", "Historical corpus ingest",
         "Acquire, parse, link the ontology, build the CSR graph, embed, consolidate and "
         "emit a manifest. Fans out one execution per source file.",
         "corpus", "historical-ingest", "airflow", "initial_dataset_load",
         '[{"name":"source_version","label":"Source version","kind":"text","required":true},'
         ' {"name":"adapter","label":"Adapter","kind":"select","required":true,'
         '  "options":["pubmed","generic-extraction"],"default":"pubmed"},'
         ' {"name":"smoke","label":"Smoke run","kind":"bool","required":false,'
         '  "default":true,"help":"Shrinks to 12 files. Use before spending GPU time."}]'),
        ("rebuild_index", "Rebuild vector index",
         "Re-embed and consolidate shards into one pinnable index.",
         "corpus", "index", "airflow", "indexing",
         '[{"name":"model","label":"Embedding model","kind":"select","required":true,'
         '  "options":["BAAI/bge-small-en-v1.5","BAAI/bge-base-en-v1.5"],'
         '  "default":"BAAI/bge-small-en-v1.5"}]'),
        ("apply_retractions", "Apply retractions",
         "Flag retracted and corrected documents so they drop out of citations without "
         "waiting for a rebuild.",
         "corpus", "freshness", "container_apps_job", "retraction",
         '[{"name":"as_of","label":"As of date","kind":"date","required":true}]'),
        ("fit_calibration", "Fit abstention calibration",
         "Fit the confidence bias and abstention threshold on the held-out dev split. "
         "Never fitted on test.",
         "quality", "calibration", "airflow", "calibration",
         '[{"name":"dev_split","label":"Dev split","kind":"text","required":true,'
         '  "default":"dev-400"}]'),
        ("run_eval_gate", "Run the evaluation gate",
         "Reference arms, sweeps and the promotion decision for a candidate release.",
         "quality", "evaluation", "airflow", "evaluation",
         '[{"name":"release","label":"Candidate release","kind":"text","required":true}]'),
    ]
    stmts = [
        ("INSERT INTO catalog.workflow "
         "  (workflow_id, code, name, description, domain, sub_domain, "
         "   default_tech_stack, purpose, params_json, execution_model, tenant_id) "
         "VALUES (:id, :c, :n, :d, :dom, :sub, :tech, :p, CAST(:params AS jsonb), "
         "        'triggered_run', :t) "
         "ON CONFLICT (tenant_id, code) DO NOTHING",
         {"id": _det("workflow", f"{tenant_id}:{c}"), "c": c, "n": n, "d": d,
          "dom": dom, "sub": sub, "tech": tech, "p": purpose, "params": params,
          "t": tenant_id})
        for c, n, d, dom, sub, tech, purpose, params in rows
    ]
    return _count_inserted(session, stmts)


SEED_SETS: dict[str, Callable[[Session, str], tuple[int, int]]] = {
    "purposes": seed_purposes,
    "domains": seed_domains,
    "endpoints": seed_endpoints,
    "datasets": seed_datasets,
    "workflows": seed_workflows,
}


def seed_entity(session: Session, entity: str, tenant_id: str) -> tuple[int, int]:
    loader = SEED_SETS.get(entity)
    if loader is None:
        raise ValueError(f"no seed set for {entity!r}; known: {sorted(SEED_SETS)}")
    return loader(session, tenant_id)
