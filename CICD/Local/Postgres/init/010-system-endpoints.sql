-- Built-in endpoints that cannot be deleted (ADR-015).
--
-- These are the ways this platform can reach storage and databases. They ship with the
-- product rather than being created per install, because a dataset location referencing a
-- deleted endpoint is a build that cannot run, and the failure appears far from the delete.

ALTER TABLE catalog.app_endpoint
    ADD COLUMN IF NOT EXISTS is_system boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS username  text,
    ADD COLUMN IF NOT EXISTS description text NOT NULL DEFAULT '';

COMMENT ON COLUMN catalog.app_endpoint.username IS
    'Login name. Non-secret by definition; the password is never stored here — it comes '
    'from the environment variable named in config_env.';

-- Deletion protection in the database, not only in a service. The catalog is written by
-- migrations, by psql and eventually by more than one service; a rule enforced in one
-- caller is a rule that holds until the second caller arrives.
CREATE OR REPLACE FUNCTION catalog.protect_system_endpoints()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.is_system THEN
            RAISE EXCEPTION
                'app endpoint % is a system endpoint and cannot be deleted; '
                'deactivate it instead (is_active = false)', OLD.code
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;

    -- Identity is what dataset locations point at. Renaming it out from under them is a
    -- delete wearing a different hat.
    IF OLD.is_system AND (NEW.code <> OLD.code OR NEW.tech_stack <> OLD.tech_stack) THEN
        RAISE EXCEPTION
            'code and tech_stack of system endpoint % are immutable', OLD.code
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- is_system itself cannot be cleared, or protection would be one UPDATE away.
    IF OLD.is_system AND NOT NEW.is_system THEN
        RAISE EXCEPTION 'is_system cannot be cleared on %', OLD.code
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS app_endpoint_protect_system ON catalog.app_endpoint;
CREATE TRIGGER app_endpoint_protect_system
    BEFORE UPDATE OR DELETE ON catalog.app_endpoint
    FOR EACH ROW EXECUTE FUNCTION catalog.protect_system_endpoints();


-- ---------------------------------------------------------------- the system set
--
-- One row per WAY of reaching a technology, because the way is what differs: the same S3
-- bucket is reached by a named profile on a laptop, by an attached role in EKS, and by
-- keys in CI. Which one applies is a deployment fact, not a dataset fact.

INSERT INTO catalog.app_endpoint
    (app_endpoint_id, code, name, description, tech_stack, env, host, port, database,
     username, options, config_env, auth_mode, auth_ref, is_system, tenant_id)
