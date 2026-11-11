# ADR 0001: The event contract is the single seam

Date: 2026-10-13
Status: accepted

## Context

Every stage of FactoryPulse either produces or consumes a sensor event: the
simulator emits them, streaming and batch ingestion write them into the raw
lake, dbt cleans and models them, quality checks assert things about them, and
the anomaly job scores them. Each stage is written in a different language or
runtime — Python for the simulator and shared components, PySpark for ingestion
and scoring, SQL for the transformation layer, and a Python runtime in a
separate container for quality checks and the dashboard.

The cheap local move is per-stage validation: each stage asserts the fields it
happens to need. That is also the move that lets the definitions drift, and it
fails silently, because a stage that checks only what it uses accepts an event
that a neighbouring stage will reject.

## Decision

One contract definition owns the event's shape, sensor types, units, operating
ranges, and status vocabulary. Every stage validates against it at its own
boundary, and no stage defines an event field, unit, or status of its own.

The contract is expressed once for Python consumers and once as a JSON Schema
for the non-Python stages, with a test that keeps the two representations in
sync. The Python validator returns a list of human-readable, field-prefixed
errors rather than raising, so a caller decides whether to route a bad row or to
fail.

## Consequences

- A schema change is made once and breaks the build wherever a stage disagrees,
  rather than drifting quietly.
- The validator sits in a shared module consumed across container boundaries.
  The Spark image imports it flat, which imposes a Python version constraint on
  that module: it must stay importable on Python 3.8 and must avoid syntax the
  image's interpreter cannot parse.
- The JSON Schema mirror must be updated alongside the Python definition; the
  sync test is what makes that obligation real rather than aspirational.
- Stages cannot evolve their own richer notion of an event without changing this
  decision, which is the intended friction.

## Alternatives considered

- **Per-stage validation.** Rejected: definitions drift, and drift is silent
  until a downstream stage rejects data an upstream stage accepted.
- **Schema registry at the Kafka boundary only.** Rejected: it covers the
  streaming path and leaves the batch, transformation, and dashboard paths
  unconstrained, so the contract would bind only the stages that already agree.
