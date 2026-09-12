-- Where a dataset comes from, and where it is stored (ADR-012).
CREATE TABLE IF NOT EXISTS catalog.dataset_endpoint (
    dataset_endpoint_id uuid        PRIMARY KEY,
    dataset_id          uuid        NOT NULL REFERENCES catalog.dataset (dataset_id)
                                    ON DELETE CASCADE,

    -- source = where it came from; the rest are places we put it.
    role                text        NOT NULL,

    -- The registered system this lives in. Null only for an external source: nobody
    -- registers Kaggle or a publisher's FTP as an app endpoint.
    app_endpoint_id     uuid        REFERENCES catalog.app_endpoint (app_endpoint_id)
                                    ON DELETE RESTRICT,

    location_kind       text        NOT NULL,
    -- The full locator: s3://bucket/prefix, abfss://container@acct/path,
    -- gs://bucket/prefix, postgres://host/db (no credentials -- see the CHECK below),
    -- file:///mnt/data/raw, https://..., kaggle://owner/dataset.
    uri                 text        NOT NULL,

    -- Non-secret detail: bucket, prefix, schema, table, container, delimiter, ...
    options             jsonb       NOT NULL DEFAULT '{}'::jsonb,
    format              text,

    bytes               bigint      NOT NULL DEFAULT 0 CHECK (bytes        >= 0),
    object_count        bigint      NOT NULL DEFAULT 0 CHECK (object_count >= 0),

    state               text        NOT NULL DEFAULT 'declared',
    is_primary          boolean     NOT NULL DEFAULT false,
    checksum            text,
    last_synced_at      timestamptz,

    tenant_id           text        NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT dse_role_ck CHECK (role IN ('source','landing','curated','export')),
    CONSTRAINT dse_state_ck CHECK (state IN ('declared','syncing','available','stale','failed')),
    CONSTRAINT dse_kind_ck CHECK (location_kind IN (
        's3','azure_blob','gcs','postgres','mysql','file_server','local_fs',
        'http_url','ftp','kaggle','hdfs','opensearch','kafka'
    )),

    -- A destination must name a registered system. You cannot store into something with
    -- no host, no credential reference and no owner.
    CONSTRAINT dse_destination_needs_endpoint_ck CHECK (
        role = 'source' OR app_endpoint_id IS NOT NULL
    ),

    -- No credentials in the URI. `postgres://user:hunter2@host/db` would be a password in
    -- a column that list APIs return and portals render; the connection secret belongs to
    -- the app_endpoint's secret_ref. This rejects any userinfo before the host.
    CONSTRAINT dse_uri_has_no_credentials_ck CHECK (
        uri !~ '^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@]*:[^/@]*@'
    ),
    CONSTRAINT dse_uri_shape_ck CHECK (uri ~ '^[a-zA-Z][a-zA-Z0-9+.-]*://.+')
);

-- Exactly one primary per role. Without this, "the curated copy" becomes ambiguous the
-- moment a second appears and a build silently takes whichever sorted first.
CREATE UNIQUE INDEX IF NOT EXISTS dataset_endpoint_primary_uq
    ON catalog.dataset_endpoint (dataset_id, role) WHERE is_primary;

CREATE INDEX IF NOT EXISTS dataset_endpoint_dataset_ix
    ON catalog.dataset_endpoint (dataset_id, role);
CREATE INDEX IF NOT EXISTS dataset_endpoint_app_ix
    ON catalog.dataset_endpoint (app_endpoint_id) WHERE app_endpoint_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS dataset_endpoint_kind_ix
    ON catalog.dataset_endpoint (location_kind, state);

-- Which copy a MIO reads. Null means "the primary for its role", so rows written before
-- this migration keep working; a build that pinned a specific copy can now say which.
ALTER TABLE catalog.mio_dataset
    ADD COLUMN IF NOT EXISTS dataset_endpoint_id uuid
        REFERENCES catalog.dataset_endpoint (dataset_endpoint_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS mio_dataset_endpoint_ix
    ON catalog.mio_dataset (dataset_endpoint_id) WHERE dataset_endpoint_id IS NOT NULL;

-- One row per dataset with its locations resolved, for the list API.
CREATE OR REPLACE VIEW catalog.dataset_overview AS
SELECT d.dataset_id,
       d.domain_id,
       dom.code                                              AS domain_code,
       d.code,
       d.name,
       d.description,
       d.source_version,
       d.adapter,
       d.sub_domain,
       d.created_at,
       d.tenant_id,
       (SELECT count(*) FROM catalog.dataset_endpoint e
         WHERE e.dataset_id = d.dataset_id)                  AS location_count,
       (SELECT e.uri FROM catalog.dataset_endpoint e
         WHERE e.dataset_id = d.dataset_id AND e.role = 'source'
         ORDER BY e.is_primary DESC, e.created_at LIMIT 1)   AS source_uri,
       (SELECT e.location_kind FROM catalog.dataset_endpoint e
         WHERE e.dataset_id = d.dataset_id AND e.role = 'source'
         ORDER BY e.is_primary DESC, e.created_at LIMIT 1)   AS source_kind,
       coalesce((SELECT sum(e.bytes) FROM catalog.dataset_endpoint e
                  WHERE e.dataset_id = d.dataset_id AND e.role <> 'source'), 0)
                                                             AS stored_bytes,
       EXISTS (SELECT 1 FROM catalog.dataset_endpoint e
                WHERE e.dataset_id = d.dataset_id AND e.role = 'source')
                                                             AS has_source,
       EXISTS (SELECT 1 FROM catalog.dataset_endpoint e
                WHERE e.dataset_id = d.dataset_id AND e.role <> 'source'
                  AND e.state = 'available')                 AS has_available_copy
FROM catalog.dataset d
JOIN catalog.domain dom ON dom.domain_id = d.domain_id;

-- A dataset nobody can rebuild from: no source location recorded. Invisible until a
-- rebuild is attempted, which is the wrong moment to discover it.
CREATE OR REPLACE VIEW catalog.dataset_without_source AS
SELECT dataset_id, domain_code, code, source_version
FROM catalog.dataset_overview WHERE NOT has_source;

-- A MIO reading a copy that is not available. The build would fail at read time.
CREATE OR REPLACE VIEW catalog.mio_dataset_unavailable AS
SELECT md.mio_id, md.dataset_id, e.dataset_endpoint_id, e.uri, e.state
FROM catalog.mio_dataset md
JOIN catalog.dataset_endpoint e ON e.dataset_endpoint_id = md.dataset_endpoint_id
WHERE e.state <> 'available';
