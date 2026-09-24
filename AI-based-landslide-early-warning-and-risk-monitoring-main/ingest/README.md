# ingest/

Data providers, the Celery schedule and the synthetic engine.

## What lands here, and when

**Phase 2** delivers all of it:

- `providers/` — one module per source implementing the `DataProvider` protocol
  (`name`, `status`, `fetch()`, `health()`), with a registry, per-provider env
  toggles, Redis caching with TTL, tenacity retry with exponential backoff and
  automatic fallback to the synthetic provider. A Prometheus metric per provider.
- `synthetic/` — the seeded, deterministic generator: a monsoon Markov wet/dry
  chain with Gamma intensities, an orographic multiplier by elevation and
  windward aspect, injectable cyclone events, and a two-layer bucket
  soil-moisture model. Five years hourly over roughly 250 grid nodes.
- `tasks/` — the Celery app and beat schedule: forecast every 30 minutes,
  observations every 15, satellite daily, aggregates hourly, inference every 30.
- `cli/` — `python -m ingest.terrain build --bbox ner --resolution 30` and the
  other operational entry points, idempotent and resumable.

**Phase 1** uses this package for the terrain pipeline before the provider
abstraction exists, so the terrain CLI lands here first.

## The rule that governs this package

A provider may fail. A provider may be switched off. A provider may be slow and
serve from cache. What a provider may **never** do is return synthetic data
without labelling it. Every payload carries `live`, `cached` or `simulated`, and
the API passes that label through to a visible chip in the interface.

See `../docs/DATA_SOURCES.md` for the source register and the measured status of
each endpoint.
