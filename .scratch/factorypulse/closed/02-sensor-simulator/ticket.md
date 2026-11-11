# 02: Sensor simulator

**What to build:** a Python simulator that emits realistic smart-factory sensor readings — temperature, vibration, pressure, humidity — attributed to machines and sites, with occasional injected anomalies, fully deterministic under a seed.

**Blocked by:** 01 Event contract & validator.

Status: `closed`

- [X] Running the simulator emits events for all four sensor types, each attributed to a machine and a site.
- [X] Output is byte-identical for a fixed seed and reproduces identically across runs.
- [X] Anomalies (spikes and drift) are injected at a configurable rate and detectable in the output.
- [X] Every emitted event passes the contract validator from ticket 01.
- [X] The targeted records-per-day is configurable (default 10K).

## Current state

- The simulator emits only `nominal` and `critical`. Assigning `warning` belongs to anomaly scoring (`test_anomaly_events_flagged_critical`).
- Spikes and drifts stay inside the physical ranges, so every emitted event passes the validator (`test_every_event_passes_the_contract_validator`).
- The simulator CLI writes JSON Lines to stdout. Publishing to Kafka is `factorypulse.producer`, built in ticket 04.

## Log

2026-09-10 · triage · 623463b · created · -
2026-09-10 · impl · 328f14b · seeded simulator with spikes and drifts; 58 tests pass, mypy clean · -
2026-09-10 · impl · 706058f · resolution commit recorded · -
2026-09-11 · impl · f28325a · cleanup of simulator, schema and validator tests · -
2026-10-11 · triage · 62c8e76 · Status `resolved` renamed `closed` · -
2026-10-13 · triage · da3af0b · Status line format · -
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
