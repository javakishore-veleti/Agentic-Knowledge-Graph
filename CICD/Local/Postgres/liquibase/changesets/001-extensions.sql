--liquibase formatted sql

--changeset akg:001-extensions splitStatements:false endDelimiter:\n/
--comment extensions
--rollback empty

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- One schema per service. No shared tables across independently deployable services
-- (PRD A 3.2), enforced by granting each service its own role in a later migration.
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS ontology;
CREATE SCHEMA IF NOT EXISTS retrieval;
CREATE SCHEMA IF NOT EXISTS audit;
