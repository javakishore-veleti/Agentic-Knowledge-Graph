-- The Administration count must include system rows.
--
-- This view excluded them because the eleven system endpoints and thirteen system
-- purposes arrived in migrations 010 and 012, so the Load button only ever inserted the
-- handful of extras and counting the system rows would have shown content nobody loaded.
-- Migrations are schema-only now and the button inserts both sets, so the exclusion
-- reports "3 purposes" immediately after a load that wrote 16.
--
-- DROP first: CREATE OR REPLACE cannot change a view's column list, and this one has
-- been redefined before.
DROP VIEW IF EXISTS catalog.initial_data_status;
CREATE VIEW catalog.initial_data_status AS
WITH counts AS (
         SELECT 'domains'::text AS entity,
            count(*) AS row_count
           FROM catalog.domain
        UNION ALL
         SELECT 'datasets'::text,
            count(*) AS count
           FROM catalog.dataset
        UNION ALL
         SELECT 'endpoints'::text,
            count(*) AS count
           FROM catalog.app_endpoint
        UNION ALL
         SELECT 'workflows'::text,
            count(*) AS count
           FROM catalog.workflow
        UNION ALL
         SELECT 'purposes'::text,
            count(*) AS count
           FROM catalog.purpose
        ), latest AS (
         SELECT DISTINCT ON (initial_data_tracker.entity) initial_data_tracker.entity,
            initial_data_tracker.status,
            initial_data_tracker.inserted_count,
            initial_data_tracker.skipped_count,
            initial_data_tracker.created_at,
            initial_data_tracker.finished_at,
            initial_data_tracker.error
           FROM catalog.initial_data_tracker
          ORDER BY initial_data_tracker.entity, initial_data_tracker.created_at DESC
        )
 SELECT c.entity,
    c.row_count,
    l.status AS last_status,
    l.inserted_count AS last_inserted,
    l.skipped_count AS last_skipped,
    l.created_at AS last_run_at,
    l.finished_at AS last_finished_at,
    l.error AS last_error,
        CASE c.entity
            WHEN 'datasets'::text THEN 'domains'::text
            WHEN 'workflows'::text THEN 'purposes'::text
            ELSE NULL::text
        END AS depends_on,
        CASE c.entity
            WHEN 'purposes'::text THEN 1
            WHEN 'domains'::text THEN 2
            WHEN 'endpoints'::text THEN 3
            WHEN 'datasets'::text THEN 4
            WHEN 'workflows'::text THEN 5
            ELSE 99
        END AS load_order
   FROM counts c
     LEFT JOIN latest l ON l.entity = c.entity;
