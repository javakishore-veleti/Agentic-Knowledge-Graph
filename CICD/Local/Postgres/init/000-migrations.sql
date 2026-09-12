-- Applied-migration tracking (ADR-020).
--
-- Every migration runs exactly once. Re-applying the whole set on each start seemed
-- harmless while the schema was small, but it forces every migration to stay compatible
-- with every later one: migration 010 inserts rows that 011 later gave a NOT NULL column,
-- so re-running 010 after 011 fails. That is not a bug in either migration -- it is what
-- re-running history does.
CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE IF NOT EXISTS catalog.schema_migrations (
    filename    text        PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now(),
    checksum    text
);

COMMENT ON TABLE catalog.schema_migrations IS
    'One row per applied migration file. stack-up.sh skips anything listed here.';
