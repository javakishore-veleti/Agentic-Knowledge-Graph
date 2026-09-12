--liquibase formatted sql

--changeset akg:003-data-catalog splitStatements:false endDelimiter:\n/
--comment data catalog
--rollback empty

-- Data catalog: domain -> dataset -> mio -> data_instance -> data_instance_exec
-- (ADR-009). MIO = Managed Informational Object.
CREATE SCHEMA IF NOT EXISTS catalog;

-- ---------------------------------------------------------------- domain

CREATE TABLE IF NOT EXISTS catalog.domain (
    domain_id   uuid        PRIMARY KEY,
    code        text        NOT NULL,
    name        text        NOT NULL,
    description text        NOT NULL DEFAULT '',
    tenant_id   text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT domain_code_ck CHECK (code ~ '^[a-z0-9][a-z0-9_-]{0,62}$')
);
CREATE UNIQUE INDEX IF NOT EXISTS domain_code_uq ON catalog.domain (tenant_id, code);

-- ---------------------------------------------------------------- dataset
-- Source data at a specific version. Immutable once acquired: a new version of the same
-- logical source is a new row, never an update, so a MIO built last month can still name
-- exactly what it read.

CREATE TABLE IF NOT EXISTS catalog.dataset (
    dataset_id     uuid        PRIMARY KEY,
    domain_id      uuid        NOT NULL REFERENCES catalog.domain (domain_id)
                               ON DELETE RESTRICT,
    code           text        NOT NULL,
    name           text        NOT NULL,
    description    text        NOT NULL DEFAULT '',
    source_version text        NOT NULL,
    -- Which adapter parses it. Edge-bearing sources parse directly; anything else goes
    -- through extraction, whose cost is reported separately (PRD B B11).
    adapter        text        NOT NULL DEFAULT 'generic-extraction',
    sub_domain     text        NOT NULL DEFAULT '',
    tenant_id      text        NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dataset_code_ck CHECK (code ~ '^[a-z0-9][a-z0-9_.-]{0,126}$')
);
CREATE UNIQUE INDEX IF NOT EXISTS dataset_version_uq
    ON catalog.dataset (domain_id, code, source_version);
CREATE INDEX IF NOT EXISTS dataset_domain_ix ON catalog.dataset (domain_id, created_at DESC);

-- ---------------------------------------------------------------- mio
-- The produced, managed artifact. Think of it as a project: it has a name, owns
-- workflows, is built from datasets, and can generate further MIOs.

