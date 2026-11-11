# 04: Tracer bullet — source to lake

**What to build:** the vertical end-to-end path that makes the whole platform real: sensor events flow from the simulator through Kafka into Spark Structured Streaming, landing as a Delta table on MinIO that Spark SQL can query.

**Blocked by:** 02 Sensor simulator, 03 Local infra.

Status: `closed`

- [X] Simulator events flow producer → Kafka topic → Spark Structured Streaming → Delta table on MinIO.
- [X] A batch path can reprocess historical events into the same Delta table.
- [X] The Delta table is queryable with Spark SQL and shows the raw sensor events.
- [X] Streaming and batch writes land in the same logical lake.

## Current state

- Streaming and batch write one raw Delta table, `raw_sensor_events`. The streamer appends; the batch path MERGEs by `event_id`, so a backfill is idempotent. A streaming replay can leave an event twice, and `fct_sensor_readings_clean` keeps one copy.
- The streamer writes each event the validator rejects to `raw_sensor_events_invalid`, with its `_validation_errors`. The batch path counts and skips them.

## Log

2026-09-10 · triage · 623463b · created · -
2026-09-11 · impl · 34159a9 · producer, streaming, batch and query jobs, compose services; 15 host tests · -
2026-09-11 · fix · 71d6c59 · integration fixes from the first live run; host 75 passed, mypy clean · -
2026-09-12 · triage · 9a180a3 · Status `resolved` after a green produce, stream, query and batch run · -
2026-10-11 · triage · 62c8e76 · Status `resolved` renamed `closed` · -
2026-10-13 · triage · da3af0b · Status line format · -
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
