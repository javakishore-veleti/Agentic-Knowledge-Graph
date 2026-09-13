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

-- Schema only. Rows arrive through Administration -> Initial Data, so a fresh
-- database is genuinely empty and an administrator can see what loading did.
-- Keeping INSERTs here also broke migration ordering: this file inserted rows that
-- a later migration gave a NOT NULL column, so it could not be applied after it.


-- Query parameters beyond sslmode belong in options, which already refuses credential
-- keys. Documented here because "additional query params" is where a password usually
-- gets smuggled into a connection string.
COMMENT ON COLUMN catalog.app_endpoint.options IS
    'Non-secret connection options: sslmode, application_name, connect_timeout, target '
    'container, index name. A CHECK rejects credential-shaped keys.';
