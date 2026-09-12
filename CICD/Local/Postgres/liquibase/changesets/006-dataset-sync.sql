--liquibase formatted sql

--changeset akg:006-dataset-sync splitStatements:false endDelimiter:\n/
--comment dataset sync
--rollback empty

-- Acquisition state for a dataset endpoint (ADR-013).
--
-- Two axes, deliberately separate:
--   state          is the DATA there?      declared | syncing | available | stale | failed
--   sync_wf_status did the RUN finish?     NULL | RUNNING | COMPLETED | FAILED
--
-- Conflating them loses real cases: a workflow can complete having written nothing
-- (COMPLETED + not available), and a refresh can run over data that is still perfectly
-- readable (RUNNING + available).
ALTER TABLE catalog.dataset_endpoint
    ADD COLUMN IF NOT EXISTS sync_wf_status   text,
    ADD COLUMN IF NOT EXISTS sync_exec_id     uuid,
    ADD COLUMN IF NOT EXISTS sync_wf_ref_id   text,
    ADD COLUMN IF NOT EXISTS sync_started_at  timestamptz,
    ADD COLUMN IF NOT EXISTS sync_finished_at timestamptz,
    ADD COLUMN IF NOT EXISTS sync_error       jsonb,
    ADD COLUMN IF NOT EXISTS sync_attempts    integer NOT NULL DEFAULT 0;

ALTER TABLE catalog.dataset_endpoint
    DROP CONSTRAINT IF EXISTS dse_sync_status_ck;
ALTER TABLE catalog.dataset_endpoint
    ADD CONSTRAINT dse_sync_status_ck CHECK (
        sync_wf_status IS NULL
        OR sync_wf_status IN ('RUNNING','COMPLETED','FAILED','CANCELLED')
    );

ALTER TABLE catalog.dataset_endpoint
    DROP CONSTRAINT IF EXISTS dse_sync_finished_ck;
ALTER TABLE catalog.dataset_endpoint
    ADD CONSTRAINT dse_sync_finished_ck CHECK (
        sync_wf_status IS DISTINCT FROM 'RUNNING' OR sync_finished_at IS NULL
    );

ALTER TABLE catalog.dataset_endpoint
    DROP CONSTRAINT IF EXISTS dse_sync_failed_has_reason_ck;
ALTER TABLE catalog.dataset_endpoint
    ADD CONSTRAINT dse_sync_failed_has_reason_ck CHECK (
        sync_wf_status IS DISTINCT FROM 'FAILED' OR sync_error IS NOT NULL
    );

-- At most one acquisition in flight per endpoint. The claim below relies on this being
-- true even if two callers race past the application check.
CREATE UNIQUE INDEX IF NOT EXISTS dataset_endpoint_one_run_uq
    ON catalog.dataset_endpoint (dataset_endpoint_id)
    WHERE sync_wf_status = 'RUNNING';

CREATE INDEX IF NOT EXISTS dataset_endpoint_sync_ix
    ON catalog.dataset_endpoint (sync_wf_status, sync_started_at DESC)
    WHERE sync_wf_status IS NOT NULL;

-- Claim an endpoint for acquisition.
--
-- The whole point is that the decision and the transition are ONE statement. A caller
-- that reads "not available" and then updates has a window in which a second caller reads
-- the same thing, and both start a DAG against the same destination. Here exactly one
-- caller gets a row back; everyone else gets none and must not start anything.
--
-- `force` re-acquires data that is already available, for a deliberate refresh.
CREATE OR REPLACE FUNCTION catalog.claim_dataset_endpoint_sync(
    p_endpoint_id uuid,
    p_exec_id     uuid,
    p_tenant      text,
    p_force       boolean DEFAULT false
) RETURNS TABLE (claimed boolean, reason text)
LANGUAGE plpgsql AS $$
DECLARE
    v_rows integer;
BEGIN
    UPDATE catalog.dataset_endpoint
       SET sync_wf_status   = 'RUNNING',
           sync_exec_id     = p_exec_id,
           sync_started_at  = now(),
           sync_finished_at = NULL,
           sync_error       = NULL,
           sync_attempts    = sync_attempts + 1,
           state            = 'syncing',
           updated_at       = now()
     WHERE dataset_endpoint_id = p_endpoint_id
       AND tenant_id = p_tenant
       -- Never two runs at once against one destination.
       AND coalesce(sync_wf_status, '') <> 'RUNNING'
       -- Already-available data is not re-downloaded unless forced.
       AND (p_force OR state <> 'available');

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows = 1 THEN
        RETURN QUERY SELECT true, 'claimed'::text;
    ELSE
        RETURN QUERY
        SELECT false,
               CASE
                 WHEN NOT EXISTS (SELECT 1 FROM catalog.dataset_endpoint
                                   WHERE dataset_endpoint_id = p_endpoint_id
                                     AND tenant_id = p_tenant)
                      THEN 'not_found'
                 WHEN (SELECT sync_wf_status FROM catalog.dataset_endpoint
                        WHERE dataset_endpoint_id = p_endpoint_id) = 'RUNNING'
                      THEN 'already_running'
                 ELSE 'already_available'
               END::text;
    END IF;
END;
$$;

-- What the Airflow callback writes when a run ends.
CREATE OR REPLACE FUNCTION catalog.complete_dataset_endpoint_sync(
    p_endpoint_id uuid,
    p_tenant      text,
    p_status      text,
    p_bytes       bigint  DEFAULT NULL,
    p_objects     bigint  DEFAULT NULL,
    p_error       jsonb   DEFAULT NULL,
    p_wf_ref_id   text    DEFAULT NULL
) RETURNS boolean
LANGUAGE plpgsql AS $$
DECLARE
    v_rows integer;
BEGIN
    UPDATE catalog.dataset_endpoint
       SET sync_wf_status   = p_status,
           sync_finished_at = now(),
           sync_wf_ref_id   = coalesce(p_wf_ref_id, sync_wf_ref_id),
           sync_error       = CASE WHEN p_status = 'FAILED' THEN
                                   coalesce(p_error, '{"detail":"no reason reported"}'::jsonb)
                              ELSE NULL END,
           bytes            = coalesce(p_bytes, bytes),
           object_count     = coalesce(p_objects, object_count),
           last_synced_at   = CASE WHEN p_status = 'COMPLETED' THEN now()
                                   ELSE last_synced_at END,
           -- Data availability follows the RUN only when the run actually produced
           -- something. A completed run that moved zero bytes leaves the endpoint
           -- unavailable, which is the honest outcome.
           state            = CASE
                                WHEN p_status = 'COMPLETED'
                                     AND coalesce(p_bytes, bytes) > 0 THEN 'available'
                                WHEN p_status = 'COMPLETED' THEN 'failed'
                                WHEN p_status = 'FAILED'    THEN 'failed'
                                ELSE state
                              END,
           updated_at       = now()
     WHERE dataset_endpoint_id = p_endpoint_id
       AND tenant_id = p_tenant;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RETURN v_rows = 1;
END;
$$;

-- A run that claimed an endpoint and never reported back. Without this, a crashed DAG
-- leaves the endpoint RUNNING forever and no further acquisition can ever claim it.
CREATE OR REPLACE VIEW catalog.dataset_endpoint_stuck_sync AS
SELECT dataset_endpoint_id, dataset_id, uri, sync_exec_id, sync_started_at, sync_attempts
FROM catalog.dataset_endpoint
WHERE sync_wf_status = 'RUNNING'
  AND sync_started_at < now() - interval '6 hours';
