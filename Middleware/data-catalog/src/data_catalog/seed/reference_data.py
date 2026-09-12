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


def seed_purposes(session: Session, tenant_id: str) -> tuple[int, int]:
    """Purposes ship in migration 012 as system rows; this adds the non-system ones a
    deployment is expected to extend over time."""
    rows = [
        ("dataset_profiling", "Dataset profiling",
         "Measure shape, nulls and cardinality before anything is built", 140),
        ("quality_audit", "Quality audit",
         "Sample and compare derived structures against their source", 150),
        ("backfill", "Backfill",
         "Re-run a stage over history after a fix", 160),
    ]
    stmts = [
        ("INSERT INTO catalog.purpose (purpose_code, name, description, sort_order, is_system) "
         "VALUES (:c, :n, :d, :o, false) ON CONFLICT (purpose_code) DO NOTHING",
         {"c": c, "n": n, "d": d, "o": o})
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


def seed_endpoints(session: Session, tenant_id: str) -> tuple[int, int]:
    """Example endpoints beyond the system set.

    The eleven system endpoints arrive in migration 010 because they describe how the
    platform reaches storage rather than what data it holds. These are the kind a
    deployment adds for itself.
    """
    rows = [
        ("local-fs-scratch", "Local scratch space", "A second local path for experiments",
         "local", "filesystem", "anonymous", 'localhost',
         '{"root": "~/runtime_data/AKG/Local/Scratch"}'),
        ("nas-corpus", "NAS corpus mount", "An on-premises mount, path supplied per machine",
         "on_prem", "filesystem", "anonymous", 'files.internal',
         '{"env": {"root": "AKG_NAS_CORPUS_ROOT"}, "defaults": {"root": "/mnt/nas/corpus"}}'),
    ]
    stmts = [
        ("INSERT INTO catalog.app_endpoint "
         "  (app_endpoint_id, code, name, description, tech_stack, provider, "
         "   provider_service, connection_type, connection_details, env, host, "
         "   is_system, tenant_id) "
         "VALUES (:id, :c, :n, :d, 'local_fs', :p, :svc, :ct, CAST(:cd AS jsonb), "
         "        'local', :h, false, :t) "
         # Conflict on the real identity, not the generated id. Migration 013 ships the
         # same two codes as examples, with different ids -- conflicting on the primary
         # key would miss that and hit the code-uniqueness index as an error instead.
         "ON CONFLICT (tenant_id, env, code) DO NOTHING",
         {"id": _det("endpoint", f"{tenant_id}:{c}"), "c": c, "n": n, "d": d,
          "p": prov, "svc": svc, "ct": ct, "cd": cd, "h": host, "t": tenant_id})
        for c, n, d, prov, svc, ct, host, cd in rows
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
