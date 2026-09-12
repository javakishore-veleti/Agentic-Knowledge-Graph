-- Purposes: what a workflow or an execution is FOR (ADR-016).
--
-- Previously `purpose` was a CHECK on five hard-coded values, which meant adding
-- "indexing" required a migration and a redeploy. It is a growing vocabulary, so it
-- becomes a table: adding one is an INSERT, and the Admin portal reads the list rather
-- than shipping its own copy.
CREATE TABLE IF NOT EXISTS catalog.purpose (
    purpose_code text        PRIMARY KEY,
    name         text        NOT NULL,
    description  text        NOT NULL DEFAULT '',
    -- Ordering in pickers, so the common ones are not alphabetically buried.
    sort_order   integer     NOT NULL DEFAULT 100,
    is_active    boolean     NOT NULL DEFAULT true,
    is_system    boolean     NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT purpose_code_ck CHECK (purpose_code ~ '^[a-z0-9][a-z0-9_]{1,46}$')
);

INSERT INTO catalog.purpose (purpose_code, name, description, sort_order, is_system) VALUES
    ('initial_dataset_load', 'Initial dataset loading',
     'First acquisition of a dataset from its source into a destination', 10, true),
    ('incremental_load', 'Incremental load',
     'Deltas since the last acquisition rather than the whole corpus', 20, true),
    ('parsing', 'Parsing',
     'Turn acquired files into columnar tables', 30, true),
    ('ontology_linking', 'Ontology linking',
     'Resolve text to stable concept identifiers', 40, true),
    ('graph_build', 'Graph build',
     'Construct the CSR graph from publisher-supplied edges', 50, true),
    ('indexing', 'Indexing',
     'Embed and consolidate shards into one pinnable index', 60, true),
    ('validation', 'Validation',
     'Alignment asserts and independent recounts against the source', 70, true),
    ('calibration', 'Calibration',
     'Fit the abstention threshold on the held-out dev split', 80, true),
    ('evaluation', 'Evaluation',
     'Run the reference arms and the promotion gate', 90, true),
    ('retraction', 'Retraction handling',
     'Flag retracted documents so they drop out of citations', 100, true),
    ('export', 'Export',
     'Publish a curated copy for downstream consumers', 110, true),
    ('reconciliation', 'Reconciliation',
     'Recount caches against their source of truth', 120, true),
    ('maintenance', 'Maintenance',
     'Housekeeping: release stuck runs, vacuum, prune', 130, true)
ON CONFLICT (purpose_code) DO NOTHING;

-- System purposes are referenced by shipped workflows; deleting one would orphan them.
CREATE OR REPLACE FUNCTION catalog.protect_system_purposes()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.is_system THEN
        RAISE EXCEPTION 'purpose % ships with the product and cannot be deleted; '
                        'deactivate it instead', OLD.purpose_code
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS purpose_protect_system ON catalog.purpose;
CREATE TRIGGER purpose_protect_system BEFORE DELETE ON catalog.purpose
    FOR EACH ROW EXECUTE FUNCTION catalog.protect_system_purposes();

-- Point the workflow master at the table. The old CHECK is dropped: a fixed list was the
-- thing that made adding a purpose a migration.
ALTER TABLE catalog.workflow DROP CONSTRAINT IF EXISTS workflow_purpose_ck;

INSERT INTO catalog.purpose (purpose_code, name, sort_order, is_system)
SELECT DISTINCT purpose, initcap(replace(purpose, '_', ' ')), 500, false
FROM catalog.workflow
WHERE purpose IS NOT NULL
  AND purpose NOT IN (SELECT purpose_code FROM catalog.purpose)
  AND purpose ~ '^[a-z0-9][a-z0-9_]{1,46}$'
ON CONFLICT (purpose_code) DO NOTHING;

ALTER TABLE catalog.workflow DROP CONSTRAINT IF EXISTS workflow_purpose_fk;
ALTER TABLE catalog.workflow
    ADD CONSTRAINT workflow_purpose_fk FOREIGN KEY (purpose)
    REFERENCES catalog.purpose (purpose_code) ON DELETE RESTRICT;

ALTER TABLE catalog.mio_workflow DROP CONSTRAINT IF EXISTS mio_workflow_purpose_ck;

INSERT INTO catalog.purpose (purpose_code, name, sort_order, is_system)
SELECT DISTINCT purpose, initcap(replace(purpose, '_', ' ')), 500, false
FROM catalog.mio_workflow
WHERE purpose IS NOT NULL
  AND purpose NOT IN (SELECT purpose_code FROM catalog.purpose)
  AND purpose ~ '^[a-z0-9][a-z0-9_]{1,46}$'
ON CONFLICT (purpose_code) DO NOTHING;

ALTER TABLE catalog.mio_workflow DROP CONSTRAINT IF EXISTS mio_workflow_purpose_fk;
ALTER TABLE catalog.mio_workflow
    ADD CONSTRAINT mio_workflow_purpose_fk FOREIGN KEY (purpose)
    REFERENCES catalog.purpose (purpose_code) ON DELETE RESTRICT;

CREATE OR REPLACE VIEW catalog.purpose_list AS
SELECT purpose_code, name, description, sort_order, is_system,
       (SELECT count(*) FROM catalog.workflow w WHERE w.purpose = p.purpose_code) AS workflow_count
FROM catalog.purpose p
WHERE is_active
ORDER BY sort_order, name;
