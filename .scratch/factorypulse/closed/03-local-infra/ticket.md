# 03: Local infra — Docker, Kafka (KRaft), MinIO

**What to build:** the local infrastructure that everything else runs on: a single-command Docker platform with Kafka in KRaft mode and MinIO object storage, pre-initialized with the topic and bucket the pipeline uses.

**Blocked by:** None (can start immediately).

Status: `closed`

- [X] A single compose command starts Kafka in KRaft mode (no ZooKeeper) and MinIO on one host.
- [X] An init step creates the sensor-events topic and the factorypulse bucket automatically.
- [X] The stack restarts reliably from scratch and all services report healthy.
- [X] No resources run outside the compose project, so nothing can incur cloud cost.

## Current state

- Kafka is a transport buffer with no volume. The durable store is the lake on MinIO, and `kafka-init` recreates the topic on every start. The comments in `compose.yaml` give the reasons for the volume, the advertised listener and the healthcheck path.

## Log

2026-09-10 · triage · 623463b · created · -
2026-09-10 · impl · 0e3bc3e · compose stack with KRaft Kafka, MinIO and two init jobs; all services healthy after a fresh down and up · -
2026-09-10 · impl · 58ccea3 · resolution commit recorded · -
2026-10-11 · triage · 62c8e76 · Status `resolved` renamed `closed` · -
2026-10-13 · triage · da3af0b · Status line format · -
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
