# ADR-011: Redis is the cache; the in-memory mirror is a toggle, and it can go stale

**Status:** Accepted · 2026-09-12

## Decision
`IAppCacheService` is what the service layer uses; it knows nothing about Redis or memory.
Behind it sit two tiers: `RedisCacheStore`, shared by every replica, and
`MemoryLruCacheStore`, an in-process mirror enabled by `AKG_CACHE_MIRROR_IN_MEMORY`. Reads
try L1 then L2; writes go to both. Both tiers apply the *same declared* strategy, so a
value's lifetime does not depend on which tier answered.

Every cached thing carries four attributes — `cache_strategy`, `cache_name`, `cache_key`,
`value` — so an entry can be reasoned about, and evicted correctly, wherever it is found.

Strategies: `TTL`, `LRU_COUNT` (bounded, least recently *read* leaves),
`NUM_OBJECTS` (bounded, oldest *written* leaves — reads do not extend life), and
`CATEGORY` (grouped, invalidated as a unit; a domain rebuild drops every listing for that
domain, which no per-key TTL can express).

## The limit, stated rather than discovered
"Mirror Redis's eviction policy" cannot be fully honoured. Redis also evicts under its own
memory pressure via `maxmemory-policy`, which an in-process cache cannot observe, so L1 can
hold a key Redis has already dropped.

Three things follow. L1's TTL never exceeds the Redis TTL, so the mirror cannot outlive the
shared entry on age. A hit in L1 is checked against L2 when L2 is reachable, and a
disagreement evicts L1 and counts `stale_l1_reads`. And a non-zero `stale_l1_reads` is a
signal to reduce the mirror's capacity or turn the toggle off — not a metric to ignore.

Where staleness is unacceptable, do not cache: `ListDataInstancesWf` is deliberately
uncached because a stale realtime or CDC instance state is worse than a slower page.

## Tenancy
`tenant_id` is part of every key and `build_key` refuses to produce one without it. A key of
`mios:state=live` serves one tenant's rows to another — a data leak wearing a performance
optimisation's clothes.

## Availability
A cache is an optimisation. Redis being down produces misses, never failures: the client is
built lazily, every call is guarded, and `available()` returning false is a normal path.
