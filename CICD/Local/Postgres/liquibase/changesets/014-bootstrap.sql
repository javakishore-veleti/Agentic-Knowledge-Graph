--liquibase formatted sql

--changeset akg:014-bootstrap splitStatements:false endDelimiter:\n/
--comment bootstrap
--rollback empty

-- First-run data loading (ADR-017).
--
-- On a blank database every list in the portal is empty, and an administrator has no way
-- to tell "nothing has been loaded" from "something is broken". This records what has
-- been loaded, so the Administration screen can say which.
--
-- System endpoints are NOT part of this: they ship with the product in migration 010,
-- because they describe how the platform reaches storage rather than what data it holds.
-- What loads here is reference content: domains, datasets, workflow definitions.
CREATE TABLE IF NOT EXISTS catalog.initial_data_tracker (
    tracker_id uuid        PRIMARY KEY,
    entity           text        NOT NULL,
    status           text        NOT NULL DEFAULT 'PENDING',
    -- Inserted vs already present. Loading twice is allowed and must be visible as a
    -- no-op rather than looking like a fresh load.
    inserted_count   integer     NOT NULL DEFAULT 0 CHECK (inserted_count >= 0),
    skipped_count    integer     NOT NULL DEFAULT 0 CHECK (skipped_count  >= 0),
    wf_ref_id        text,
    error            jsonb,
    trace_id         text        NOT NULL,
    tenant_id        text        NOT NULL,
    env              text        NOT NULL,
    requested_by     text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    finished_at      timestamptz,

    CONSTRAINT initial_data_entity_ck CHECK (entity IN ('domains', 'datasets', 'endpoints',
                                                     'workflows', 'purposes')),
    CONSTRAINT initial_data_status_ck CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')),
    CONSTRAINT initial_data_terminal_ck CHECK (
        (status IN ('SUCCEEDED','FAILED') AND finished_at IS NOT NULL)
     OR (status IN ('PENDING','RUNNING')  AND finished_at IS NULL)
    ),
    CONSTRAINT initial_data_failed_reason_ck CHECK (status <> 'FAILED' OR error IS NOT NULL)
);

-- One load at a time per entity. Two administrators pressing the same button together
-- would otherwise run two DAGs inserting the same rows.
CREATE UNIQUE INDEX IF NOT EXISTS initial_data_one_running_uq
    ON catalog.initial_data_tracker (tenant_id, entity)
    WHERE status IN ('PENDING', 'RUNNING');

CREATE INDEX IF NOT EXISTS initial_data_recent_ix
    ON catalog.initial_data_tracker (tenant_id, entity, created_at DESC);

-- What the Administration screen reads: how much exists now, and what was last loaded.
CREATE OR REPLACE VIEW catalog.initial_data_status AS
WITH counts AS (
    SELECT 'domains'   AS entity, count(*) AS row_count FROM catalog.domain
    UNION ALL SELECT 'datasets',  count(*) FROM catalog.dataset
    UNION ALL SELECT 'endpoints', count(*) FROM catalog.app_endpoint WHERE NOT is_system
    UNION ALL SELECT 'workflows', count(*) FROM catalog.workflow
    UNION ALL SELECT 'purposes',  count(*) FROM catalog.purpose WHERE NOT is_system
),
latest AS (
    SELECT DISTINCT ON (entity)
           entity, status, inserted_count, skipped_count, created_at, finished_at, error
    FROM catalog.initial_data_tracker
    ORDER BY entity, created_at DESC
)
SELECT c.entity,
       c.row_count,
       l.status         AS last_status,
       l.inserted_count AS last_inserted,
       l.skipped_count  AS last_skipped,
       l.created_at     AS last_run_at,
       l.finished_at    AS last_finished_at,
       l.error          AS last_error,
       -- What must exist before this entity can load. Datasets carry a foreign key to
       -- domains, so loading them first fails at the constraint rather than at a check
       -- the administrator can read.
       CASE c.entity
           WHEN 'datasets'  THEN 'domains'
           WHEN 'workflows' THEN 'purposes'
           ELSE NULL
       END AS depends_on,
       -- The order an administrator should work through on a blank database. Stated here
       -- so the portal does not carry its own copy and drift from the dependencies above.
       CASE c.entity
           WHEN 'purposes'  THEN 1   -- vocabulary first: workflows reference it
           WHEN 'domains'   THEN 2   -- datasets carry a foreign key to it
           WHEN 'endpoints' THEN 3   -- independent, but dataset locations will want them
           WHEN 'datasets'  THEN 4
           WHEN 'workflows' THEN 5
           ELSE 99
       END AS load_order
