--liquibase formatted sql

--changeset akg:011-endpoint-provider-model splitStatements:false endDelimiter:\n/
--comment endpoint provider model
--rollback empty

-- Endpoints restructured: provider, service, connection type, connection details.
--
-- The previous shape conflated things. `tech_stack = 's3'` did not say AWS;
-- `tech_stack = 'postgres'` did not distinguish a local container from RDS from Azure
-- Flexible Server. And connection facts were spread across host, port, database,
-- username, options and config_env, so "what does this endpoint need" had no single
-- answer.
--
--   provider          who runs it            aws | azure | gcp | local | on_prem | other
--   provider_service  what service           s3, blob_storage, rds_postgres, kinesis, ...
--   connection_type   how you connect        basic_auth | token | client_credentials |
--                                            command | env_vars | profile | anonymous
--   connection_details  JSON whose shape follows connection_type
ALTER TABLE catalog.app_endpoint
    ADD COLUMN IF NOT EXISTS provider           text,
    ADD COLUMN IF NOT EXISTS provider_service   text,
    ADD COLUMN IF NOT EXISTS connection_type    text,
    ADD COLUMN IF NOT EXISTS connection_details jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Carry the existing rows forward rather than asking anyone to retype them.
UPDATE catalog.app_endpoint SET
    provider = COALESCE(provider, CASE
        WHEN tech_stack IN ('s3') OR code LIKE 'aws-%' OR env LIKE 'aws-%' THEN 'aws'
        WHEN tech_stack IN ('azure_blob') OR code LIKE 'azure-%' OR env LIKE 'azure-%' THEN 'azure'
        WHEN tech_stack IN ('gcs') THEN 'gcp'
        WHEN tech_stack IN ('local_fs') OR env = 'local' THEN 'local'
        ELSE 'other' END),
    provider_service = COALESCE(provider_service, CASE
        WHEN tech_stack = 's3'          THEN 's3'
        WHEN tech_stack = 'azure_blob'  THEN 'blob_storage'
        WHEN tech_stack = 'gcs'         THEN 'cloud_storage'
        WHEN tech_stack = 'local_fs'    THEN 'filesystem'
        WHEN tech_stack = 'postgres' AND env LIKE 'aws-%'   THEN 'rds_postgres'
        WHEN tech_stack = 'postgres' AND env LIKE 'azure-%' THEN 'postgres_flexible_server'
        WHEN tech_stack = 'postgres'    THEN 'postgres'
        ELSE tech_stack END),
    connection_type = COALESCE(connection_type, CASE auth_mode
        WHEN 'aws_profile'            THEN 'profile'
        WHEN 'aws_role'               THEN 'ambient'
        WHEN 'azure_cli'              THEN 'command'
        WHEN 'azure_managed_identity' THEN 'ambient'
        WHEN 'azure_client_secret'    THEN 'client_credentials'
        WHEN 'gcp_adc'                THEN 'ambient'
        WHEN 'anonymous'              THEN 'anonymous'
        ELSE 'env_vars' END),
    -- Plain facts at the top level; variable NAMES nested under "env". Keeping them
    -- apart is what lets a constraint tell a password from the name of the variable that
    -- supplies one -- merging them flat made `"password": "AKG_PG_PASSWORD"` look
    -- identical to `"password": "hunter2"` to any rule that only reads keys.
    connection_details = CASE WHEN connection_details = '{}'::jsonb THEN
        jsonb_strip_nulls(
            COALESCE(options, '{}'::jsonb)
            || jsonb_build_object(
                 'host', host, 'port', port, 'database', database,
                 'username', username, 'profile', auth_ref)
        ) || jsonb_build_object('env', COALESCE(config_env, '{}'::jsonb))
          -- A command-based endpoint must name WHICH helper. az_cli_token is the one the
          -- old azure_cli mode meant; without this the allowlist rejects the row, which
          -- is the constraint doing its job rather than a migration bug.
          || CASE WHEN auth_mode = 'azure_cli'
                  THEN jsonb_build_object('command', 'az_cli_token')
                  ELSE '{}'::jsonb END
    ELSE connection_details END