CREATE TABLE IF NOT EXISTS catalog.mio (
    mio_id           uuid        PRIMARY KEY,
    domain_id        uuid        NOT NULL REFERENCES catalog.domain (domain_id)
                                 ON DELETE RESTRICT,
    code             text        NOT NULL,
    name             text        NOT NULL,
    description      text        NOT NULL DEFAULT '',

    -- What the artifact physically is: csr_graph, pgvector_index, opensearch_index,
    -- parquet_tables, blob_prefix, ...
    tech_stack       text        NOT NULL,

    -- The produced thing's shape. These describe the artifact, not the source, which is
    -- why they live here rather than on dataset.
    documents_count  bigint      NOT NULL DEFAULT 0 CHECK (documents_count >= 0),
    edges_count      bigint      NOT NULL DEFAULT 0 CHECK (edges_count     >= 0),
    size_bytes       bigint      NOT NULL DEFAULT 0 CHECK (size_bytes      >= 0),

    -- Per-layer ground truth: the internal assert plus an independent recount from the
    -- source. Both must pass before a MIO is promotable.
    validations      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    state            text        NOT NULL DEFAULT 'draft',

    -- Which artifact version is currently pinned for serving, if any.
    pinned_version   text,
    tenant_id        text        NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT mio_code_ck  CHECK (code ~ '^[a-z0-9][a-z0-9_.-]{0,126}$'),
    CONSTRAINT mio_state_ck CHECK (state IN ('draft','building','ready','live','rejected','retired')),
    -- A live MIO is being served, so it must name the version that is being served.
    CONSTRAINT mio_live_pinned_ck CHECK (state <> 'live' OR pinned_version IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS mio_code_uq ON catalog.mio (domain_id, code);
CREATE INDEX IF NOT EXISTS mio_state_ix ON catalog.mio (tenant_id, state, updated_at DESC);

-- Which datasets a MIO is built from. Many-to-many: one dataset can feed several MIOs
-- (a graph and an index over the same corpus), and a MIO can combine several datasets.
CREATE TABLE IF NOT EXISTS catalog.mio_dataset (
    mio_id     uuid NOT NULL REFERENCES catalog.mio (mio_id)         ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES catalog.dataset (dataset_id) ON DELETE RESTRICT,
    role       text NOT NULL DEFAULT 'input',
    PRIMARY KEY (mio_id, dataset_id, role),
    CONSTRAINT mio_dataset_role_ck CHECK (role IN ('input','reference','ontology'))
);
CREATE INDEX IF NOT EXISTS mio_dataset_by_dataset_ix ON catalog.mio_dataset (dataset_id);

-- Workflows a MIO owns. The engine is not named here: it is resolved from config at
-- trigger time (ADR-008).
CREATE TABLE IF NOT EXISTS catalog.mio_workflow (
    mio_id     uuid NOT NULL REFERENCES catalog.mio (mio_id) ON DELETE CASCADE,
    workflow   text NOT NULL,
    purpose    text NOT NULL DEFAULT 'build',
    PRIMARY KEY (mio_id, workflow),
    CONSTRAINT mio_workflow_purpose_ck
        CHECK (purpose IN ('build','refresh','validate','retract','calibrate'))
);

-- ---------------------------------------------------------------- app_endpoint
-- Where a technology actually lives. Several endpoints may serve the same technology
-- (local Postgres and Azure Postgres; two OpenSearch clusters), so nothing is keyed on
-- tech_stack alone.
--
-- NO CREDENTIALS HERE. secret_ref names a Key Vault entry; the secret itself never enters
-- the catalog, because these rows are returned by list APIs and rendered in a portal.

CREATE TABLE IF NOT EXISTS catalog.app_endpoint (
    app_endpoint_id uuid        PRIMARY KEY,
    code            text        NOT NULL,
    name            text        NOT NULL,
    tech_stack      text        NOT NULL,
    env             text        NOT NULL,
    host            text        NOT NULL,
    port            integer     CHECK (port IS NULL OR (port > 0 AND port <= 65535)),
    database        text,
    -- Non-secret connection options only: sslmode, index name, container name, ...
    options         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    -- e.g. "kv://akg-dev/postgres-catalog-password"
    secret_ref      text,
    is_active       boolean     NOT NULL DEFAULT true,
    tenant_id       text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT app_endpoint_code_ck CHECK (code ~ '^[a-z0-9][a-z0-9_.-]{0,62}$'),
    CONSTRAINT app_endpoint_env_ck
        CHECK (env IN ('local','azure-dev','azure-prod','aws-dev','aws-prod')),
    -- Belt and braces against a credential arriving in a field meant for options. The
    -- API model cannot express one either; this catches a direct INSERT.
    CONSTRAINT app_endpoint_no_secrets_ck CHECK (
        NOT (options ?| array['password','pwd','secret','api_key','apikey','token',
                              'connection_string','sas_token','access_key'])
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS app_endpoint_code_uq
    ON catalog.app_endpoint (tenant_id, env, code);
CREATE INDEX IF NOT EXISTS app_endpoint_tech_ix
    ON catalog.app_endpoint (tech_stack, env) WHERE is_active;

-- ---------------------------------------------------------------- data_instance
-- historical | realtime | cdc.
--
-- CDC is a continuous stream, not a series of batches. One instance per change event
-- would bury the instances that matter under millions of near-empty rows, so a MIO gets
-- at most ONE cdc instance and the id is derived rather than random.

CREATE TABLE IF NOT EXISTS catalog.data_instance (
    data_instance_id uuid        PRIMARY KEY,
    mio_id           uuid        NOT NULL REFERENCES catalog.mio (mio_id) ON DELETE CASCADE,
    kind             text        NOT NULL,
    label            text        NOT NULL,
    description      text        NOT NULL DEFAULT '',
    state            text        NOT NULL DEFAULT 'pending',
    -- For cdc: the stream position, so a restart resumes rather than replays.
    stream_cursor    text,
    tenant_id        text        NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT data_instance_kind_ck  CHECK (kind IN ('historical','realtime','cdc')),
    CONSTRAINT data_instance_state_ck
        CHECK (state IN ('pending','active','paused','completed','failed','retired')),
    -- Only a cdc instance carries a stream cursor; on a batch instance it would be
    -- meaningless and would invite code to treat one kind as the other.
    CONSTRAINT data_instance_cursor_ck CHECK (kind = 'cdc' OR stream_cursor IS NULL)
);

-- The enforcement that keeps CDC from multiplying.
CREATE UNIQUE INDEX IF NOT EXISTS data_instance_one_cdc_per_mio_uq
    ON catalog.data_instance (mio_id) WHERE kind = 'cdc';

CREATE INDEX IF NOT EXISTS data_instance_mio_ix
    ON catalog.data_instance (mio_id, kind, created_at DESC);

-- ---------------------------------------------------------------- data_instance_exec
-- One run of one data_instance.

CREATE TABLE IF NOT EXISTS catalog.data_instance_exec (
    data_instance_exec_id uuid        PRIMARY KEY,
    data_instance_id      uuid        NOT NULL REFERENCES catalog.data_instance (data_instance_id)
                                      ON DELETE CASCADE,
    status                text        NOT NULL DEFAULT 'PENDING',

    -- Summary of the technologies involved, for filtering without opening the JSON.
    input_tech            text,
    output_tech           text,

    -- List of inputs read: [{dataset_id, app_endpoint_id, location, tech_stack, rows}, ...]
    input_data_json       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    -- List of outputs written: [{app_endpoint_id, location, tech_stack, artifact_version}, ...]
    output_data_json      jsonb       NOT NULL DEFAULT '[]'::jsonb,
    -- Cache of the workflow executions for this run. wf_exec_log.data_instance_exec_id is
    -- the record; this is recounted against it by data_instance_exec_drift below.
    wf_execs_json         jsonb       NOT NULL DEFAULT '[]'::jsonb,

    -- Produced MIO, when this run generated one.
    produced_mio_id       uuid        REFERENCES catalog.mio (mio_id) ON DELETE SET NULL,

    trace_id              text        NOT NULL,
    tenant_id             text        NOT NULL,
    env                   text        NOT NULL,
    requested_by          text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    started_at            timestamptz,
    finished_at           timestamptz,

    CONSTRAINT die_status_ck CHECK (
        status IN ('PENDING','SUBMITTED','RUNNING','SUCCEEDED','FAILED','CANCELLED')
    ),
    CONSTRAINT die_terminal_ck CHECK (
        (status IN ('SUCCEEDED','FAILED','CANCELLED') AND finished_at IS NOT NULL)
     OR (status IN ('PENDING','SUBMITTED','RUNNING')  AND finished_at IS NULL)
    ),
    -- The three payloads are lists. A caller that sends an object instead of a list would
    -- otherwise be discovered much later, by a portal rendering nothing.
    CONSTRAINT die_input_is_list_ck  CHECK (jsonb_typeof(input_data_json)  = 'array'),
    CONSTRAINT die_output_is_list_ck CHECK (jsonb_typeof(output_data_json) = 'array'),
    CONSTRAINT die_wfexecs_is_list_ck CHECK (jsonb_typeof(wf_execs_json)   = 'array')
);

CREATE INDEX IF NOT EXISTS die_instance_ix
    ON catalog.data_instance_exec (data_instance_id, created_at DESC);
CREATE INDEX IF NOT EXISTS die_status_ix
    ON catalog.data_instance_exec (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS die_trace_ix ON catalog.data_instance_exec (trace_id);
CREATE INDEX IF NOT EXISTS die_input_gin
    ON catalog.data_instance_exec USING gin (input_data_json jsonb_path_ops);
CREATE INDEX IF NOT EXISTS die_output_gin
    ON catalog.data_instance_exec USING gin (output_data_json jsonb_path_ops);

-- "Which executions touched this endpoint" is a question the JSON cannot answer by join,
-- so the one relationship worth querying is recorded explicitly. Payload detail stays in
-- the JSON.
CREATE TABLE IF NOT EXISTS catalog.data_instance_exec_endpoint (
    data_instance_exec_id uuid NOT NULL REFERENCES catalog.data_instance_exec (data_instance_exec_id)
                               ON DELETE CASCADE,
    app_endpoint_id       uuid NOT NULL REFERENCES catalog.app_endpoint (app_endpoint_id)
                               ON DELETE RESTRICT,
    direction             text NOT NULL,
    PRIMARY KEY (data_instance_exec_id, app_endpoint_id, direction),
    CONSTRAINT diee_direction_ck CHECK (direction IN ('input','output'))
);
CREATE INDEX IF NOT EXISTS diee_by_endpoint_ix
    ON catalog.data_instance_exec_endpoint (app_endpoint_id, direction);

-- ---------------------------------------------------------------- mio_lineage
-- A MIO generating another MIO, recorded with the execution that did it, so provenance
-- answers "which run produced this" and not merely "what came from what".

CREATE TABLE IF NOT EXISTS catalog.mio_lineage (
    produced_mio_id       uuid NOT NULL REFERENCES catalog.mio (mio_id) ON DELETE CASCADE,
    source_mio_id         uuid NOT NULL REFERENCES catalog.mio (mio_id) ON DELETE RESTRICT,
    data_instance_exec_id uuid REFERENCES catalog.data_instance_exec (data_instance_exec_id)
                               ON DELETE SET NULL,
    PRIMARY KEY (produced_mio_id, source_mio_id),
    -- A MIO cannot be its own parent. Longer cycles are checked in the service, where the
    -- full graph is available.
    CONSTRAINT mio_lineage_no_self_ck CHECK (produced_mio_id <> source_mio_id)
);
CREATE INDEX IF NOT EXISTS mio_lineage_source_ix ON catalog.mio_lineage (source_mio_id);

-- ---------------------------------------------------------------- links and views

-- The real link between a workflow execution and the data_instance_exec it belongs to.
-- wf_execs_json is the cache; this is the record.
ALTER TABLE orchestration.wf_exec_log
    ADD COLUMN IF NOT EXISTS data_instance_exec_id uuid
        REFERENCES catalog.data_instance_exec (data_instance_exec_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS wf_exec_log_die_ix
    ON orchestration.wf_exec_log (data_instance_exec_id)
    WHERE data_instance_exec_id IS NOT NULL;

-- Cache versus recount. A non-empty result is a bug in the writer, not a reporting quirk.
CREATE OR REPLACE VIEW catalog.data_instance_exec_drift AS
SELECT e.data_instance_exec_id,
       jsonb_array_length(e.wf_execs_json) AS cached_wf_execs,
       count(w.exec_id)                    AS actual_wf_execs
FROM catalog.data_instance_exec e
LEFT JOIN orchestration.wf_exec_log w
       ON w.data_instance_exec_id = e.data_instance_exec_id
GROUP BY e.data_instance_exec_id, e.wf_execs_json
HAVING jsonb_array_length(e.wf_execs_json) <> count(w.exec_id);

-- One row per MIO with its datasets, workflows, instances and latest run: what the
-- catalog list API returns, computed once here rather than in five queries per row.
CREATE OR REPLACE VIEW catalog.mio_overview AS
SELECT m.mio_id,
       m.domain_id,
       d.code                                            AS domain_code,
       m.code,
       m.name,
       m.tech_stack,
       m.state,
       m.pinned_version,
       m.documents_count,
       m.edges_count,
       m.size_bytes,
       m.validations,
       -- Promotable only when every validation recorded passes. An empty validations
       -- object is not a pass: nothing was checked.
       (m.validations <> '{}'::jsonb
        AND NOT EXISTS (
              SELECT 1 FROM jsonb_each(m.validations) v
              WHERE v.value <> 'true'::jsonb))           AS validations_pass,
       (SELECT count(*) FROM catalog.mio_dataset  md WHERE md.mio_id = m.mio_id) AS dataset_count,
       (SELECT count(*) FROM catalog.mio_workflow mw WHERE mw.mio_id = m.mio_id) AS workflow_count,
       (SELECT count(*) FROM catalog.data_instance di WHERE di.mio_id = m.mio_id) AS instance_count,
       -- coalesce is required: bool_or over zero rows is NULL, so a MIO with no
       -- instances would report has_cdc = null rather than false.
       coalesce((SELECT bool_or(di.kind = 'cdc') FROM catalog.data_instance di
                  WHERE di.mio_id = m.mio_id), false)    AS has_cdc,
       (SELECT count(*) FROM catalog.mio_lineage l WHERE l.source_mio_id = m.mio_id)
                                                         AS generated_mio_count,
       (SELECT max(x.created_at)
          FROM catalog.data_instance_exec x
          JOIN catalog.data_instance di2 ON di2.data_instance_id = x.data_instance_id
         WHERE di2.mio_id = m.mio_id)                    AS last_exec_at,
       m.tenant_id,
       m.created_at,
       m.updated_at
FROM catalog.mio m
JOIN catalog.domain d ON d.domain_id = m.domain_id;

-- A live MIO whose validations do not all pass. Should always be empty.
CREATE OR REPLACE VIEW catalog.mio_unsafe_live AS
SELECT mio_id, code, state, validations
FROM catalog.mio_overview
WHERE state = 'live' AND NOT validations_pass;
