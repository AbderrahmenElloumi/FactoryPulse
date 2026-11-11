# 11: Weekly mart and the idempotent write seam

**What to build:** the weekly aggregation as a real second grain, and one merge path that makes re-running any write safe. Running batch ingestion and the weekly build twice over the same range must leave exactly the rows that running them once leaves, and the weekly mart must be queryable per machine per ISO week.

**Blocked by:** None (can start immediately).

Status: `closed`

- [x] One shared merge path performs both the raw-ingest write and the anomaly write, so the idempotency guarantee has a single implementation rather than one per caller.
- [x] Re-running batch ingestion over the same range leaves the row count unchanged.
- [x] A machine × ISO week mart exists, rolls up from the hourly mart, and is queryable.
- [x] Re-running the weekly build leaves the row count unchanged.
- [x] The registry that names every table and declares its columns lists the new mart and its columns, and the test that locks that registry against the dbt models covers it.

## Current state

Decisions later tickets depend on:

- `merge_into_delta` in `spark/common.py` is the one idempotent write to the lake. Batch ingestion merges on `event_id`; the anomaly job merges `mrt_anomaly_scores` on its own keys. A new Spark writer goes through it.
- `merge_into_delta` raises `MergeKeyError` before any SQL runs when the key list is empty or the source frame lacks a key column.
- `merge_into_delta` drops duplicate source keys before the MERGE, because overlapping backfill snapshots repeat events. Which copy survives a conflicting duplicate is undefined (open finding P3).
- `mrt_machine_weekly` holds one row per machine and ISO week, rolls up from `mrt_machine_hourly`, is materialized as a table and is keyed on `machine_week_key`. A re-run replaces its rows.
- The registry in `factorypulse.analytics` lists `mrt_machine_weekly` and its columns among the dbt models. Tables written by Spark sit in a separate list, and `analytics_path` resolves both kinds.

## Log

2026-10-13 · triage · 11bccc7 · created, split out of ticket 06 · -
2026-11-07 · impl · 4946b79 · shared merge helper and weekly mart; host 146 passed, 2 skipped · -
2026-11-07 · review · a4d8292 · block (2 major: vacuous duplicate-source test, untested empty-keys branch) · .scratch/factorypulse/closed/11-weekly-mart-and-idempotent-write/review.md
2026-11-07 · fix · 9a47403 · fixed both majors and the stale test-module docstring; host 148 passed, 2 skipped · .scratch/factorypulse/closed/11-weekly-mart-and-idempotent-write/review.md
2026-11-07 · rereview · 2c546e5 · pass; minors left open · .scratch/factorypulse/closed/11-weekly-mart-and-idempotent-write/review.md
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