VALUES
    -- local filesystem
    ('00000000-0000-4000-8000-000000000001', 'local-fs',
     'Local filesystem', 'Files on the machine running the code',
     'local_fs', 'local', 'localhost', NULL, NULL, NULL,
     '{}'::jsonb, '{"root": "AKG_LOCAL_DATA_ROOT"}'::jsonb,
     'anonymous', NULL, true, 'reference'),

    -- S3, three ways
    ('00000000-0000-4000-8000-000000000002', 'aws-s3-profile',
     'AWS S3 (named profile)', 'Uses a profile from ~/.aws/credentials on this machine',
     's3', 'local', 's3.amazonaws.com', NULL, NULL, NULL,
     '{}'::jsonb, '{"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION"}'::jsonb,
     'aws_profile', 'default', true, 'reference'),

    ('00000000-0000-4000-8000-000000000003', 'aws-s3-keys',
     'AWS S3 (access keys)', 'Access key and secret supplied by the environment',
     's3', 'local', 's3.amazonaws.com', NULL, NULL, NULL,
     '{}'::jsonb,
     '{"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION",
       "access_key_id": "AKG_AWS_ACCESS_KEY_ID",
       "secret_access_key": "AKG_AWS_SECRET_ACCESS_KEY"}'::jsonb,
     'env_vars', NULL, true, 'reference'),

    ('00000000-0000-4000-8000-000000000004', 'aws-s3-role',
     'AWS S3 (attached role)', 'Instance profile, ECS task role or EKS IRSA',
     's3', 'aws-dev', 's3.amazonaws.com', NULL, NULL, NULL,
     '{}'::jsonb, '{"bucket": "AKG_AWS_S3_BUCKET", "region": "AKG_AWS_REGION"}'::jsonb,
     'aws_role', NULL, true, 'reference'),

    -- Azure Blob, three ways
    ('00000000-0000-4000-8000-000000000005', 'azure-blob-cli',
     'Azure Blob (az login)', 'Uses the token az login left on this machine',
     'azure_blob', 'local', 'blob.core.windows.net', NULL, NULL, NULL,
     '{}'::jsonb,
     '{"account": "AKG_AZURE_STORAGE_ACCOUNT", "container": "AKG_AZURE_STORAGE_CONTAINER"}'::jsonb,
     'azure_cli', NULL, true, 'reference'),

    ('00000000-0000-4000-8000-000000000006', 'azure-blob-sp',
     'Azure Blob (service principal)', 'Client id and secret supplied by the environment',
     'azure_blob', 'azure-dev', 'blob.core.windows.net', NULL, NULL, NULL,
     '{}'::jsonb,
     '{"account": "AKG_AZURE_STORAGE_ACCOUNT", "container": "AKG_AZURE_STORAGE_CONTAINER",
       "tenant_id": "AKG_AZURE_TENANT_ID", "client_id": "AKG_AZURE_CLIENT_ID",
       "client_secret": "AKG_AZURE_CLIENT_SECRET"}'::jsonb,
     'azure_client_secret', NULL, true, 'reference'),

    ('00000000-0000-4000-8000-000000000007', 'azure-blob-msi',
     'Azure Blob (managed identity)', 'Workload identity inside Azure; no secret at all',
     'azure_blob', 'azure-prod', 'blob.core.windows.net', NULL, NULL, NULL,
     '{}'::jsonb,
     '{"account": "AKG_AZURE_STORAGE_ACCOUNT", "container": "AKG_AZURE_STORAGE_CONTAINER"}'::jsonb,
     'azure_managed_identity', NULL, true, 'reference'),

    -- Postgres, three deployments. Host, port, database and username are connection
    -- facts; the password is only ever the NAME of an environment variable.
    ('00000000-0000-4000-8000-000000000011', 'pg-local',
     'PostgreSQL (local)', 'Postgres in the local Docker stack',
     'postgres', 'local', 'localhost', 5432, 'akg', 'akg',
     '{"sslmode": "disable"}'::jsonb,
     '{"host": "AKG_PG_HOST", "port": "AKG_PG_PORT", "database": "AKG_PG_DATABASE",
       "username": "AKG_PG_USERNAME", "password": "AKG_PG_PASSWORD"}'::jsonb,
     'env_vars', NULL, true, 'reference'),

    ('00000000-0000-4000-8000-000000000012', 'pg-aws-rds',
     'PostgreSQL (AWS RDS)', 'Amazon RDS for PostgreSQL',
     'postgres', 'aws-dev', 'CHANGE-ME.rds.amazonaws.com', 5432, 'akg', 'akg',
     '{"sslmode": "require"}'::jsonb,
     '{"host": "AKG_RDS_PG_HOST", "port": "AKG_RDS_PG_PORT",
       "database": "AKG_RDS_PG_DATABASE", "username": "AKG_RDS_PG_USERNAME",
       "password": "AKG_RDS_PG_PASSWORD"}'::jsonb,
     'env_vars', NULL, true, 'reference'),

    ('00000000-0000-4000-8000-000000000013', 'pg-azure',
     'PostgreSQL (Azure Flexible Server)', 'Azure Database for PostgreSQL',
     'postgres', 'azure-dev', 'CHANGE-ME.postgres.database.azure.com', 5432, 'akg', 'akg',
     '{"sslmode": "require"}'::jsonb,
     '{"host": "AKG_AZURE_PG_HOST", "port": "AKG_AZURE_PG_PORT",
       "database": "AKG_AZURE_PG_DATABASE", "username": "AKG_AZURE_PG_USERNAME",
       "password": "AKG_AZURE_PG_PASSWORD"}'::jsonb,
     'env_vars', NULL, true, 'reference'),

    -- the PubMed origin, so a dataset can point at it without inventing a row
    ('00000000-0000-4000-8000-000000000021', 'pubmed-ftp',
     'PubMed baseline (NCBI)', 'Public FTP origin of the annual baseline',
     'ftp', 'local', 'ftp.ncbi.nlm.nih.gov', NULL, NULL, NULL,
     '{"path": "/pubmed/baseline/"}'::jsonb,
     '{"base_url": "AKG_PUBMED_BASELINE_URL"}'::jsonb,
     'anonymous', NULL, true, 'reference')
ON CONFLICT (app_endpoint_id) DO NOTHING;

-- Query parameters beyond sslmode belong in options, which already refuses credential
-- keys. Documented here because "additional query params" is where a password usually
-- gets smuggled into a connection string.
COMMENT ON COLUMN catalog.app_endpoint.options IS
    'Non-secret connection options: sslmode, application_name, connect_timeout, target '
    'container, index name. A CHECK rejects credential-shaped keys.';
