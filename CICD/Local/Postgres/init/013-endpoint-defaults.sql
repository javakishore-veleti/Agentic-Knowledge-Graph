-- Declared defaults for endpoint configuration (ADR-015).
--
-- A fresh checkout should work with nothing configured. A filesystem root under the
-- user's home is a sensible guess, and requiring a variable before anything runs is
-- friction for no safety.
--
-- Defaults live under "defaults" in connection_details, alongside "env":
--
--   {"env": {"root": "AKG_LOCAL_DATA_ROOT"},
--    "defaults": {"root": "~/runtime_data/AKG/Local/FileSystem"}}

-- A default is refused for anything secret-shaped. Substituting a default credential
-- would connect as the wrong identity, or a blank one, and do it quietly enough that the
-- mistake surfaces somewhere else entirely. A missing secret must stay missing.
CREATE OR REPLACE FUNCTION catalog.defaults_hold_no_secrets(d jsonb)
RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT NOT (coalesce(d -> 'defaults', '{}'::jsonb) ?| array[
        'password', 'pwd', 'secret', 'client_secret', 'api_key', 'apikey', 'token',
        'access_key', 'secret_access_key', 'sas_token', 'account_key', 'connection_string'
    ])
$$;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_defaults_no_secrets_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_defaults_no_secrets_ck
    CHECK (catalog.defaults_hold_no_secrets(connection_details));

-- The local filesystem now works out of the box.
UPDATE catalog.app_endpoint
   SET connection_details = connection_details
        || jsonb_build_object('defaults',
             jsonb_build_object('root', '~/runtime_data/AKG/Local/FileSystem')),
       description = 'Files on the machine running the code. Defaults to '
                     '~/runtime_data/AKG/Local/FileSystem when AKG_LOCAL_DATA_ROOT is unset.'
 WHERE code = 'local-fs';

-- Users add their own filesystem locations with whatever path they want. These are not
-- system endpoints: they are created, edited and deleted freely, and they declare their
-- root directly rather than through a variable, because a path chosen for one machine is
-- not a deployment-varying value.
COMMENT ON TABLE catalog.app_endpoint IS
    'One row per WAY of reaching a service. System rows ship with the product and cannot '
    'be deleted; user rows are free-form. For local_fs, set connection_details.root to '
    'any path, or leave it to inherit the default.';

-- A local filesystem endpoint must say where it points: either a literal root, a variable
-- that supplies one, or a default. Without any of the three it resolves to nothing and
-- fails at read time, far from here.
CREATE OR REPLACE FUNCTION catalog.local_fs_has_root(d jsonb, service text)
RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT service <> 'filesystem'
        OR (d ? 'root')
        OR (coalesce(d -> 'env', '{}'::jsonb) ? 'root')
        OR (coalesce(d -> 'defaults', '{}'::jsonb) ? 'root')
$$;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_local_fs_root_ck;
ALTER TABLE catalog.app_endpoint ADD CONSTRAINT app_endpoint_local_fs_root_ck
    CHECK (catalog.local_fs_has_root(connection_details, provider_service));

-- Two examples of user-defined filesystem endpoints, showing both styles.
INSERT INTO catalog.app_endpoint
    (app_endpoint_id, code, name, description, tech_stack, provider, provider_service,
     connection_type, connection_details, env, host, is_system, tenant_id)
VALUES
    ('00000000-0000-4000-8000-000000000031', 'local-fs-scratch',
     'Local scratch space', 'A second local path, defined by the user',
     'local_fs', 'local', 'filesystem', 'anonymous',
     '{"root": "~/runtime_data/AKG/Local/Scratch"}'::jsonb,
     'local', 'localhost', false, 'reference'),
    ('00000000-0000-4000-8000-000000000032', 'nas-corpus',
     'NAS corpus mount', 'An on-premises mount, path supplied per machine',
     'file_server', 'on_prem', 'filesystem', 'anonymous',
     '{"env": {"root": "AKG_NAS_CORPUS_ROOT"},
       "defaults": {"root": "/mnt/nas/corpus"}}'::jsonb,
     'local', 'files.internal', false, 'reference')
ON CONFLICT (app_endpoint_id) DO NOTHING;
