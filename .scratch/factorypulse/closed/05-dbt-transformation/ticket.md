# 05: dbt transformation layer

**What to build:** the analytics layer — clean, versioned SQL models built by dbt over the Delta lake: a machine dimension, a cleaned sensor-readings table, and hourly per-machine aggregates.

**Blocked by:** 04 Source to lake.

Status: `closed`

- [x] dbt models produce clean analytics tables (machine dimension, clean sensor readings, hourly machine aggregates) over the Delta lake.
- [x] Models are pure SQL, versioned, and reproducible.
- [x] dbt tests assert not-null, uniqueness, and accepted values; fixture-based model tests pass for the hourly aggregate.
- [x] Output tables are queryable the same way as the raw lake.

## Current state

- `scripts/dbt.sh` has no `test` command. Every dbt run starts from an empty session catalog, so the dbt tests run inside `dbt build` (`docs/agents/gotchas/dbt.md`).

## Log

2026-09-10 · triage · 623463b · created · -
2026-09-23 · impl · 9c5cbd1 · three models, fixture seeds and assertion; host 103 passed; pre-commit review findings 1-6 parked in ticket 07 · -
2026-10-07 · triage · 0e091e0 · closed · -
2026-10-13 · triage · da3af0b · Status line format · -
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