WHERE provider IS NULL OR connection_type IS NULL;

ALTER TABLE catalog.app_endpoint ALTER COLUMN provider         SET NOT NULL;
ALTER TABLE catalog.app_endpoint ALTER COLUMN provider_service SET NOT NULL;
ALTER TABLE catalog.app_endpoint ALTER COLUMN connection_type  SET NOT NULL;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_provider_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_provider_ck
    CHECK (provider IN ('aws', 'azure', 'gcp', 'local', 'on_prem', 'other'));

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_conn_type_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_conn_type_ck
    CHECK (connection_type IN (
        'basic_auth',          -- username plus a password named in the details
        'token',               -- a static token named in the details
        'client_credentials',  -- tenant/client id, secret named in the details
        'command',             -- a credential helper from the allowlist below
        'env_vars',            -- everything comes from named variables
        'profile',             -- a named profile in a local credentials file
        'ambient',             -- attached role, managed identity, ADC: nothing to declare
        'anonymous'            -- public
    ));

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_conn_details_obj_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_conn_details_obj_ck
    CHECK (jsonb_typeof(connection_details) = 'object');

-- connection_details holds non-secret facts at the top level and variable NAMES under
-- "env". The distinction matters: `{"password": "hunter2"}` is a leak, while
-- `{"env": {"password": "AKG_PG_PASSWORD"}}` is a pointer to one. A rule that only looked
-- at key names could not tell them apart, which is why they live at different depths.
CREATE OR REPLACE FUNCTION catalog.connection_details_clean(d jsonb)
RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT
        -- No credential-shaped key at the top level, where values are literal.
        NOT ((coalesce(d, '{}'::jsonb) - 'env') ?| array[
            'password', 'pwd', 'secret', 'client_secret', 'api_key', 'apikey', 'token',
            'access_key', 'secret_access_key', 'sas_token', 'account_key',
            'connection_string'
        ])
        -- And everything under "env" must be a variable NAME, never a value.
        AND coalesce((
            SELECT bool_and(v ~ '^AKG_[A-Z0-9_]{2,62}$')
            FROM jsonb_each_text(coalesce(d -> 'env', '{}'::jsonb)) AS kv(k, v)
        ), true)
$$;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_conn_details_no_secrets_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_conn_details_no_secrets_ck
    CHECK (catalog.connection_details_clean(connection_details));

-- `command` executes something on the host that runs the code. Free text here would be
-- remote code execution for anyone who can edit an endpoint, so only known credential
-- helpers are allowed, named by key rather than written as a command line.
CREATE OR REPLACE FUNCTION catalog.command_is_allowed(d jsonb, ctype text)
RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ctype <> 'command'
        OR coalesce(d ->> 'command', '') IN (
            'az_cli_token',        -- az account get-access-token
            'aws_sso_login',       -- aws sso login / sts get-caller-identity
            'gcloud_adc_token',    -- gcloud auth application-default print-access-token
            'kubectl_token'        -- kubectl create token
        )
$$;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_command_allowlist_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_command_allowlist_ck
    CHECK (catalog.command_is_allowed(connection_details, connection_type));

-- basic_auth without a username is unusable, and fails at connect time rather than here.
ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_basic_auth_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_basic_auth_ck
    CHECK (connection_type <> 'basic_auth' OR connection_details ? 'username');

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_profile_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_profile_ck
    CHECK (connection_type <> 'profile' OR connection_details ? 'profile');

CREATE INDEX IF NOT EXISTS app_endpoint_provider_ix
    ON catalog.app_endpoint (provider, provider_service) WHERE is_active;

-- What the list API reads.
CREATE OR REPLACE VIEW catalog.app_endpoint_list AS
SELECT app_endpoint_id, code, name, description, provider, provider_service,
       connection_type, connection_details, env, is_active, is_system, tenant_id,
       created_at
FROM catalog.app_endpoint;

COMMENT ON COLUMN catalog.app_endpoint.connection_details IS
    'Shape follows connection_type. Holds names and non-secret facts only: variable '
    'names, a profile name, a host, a bucket. Never a secret.';
