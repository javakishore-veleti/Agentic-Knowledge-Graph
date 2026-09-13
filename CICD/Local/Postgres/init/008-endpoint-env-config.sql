-- Endpoints resolve their connection details from environment variables (ADR-015).
--
-- config_env maps a logical key to the NAME of an environment variable, never a value:
--
--   {"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION",
--    "access_key_id": "AKG_AWS_ACCESS_KEY_ID", "secret_access_key": "AKG_AWS_SECRET_ACCESS_KEY"}
--
-- One endpoint row then works in every environment: local, azure-dev and aws-prod supply
-- different values for the same names. Nothing secret enters the catalog, so a list API
-- returning these rows leaks nothing.
ALTER TABLE catalog.app_endpoint
    ADD COLUMN IF NOT EXISTS config_env jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_config_env_is_object_ck;
ALTER TABLE catalog.app_endpoint
    ADD CONSTRAINT app_endpoint_config_env_is_object_ck
    CHECK (jsonb_typeof(config_env) = 'object');

-- Every value must be an environment variable NAME: uppercase, AKG_-prefixed. This is what
-- stops someone putting the secret itself in the map -- a real key is lowercase or mixed
-- and never matches the convention -- and it keeps every variable this platform reads
-- inside one namespace.
--
-- A CHECK cannot contain a subquery, so the iteration lives in an IMMUTABLE function.
CREATE OR REPLACE FUNCTION catalog.config_env_names_ok(cfg jsonb)
RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT coalesce(bool_and(v ~ '^AKG_[A-Z0-9_]{2,62}$'), true)
    FROM jsonb_each_text(coalesce(cfg, '{}'::jsonb)) AS kv(k, v)
$$;

COMMENT ON FUNCTION catalog.config_env_names_ok(jsonb) IS
    'True when every value in config_env is an AKG_-prefixed environment variable NAME '
    'rather than a value. Used by a CHECK, so it must stay IMMUTABLE.';

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_config_env_names_ck;
ALTER TABLE catalog.app_endpoint
    ADD CONSTRAINT app_endpoint_config_env_names_ck
    CHECK (catalog.config_env_names_ok(config_env));

-- Endpoints that declare no configuration at all. Fine for a plain HTTP source; a problem
-- for anything needing credentials, because it will fail at connect time rather than here.
-- 009 later changes this view's column list, and CREATE OR REPLACE cannot drop or
-- reorder columns. Dropping first makes this migration safe whatever shape the
-- view happens to be in -- which matters on a database that has been partially
-- migrated by an earlier attempt.
DROP VIEW IF EXISTS catalog.app_endpoint_unconfigured;
CREATE VIEW catalog.app_endpoint_unconfigured AS
SELECT app_endpoint_id, code, tech_stack, env
FROM catalog.app_endpoint
WHERE is_active AND config_env = '{}'::jsonb
  AND tech_stack NOT IN ('http', 'ftp', 'local_fs');

COMMENT ON COLUMN catalog.app_endpoint.config_env IS
    'Logical key -> environment variable NAME. Never a value. Resolved at runtime by '
    'whichever process needs the connection.';
