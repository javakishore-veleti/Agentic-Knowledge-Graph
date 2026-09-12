-- How an endpoint authenticates, wherever this code happens to be running (ADR-015).
--
-- Credentials reach the platform four ways, and which one is right depends on where the
-- process runs, not on the endpoint itself:
--
--   env_vars              names declared in config_env; keys live in the environment
--   aws_profile           a named profile in ~/.aws/credentials on this machine
--   aws_role              ambient role: EC2 instance profile, ECS task role, EKS IRSA
--   azure_cli             the token `az login` left on this machine
--   azure_managed_identity  MSI / workload identity inside Azure
--   azure_client_secret   service principal; id and secret named in config_env
--   gcp_adc               application default credentials
--   anonymous             public source needing no credential at all
--
-- auth_ref holds the NON-SECRET selector for the mode: a profile name, a tenant id, a
-- client id. Never a secret -- those stay in the environment or in the credential store
-- the mode names.
ALTER TABLE catalog.app_endpoint
    ADD COLUMN IF NOT EXISTS auth_mode text NOT NULL DEFAULT 'env_vars',
    ADD COLUMN IF NOT EXISTS auth_ref  text;

ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_auth_mode_ck;
ALTER TABLE catalog.app_endpoint
    ADD CONSTRAINT app_endpoint_auth_mode_ck CHECK (auth_mode IN (
        'env_vars', 'aws_profile', 'aws_role', 'azure_cli', 'azure_managed_identity',
        'azure_client_secret', 'gcp_adc', 'anonymous'
    ));

-- A profile-based mode without the profile name is unusable, and the failure would appear
-- at connect time rather than at definition time.
ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_auth_ref_ck;
ALTER TABLE catalog.app_endpoint
    ADD CONSTRAINT app_endpoint_auth_ref_ck CHECK (
        auth_mode <> 'aws_profile' OR (auth_ref IS NOT NULL AND auth_ref <> '')
    );

-- auth_ref must never look like a secret. A profile name, tenant id or client id is short
-- and unremarkable; a pasted key is long and high-entropy. This is a blunt guard, but the
-- failure it prevents -- a secret sitting in a column that list APIs return -- is worse
-- than the occasional false positive on a very long profile name.
ALTER TABLE catalog.app_endpoint DROP CONSTRAINT IF EXISTS app_endpoint_auth_ref_not_secret_ck;
ALTER TABLE catalog.app_endpoint
    ADD CONSTRAINT app_endpoint_auth_ref_not_secret_ck CHECK (
        auth_ref IS NULL OR length(auth_ref) <= 128
    );

COMMENT ON COLUMN catalog.app_endpoint.auth_mode IS
    'How to obtain credentials where this code runs. See ADR-015.';
COMMENT ON COLUMN catalog.app_endpoint.auth_ref IS
    'Non-secret selector for the mode: AWS profile name, Azure tenant or client id. '
    'Never a secret.';

-- Endpoints whose mode needs configuration but declare none.
CREATE OR REPLACE VIEW catalog.app_endpoint_unconfigured AS
SELECT app_endpoint_id, code, tech_stack, env, auth_mode, auth_ref
FROM catalog.app_endpoint
WHERE is_active
  AND auth_mode IN ('env_vars', 'azure_client_secret')
  AND config_env = '{}'::jsonb
  AND tech_stack NOT IN ('http', 'ftp', 'local_fs');
