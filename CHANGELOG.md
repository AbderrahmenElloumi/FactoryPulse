# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [1.0.0] - 2026-11-11

### Added

- Airflow schedules the batch work: `factorypulse_daily` runs batch
  ingestion, the raw lake checks, the daily dbt build and the model checks;
  `factorypulse_weekly` builds the weekly mart and checks it.
- Great Expectations checks the raw lake, the daily models and the weekly
  mart, and fails on any broken check.
- Spark scores each machine's hourly temperature and vibration as a z-score
  against its trailing 24-hour baseline, into `mrt_anomaly_scores`.
- A weekly per-machine mart, `mrt_machine_weekly`.
- A Streamlit dashboard showing fleet KPIs, hourly trends and the at-risk
  machines.
- `bash scripts/lake.sh all` runs the whole pipeline once, from the platform
  to the anomaly scores.
- Issue templates, a pull request template and a contributing guide. An
  accepted pull request is imported into the development line and credited in
  the changelog entry of the release that carries it.

### Changed

- Compose reads every credential from `.env`: copy `.env.example` to `.env`
  first. MinIO refuses to start without its credentials, and the DAG file
  refuses to load without `AIRFLOW_JWT_SECRET`.
- The README and `docs/architecture-guide.md` describe the built pipeline.
- Releases are published to this repository as one commit per version, tagged
  `vX.Y.Z`.

### Removed

- The earlier `v1.0.0` tag, which labelled a state that did not meet its own
  acceptance criteria. This release is the first `v1.0.0`.

## [0.1.0] - 2026-09-21

### Added

- The event contract shared by every stage, with a JSON Schema mirror for the
  non-Python stages and a test keeping the two in sync.
- A sensor simulator emitting temperature, vibration, pressure, and humidity
  readings, with configurable volume, a seed for reproducible output, and
  injected anomalies.
- Local infrastructure under one `docker compose up`: single-node Kafka in KRaft
  mode, MinIO with idempotent init jobs, and a query service.
- PySpark structured streaming and batch ingestion into a raw Delta table on
  MinIO, with an idempotent merge so re-runs do not duplicate.
- A dbt analytics layer over the Delta lake producing a machine dimension, a
  cleaned readings fact, and a per-machine hourly mart, with dbt tests and a
  fixture-comparison test.
- A test suite covering the contract, validator, simulator, Spark common layer,
  and the dbt project.
