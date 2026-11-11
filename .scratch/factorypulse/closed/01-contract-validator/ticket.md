# 01: Event contract & validator

**What to build:** a single, versioned sensor-event contract that every stage of the pipeline reads from and writes to, plus a shared validator with unit tests proving it. This is the testing seam for the whole system.

**Blocked by:** None (can start immediately).

Status: `closed`

- [X] The repo defines one sensor-event contract covering event_id, timestamp, site_id, machine_id, sensor_type, value, unit, and status.
- [X] A shared validator accepts events conforming to the contract and rejects out-of-range values, null required fields, unknown sensor types or units, and invalid statuses.
- [X] Unit tests cover representative valid and invalid events; the test suite passes.
- [X] The project is under version control with commits landing incrementally.

## Current state

- `docs/adr/0001-event-contract-as-single-seam.md` records the contract as the single seam. `tests/test_schema_sync.py` keeps the JSON Schema mirror in step with `factorypulse.contract`.
- The validator is minimal-strict: an event with extra fields passes (`test_extra_unknown_fields_are_allowed`).
- The physical ranges are the validator's ceiling. Anomaly detection works inside them.

## Log

2026-09-10 · triage · 623463b · created · -
2026-09-10 · impl · 4335c05 · contract, JSON Schema mirror and validator; 43 tests pass · -
2026-09-10 · impl · 1ace814 · resolution commit recorded · -
2026-10-11 · triage · 62c8e76 · Status `resolved` renamed `closed` · -
2026-10-13 · triage · da3af0b · Status line format · -
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
