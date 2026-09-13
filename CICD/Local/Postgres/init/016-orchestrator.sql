-- The orchestrator's own schema.
--
-- Deliberately NOT catalog.wf_exec_log: that table belongs to data-catalog, and a table
-- written by two independently deployable services is a shared database by another name.
-- The orchestrator owns run identity and state; data-catalog keeps its own record of what
-- a run meant for a dataset, joined by run_id when anyone needs both.
CREATE SCHEMA IF NOT EXISTS orch;

CREATE TABLE IF NOT EXISTS orch.wf_run (
    run_id          uuid PRIMARY KEY,
    engine          text NOT NULL,
    -- What to run, in the engine's terms: a dag_id, a state machine ARN, a job name.
    workflow_ref    text NOT NULL,
    -- What the engine called this run. Null until the engine has accepted it.
    engine_run_id   text,
    -- The CALLER's idempotency key.
    run_key         text,
    state           text NOT NULL DEFAULT 'queued',
    engine_state    text,
    conf            jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Opaque to this service: it ties a run back to whatever asked for it.
    caller_ref      jsonb NOT NULL DEFAULT '{}'::jsonb,
    error           jsonb,
    trace_id        text,
    tenant_id       text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    started_at      timestamptz,
    finished_at     timestamptz,

    CONSTRAINT wf_run_state_ck CHECK (
        state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    -- A terminal run has an end; a live one does not. Without this a "succeeded" row with
    -- no finished_at reads as still running to anything sorting by completion.
    CONSTRAINT wf_run_terminal_ck CHECK (
        (state IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NOT NULL)
        OR (state IN ('queued', 'running') AND finished_at IS NULL)),
    -- A failure must say why. The alternative is a failed run nobody can explain.
    CONSTRAINT wf_run_failed_reason_ck CHECK (state <> 'failed' OR error IS NOT NULL)
);

-- The idempotency guarantee, enforced by the database rather than by a read-then-write
-- in the service: two concurrent requests carrying the same key cannot both start a run.
CREATE UNIQUE INDEX IF NOT EXISTS wf_run_key_uq
    ON orch.wf_run (tenant_id, engine, workflow_ref, run_key)
    WHERE run_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS wf_run_listing_ix
    ON orch.wf_run (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS wf_run_live_ix
    ON orch.wf_run (tenant_id, state, created_at DESC)
    WHERE state IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS wf_run_workflow_ix
    ON orch.wf_run (tenant_id, engine, workflow_ref, created_at DESC);

COMMENT ON TABLE orch.wf_run IS
    'One workflow run, whichever engine ran it. State is the normalised vocabulary; '
    'engine_state keeps what the engine itself said, for operators reading a trace.';
