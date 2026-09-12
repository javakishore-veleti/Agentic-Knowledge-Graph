-- Engine-neutral workflow tables (ADR-008).
--
--   wf_batch      one row per batch execution instance  (the header)
--   wf_exec_log   one row per individual execution      (the detail)
--
-- wf_exec_log.wf_batch_id is nullable: an ad-hoc single run from the Admin portal has no
-- batch, a 1,334-file ingest has one batch and 1,334 detail rows.
CREATE SCHEMA IF NOT EXISTS orchestration;

CREATE TABLE IF NOT EXISTS orchestration.wf_batch (
    wf_batch_id     uuid        PRIMARY KEY,

    -- The logical batch, e.g. 'pubmed-baseline-2026-ingest'.
    batch_name      text        NOT NULL,
    -- One instance of that batch, e.g. '2026-09-12-01'. Unique per batch per tenant, so
    -- re-running a batch cannot silently merge into the previous instance's counts.
    batch_instance  text        NOT NULL,

    domain          text        NOT NULL,
    sub_domain      text        NOT NULL,
    tech_stack      text        NOT NULL,
    status          text        NOT NULL DEFAULT 'PENDING',
    input_data      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    output_data     jsonb,
    error           jsonb,

    -- Denormalised counters, maintained by the orchestrator so the Admin portal can page
    -- a batch list without aggregating millions of detail rows. They are a cache, and
    -- wf_batch_drift below recounts them against the detail table -- the same
    -- invariant-plus-recount discipline the artifact manifests use.
    total_count     integer     NOT NULL DEFAULT 0 CHECK (total_count     >= 0),
    succeeded_count integer     NOT NULL DEFAULT 0 CHECK (succeeded_count >= 0),
    failed_count    integer     NOT NULL DEFAULT 0 CHECK (failed_count    >= 0),

    trace_id        text        NOT NULL,
    tenant_id       text        NOT NULL,
    env             text        NOT NULL,
    requested_by    text,

    created_at      timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    finished_at     timestamptz,

    CONSTRAINT wf_batch_status_ck CHECK (
        status IN ('PENDING','SUBMITTED','RUNNING','SUCCEEDED','FAILED','CANCELLED')
    ),
    CONSTRAINT wf_batch_terminal_ck CHECK (
        (status IN ('SUCCEEDED','FAILED','CANCELLED') AND finished_at IS NOT NULL)
     OR (status IN ('PENDING','SUBMITTED','RUNNING')  AND finished_at IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS wf_batch_instance_uq
    ON orchestration.wf_batch (tenant_id, batch_name, batch_instance);
CREATE INDEX IF NOT EXISTS wf_batch_recent_ix
    ON orchestration.wf_batch (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS wf_batch_status_ix
    ON orchestration.wf_batch (status, created_at DESC);


CREATE TABLE IF NOT EXISTS orchestration.wf_exec_log (
    exec_id         uuid        PRIMARY KEY,

    -- Optional parent. ON DELETE RESTRICT: a batch with detail rows must not vanish and
    -- orphan its own audit trail.
    wf_batch_id     uuid        REFERENCES orchestration.wf_batch (wf_batch_id)
                                ON DELETE RESTRICT,

    domain          text        NOT NULL,
    sub_domain      text        NOT NULL,
    workflow        text        NOT NULL,

    -- airflow | container_apps_job | azure_functions | azure_kafka_consumer
    -- | aws_step_functions | aws_lambda | aws_kafka_consumer
    tech_stack      text        NOT NULL,

    -- The engine's own identifier: Airflow dag_run_id, Step Functions execution ARN,
    -- Lambda request id. NULL until the engine accepts the submission, which is what
    -- makes a failed submit detectable instead of invisible.
    wf_ref_id       text,

    status          text        NOT NULL DEFAULT 'PENDING',
    input_data      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    output_data     jsonb,
    error           jsonb,

    -- Same trace_id as the query path, so a build and a query that used its artifacts are
    -- correlatable in one search.
    trace_id        text        NOT NULL,
    tenant_id       text        NOT NULL,
    env             text        NOT NULL,
    requested_by    text,
    idempotency_key text,

    created_at      timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    finished_at     timestamptz,

    CONSTRAINT wf_exec_log_status_ck CHECK (
        status IN ('PENDING','SUBMITTED','RUNNING','SUCCEEDED','FAILED','CANCELLED')
    ),
    -- Mirrors the WorkflowExecution validators, so the database and the contracts package
    -- cannot disagree about what a row means.
    CONSTRAINT wf_exec_log_terminal_ck CHECK (
        (status IN ('SUCCEEDED','FAILED','CANCELLED') AND finished_at IS NOT NULL)
     OR (status IN ('PENDING','SUBMITTED','RUNNING')  AND finished_at IS NULL)
    ),
    CONSTRAINT wf_exec_log_submitted_ck CHECK (
        status = 'PENDING' OR wf_ref_id IS NOT NULL
    )
);

-- A retried submit cannot log the same engine execution twice.
CREATE UNIQUE INDEX IF NOT EXISTS wf_exec_log_engine_uq
    ON orchestration.wf_exec_log (tech_stack, wf_ref_id)
    WHERE wf_ref_id IS NOT NULL;
-- A double-clicked Admin button collapses to one execution.
CREATE UNIQUE INDEX IF NOT EXISTS wf_exec_log_idem_uq
    ON orchestration.wf_exec_log (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Paging one batch's detail rows is the hottest Admin query at volume.
CREATE INDEX IF NOT EXISTS wf_exec_log_batch_ix
    ON orchestration.wf_exec_log (wf_batch_id, created_at DESC)
    WHERE wf_batch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS wf_exec_log_batch_failed_ix
    ON orchestration.wf_exec_log (wf_batch_id)
    WHERE status = 'FAILED';
CREATE INDEX IF NOT EXISTS wf_exec_log_domain_ix
    ON orchestration.wf_exec_log (domain, sub_domain, created_at DESC);
CREATE INDEX IF NOT EXISTS wf_exec_log_stack_status_ix
    ON orchestration.wf_exec_log (tech_stack, status);
CREATE INDEX IF NOT EXISTS wf_exec_log_trace_ix
    ON orchestration.wf_exec_log (trace_id);
CREATE INDEX IF NOT EXISTS wf_exec_log_input_gin
    ON orchestration.wf_exec_log USING gin (input_data jsonb_path_ops);

-- Scale lever, deliberately not applied yet: wf_exec_log is the table that grows without
-- bound and RANGE partitioning on created_at is the answer. It is not done here because a
-- unique index on a partitioned table must contain the partition key, which would turn
-- wf_exec_log_engine_uq into (tech_stack, wf_ref_id, created_at) and stop it from
-- preventing duplicate submits. Partition when volume demands it, and replace that
-- guarantee with an application-level check at the same time -- not before.

-- Truth, recounted from the detail rows.
CREATE OR REPLACE VIEW orchestration.wf_batch_rollup AS
SELECT b.wf_batch_id,
       b.batch_name,
       b.batch_instance,
       b.status                                                        AS batch_status,
       count(e.exec_id)                                                AS actual_total,
       count(*) FILTER (WHERE e.status = 'SUCCEEDED')                   AS actual_succeeded,
       count(*) FILTER (WHERE e.status = 'FAILED')                      AS actual_failed,
       count(*) FILTER (WHERE e.status IN ('PENDING','SUBMITTED','RUNNING')) AS actual_open,
       min(e.started_at)                                               AS first_started_at,
       max(e.finished_at)                                              AS last_finished_at
FROM orchestration.wf_batch b
LEFT JOIN orchestration.wf_exec_log e USING (wf_batch_id)
GROUP BY b.wf_batch_id, b.batch_name, b.batch_instance, b.status;

-- Counter cache versus recount. A non-empty result is a bug in the orchestrator, not a
-- reporting quirk.
CREATE OR REPLACE VIEW orchestration.wf_batch_drift AS
SELECT b.wf_batch_id, b.batch_name, b.batch_instance,
       b.total_count, r.actual_total,
       b.succeeded_count, r.actual_succeeded,
       b.failed_count, r.actual_failed
FROM orchestration.wf_batch b
JOIN orchestration.wf_batch_rollup r USING (wf_batch_id)
WHERE b.total_count     <> r.actual_total
   OR b.succeeded_count <> r.actual_succeeded
   OR b.failed_count    <> r.actual_failed;

-- A batch that claims to be finished while detail rows are still open.
CREATE OR REPLACE VIEW orchestration.wf_batch_inconsistent AS
SELECT * FROM orchestration.wf_batch_rollup
WHERE batch_status IN ('SUCCEEDED','FAILED','CANCELLED') AND actual_open > 0;

-- Submitted but never acknowledged by any engine: the failure mode that would otherwise
-- be silent.
CREATE OR REPLACE VIEW orchestration.wf_exec_stuck AS
SELECT * FROM orchestration.wf_exec_log
WHERE status = 'PENDING' AND created_at < now() - interval '5 minutes';

-- The Airflow slice, under the name the owner first used. Accurate as a view.
CREATE OR REPLACE VIEW orchestration.airflow_exec_log AS
SELECT * FROM orchestration.wf_exec_log WHERE tech_stack = 'airflow';