FROM counts c
LEFT JOIN latest l ON l.entity = c.entity;

-- Claim a load, or refuse and say why. Same shape as the acquisition claim: the decision
-- and the transition are one statement, so two callers cannot both be told to proceed.
CREATE OR REPLACE FUNCTION catalog.claim_initial_data_load(
    p_tracker_id uuid, p_entity text, p_tenant text, p_env text, p_trace text,
    p_requested_by text DEFAULT NULL, p_force boolean DEFAULT false
) RETURNS TABLE (claimed boolean, reason text)
LANGUAGE plpgsql AS $$
DECLARE
    v_running integer;
    v_done    integer;
    v_missing text;
BEGIN
    SELECT count(*) INTO v_running FROM catalog.initial_data_tracker
     WHERE tenant_id = p_tenant AND entity = p_entity AND status IN ('PENDING','RUNNING');
    IF v_running > 0 THEN
        RETURN QUERY SELECT false, 'already_running'::text;
        RETURN;
    END IF;

    -- Already loaded successfully: do nothing, however many times the button is pressed.
    -- This is the tracker's main job. Re-running would be harmless on its own, since every
    -- insert is ON CONFLICT DO NOTHING, but it would spawn a DAG, write a run row, and
    -- make the screen report a fresh load that changed nothing -- which reads as progress.
    SELECT count(*) INTO v_done FROM catalog.initial_data_tracker
     WHERE tenant_id = p_tenant AND entity = p_entity AND status = 'SUCCEEDED';
    IF v_done > 0 AND NOT p_force THEN
        RETURN QUERY SELECT false, 'already_loaded'::text;
        RETURN;
    END IF;

    -- Refuse a load whose prerequisite is empty, with a message naming it rather than a
    -- foreign key violation from inside a DAG.
    SELECT depends_on INTO v_missing FROM catalog.initial_data_status WHERE entity = p_entity;
    IF v_missing IS NOT NULL
       AND (SELECT row_count FROM catalog.initial_data_status WHERE entity = v_missing) = 0 THEN
        RETURN QUERY SELECT false, ('requires_' || v_missing)::text;
        RETURN;
    END IF;

    INSERT INTO catalog.initial_data_tracker
        (tracker_id, entity, status, trace_id, tenant_id, env, requested_by)
    VALUES (p_tracker_id, p_entity, 'PENDING', p_trace, p_tenant, p_env, p_requested_by);

    RETURN QUERY SELECT true, 'claimed'::text;
END;
$$;

CREATE OR REPLACE FUNCTION catalog.complete_initial_data_load(
    p_tracker_id uuid, p_status text, p_inserted integer DEFAULT 0,
    p_skipped integer DEFAULT 0, p_error jsonb DEFAULT NULL, p_wf_ref text DEFAULT NULL
) RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE v_rows integer;
BEGIN
    UPDATE catalog.initial_data_tracker
       SET status         = p_status,
           inserted_count = coalesce(p_inserted, 0),
           skipped_count  = coalesce(p_skipped, 0),
           error          = CASE WHEN p_status = 'FAILED'
                                 THEN coalesce(p_error, '{"detail":"no reason reported"}'::jsonb)
                                 ELSE NULL END,
           wf_ref_id      = coalesce(p_wf_ref, wf_ref_id),
           finished_at    = now()
     WHERE tracker_id = p_tracker_id;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RETURN v_rows = 1;
END;
$$;

-- A load claimed and never reported. Without this the unique index blocks every future
-- load of that entity, permanently.
CREATE OR REPLACE VIEW catalog.initial_data_stuck AS
SELECT tracker_id, entity, created_at
FROM catalog.initial_data_tracker
WHERE status IN ('PENDING','RUNNING') AND created_at < now() - interval '30 minutes';
