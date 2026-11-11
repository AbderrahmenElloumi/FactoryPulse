# FactoryPulse Domain Glossary

Terms as this project uses them. Use these words exactly; do not drift to
synonyms. This file defines *concepts*, never which module implements them —
naming an implementation here is how it previously came to describe behaviour
that had not been built.

## Core Concepts

- **Event**: a single sensor reading emitted by the simulator. It is the unit
  that flows through every stage of the pipeline.
- **Event Contract**: the canonical schema every event must satisfy. Its
  required fields are `event_id`, `ts`, `site_id`, `machine_id`, `sensor_type`,
  `value`, `unit`, and `status`. The contract is the single seam shared by every
  stage: each stage either produces or consumes contract-conforming events.
- **Site**: a physical location where machines are installed. A site holds many
  machines.
- **Machine**: a physical asset emitting sensor readings.
- **Sensor Type**: one of `temperature`, `vibration`, `pressure`, `humidity`.
  Each sensor type reports in exactly one unit.
- **Sensor Reading**: the `value` and `unit` pair carried by an event, for one
  sensor type on one machine at one instant.

## Status Vocabulary

- **Health Status**: the three-valued judgement carried by an event and by an
  anomaly score — `nominal`, `warning`, or `critical`. A machine's status is the
  worst status among its sensors.

## Lakehouse

- **Raw Lake**: the Delta table holding contract-conforming events as ingested,
  before any cleaning. It preserves rejected rows separately so that a bad row
  can be read back and diagnosed rather than guessed at.
- **Analytics Layer**: the cleaned and modelled tables derived from the raw
  lake. It has three kinds of table, distinguished by prefix:
  - **Dimension** (`dim_`): descriptive entities, such as machines.
  - **Fact** (`fct_`): cleaned, deduplicated observations at their natural grain.
  - **Mart** (`mrt_`): aggregates built for a consumer, such as per-machine
    hourly summaries, weekly rollups, and anomaly scores.
- **Lake Path**: the location of a table within the lake. Tables are addressed by
  name, and a name resolves to one path.

## Analysis

- **Window**: a bounded span of time over which readings are summarised. A
  rolling window moves with each observation; an hourly or weekly window is
  fixed to a calendar boundary.
- **Anomaly Score**: a per-machine, per-sensor-type, per-window measure of how
  far that sensor's readings deviate from the machine's own recent behaviour,
  expressed as a z-score.
- **Baseline**: the trailing windows of the same machine and sensor type that
  precede a scored window, never including it. An Anomaly Score is measured
  against it. Too few baseline windows means no score.
- **Machine Health**: the summary view of a machine's current state, derived
  from its anomaly scores and recent readings.

## Quality and Delivery

- **Quality Check**: one named, falsifiable assertion about a table — a schema
  requirement, a value range, a missingness bound, or a set of allowed values.
- **Quality Report**: the outcome of running a set of quality checks against a
  table, naming every check that failed. A report that cannot name a failure is
  not a report.
- **Release**: a version of the project published from a tagged commit, carrying
  its own version number, changelog entry, and README.
