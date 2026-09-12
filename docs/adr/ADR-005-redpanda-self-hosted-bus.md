# ADR-005: Self-hosted Redpanda provides the Kafka API in v1

**Status:** Accepted · 2026-09-12

## Context
Both PRDs mandate a single Kafka-protocol bus and forbid RabbitMQ. Azure's managed option is Event
Hubs' Kafka endpoint, which bills continuously whether or not traffic flows. Idle cost must be
near zero.

## Decision
Redpanda runs as a single container: locally in Compose, and on Azure Container Apps for v1. It
speaks the Kafka protocol, so producers and consumers use a plain Kafka client and no Azure SDK
reaches domain code.

## Consequences
- Single-node durability. Acceptable for v1; **not** acceptable for production traffic, and this
  ADR must be revisited before any production claim.
- Migrating to Event Hubs or MSK is a broker string and credential change, by construction.
- Topic names, partition keys, and the event envelope stay identical across environments, so
  PRD B §7's catalogue is unaffected.
