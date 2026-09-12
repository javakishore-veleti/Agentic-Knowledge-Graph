-- Master list of workflows, and the MIO association richer than 002's link table.
--
-- 003 gave mio_workflow (mio_id, workflow, purpose) where `workflow` was free text. A
-- master list makes a workflow a first-class thing with parameters, so the Admin portal
-- can render a trigger form instead of hard-coding one per workflow.
CREATE TABLE IF NOT EXISTS catalog.workflow (
    workflow_id   uuid        PRIMARY KEY,
    code          text        NOT NULL,
    name          text        NOT NULL,
    description   text        NOT NULL DEFAULT '',
    domain        text        NOT NULL,
    sub_domain    text        NOT NULL,

    -- Resolved from configuration, shown read-only: the portal never chooses an engine
    -- (ADR-008).
    default_tech_stack text   NOT NULL DEFAULT 'airflow',
    purpose       text        NOT NULL DEFAULT 'build',

    -- [{name,label,kind,required,default,options,help}, ...]
    params_json   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    is_active     boolean     NOT NULL DEFAULT true,
    tenant_id     text        NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT workflow_code_ck    CHECK (code ~ '^[a-z0-9][a-z0-9_.-]{0,126}$'),
    CONSTRAINT workflow_purpose_ck CHECK (purpose IN ('build','refresh','validate','retract','calibrate')),
    CONSTRAINT workflow_params_is_list_ck CHECK (jsonb_typeof(params_json) = 'array')
);
CREATE UNIQUE INDEX IF NOT EXISTS workflow_code_uq ON catalog.workflow (tenant_id, code);
CREATE INDEX IF NOT EXISTS workflow_domain_ix ON catalog.workflow (domain, sub_domain) WHERE is_active;

-- Re-point the association at the master list. The old text column stays as a fallback
-- for rows written before this migration, so nothing is lost.
ALTER TABLE catalog.mio_workflow
    ADD COLUMN IF NOT EXISTS workflow_id uuid REFERENCES catalog.workflow (workflow_id)
        ON DELETE RESTRICT;
ALTER TABLE catalog.mio_workflow
    ADD COLUMN IF NOT EXISTS enabled boolean NOT NULL DEFAULT true;
ALTER TABLE catalog.mio_workflow
    ADD COLUMN IF NOT EXISTS param_overrides_json jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS mio_workflow_by_workflow_ix
    ON catalog.mio_workflow (workflow_id) WHERE workflow_id IS NOT NULL;

-- Workflows attached to a MIO, joined to the master so the portal gets the parameter
-- definitions in the same read.
CREATE OR REPLACE VIEW catalog.mio_workflow_detail AS
SELECT mw.mio_id,
       mw.workflow          AS workflow_code,
       mw.purpose,
       mw.enabled,
       mw.param_overrides_json,
       w.workflow_id,
       w.name               AS workflow_name,
       w.description,
       w.default_tech_stack,
       w.params_json,
       w.is_active          AS workflow_active
FROM catalog.mio_workflow mw
LEFT JOIN catalog.workflow w
       ON w.workflow_id = mw.workflow_id
       OR (mw.workflow_id IS NULL AND w.code = mw.workflow);

-- A MIO association pointing at a workflow that no longer exists in the master list, or
-- at a deactivated one. Should be empty; a non-empty result means the Admin portal would
-- render a trigger button that cannot work.
CREATE OR REPLACE VIEW catalog.mio_workflow_orphans AS
SELECT mio_id, workflow_code, workflow_id, workflow_active
FROM catalog.mio_workflow_detail
WHERE workflow_id IS NULL OR workflow_active IS NOT TRUE;
