# 08: Anomaly detection

**What to build:** the predictive-maintenance core — a PySpark job computing rolling z-scores on vibration and temperature per machine, writing per-machine anomaly scores and a nominal/warning/critical status for each time window.

**Blocked by:** 11 Weekly mart and the idempotent write seam.

Status: `closed`

- [x] A PySpark job computes rolling z-scores on vibration and temperature per machine over a time window.
- [x] Output is a queryable analytics table of anomaly scores: per machine and window, a score plus a status (nominal/warning/critical).
- [x] On seeded labeled fixtures, known-normal machines score low and injected anomalies score high.
- [x] Scores join to the analytics tables produced earlier.

## Current state

Decisions later tickets depend on:

- `mrt_anomaly_scores` holds one row per machine, hourly window and scored sensor (temperature, vibration), keyed on `(machine_id, window_start, sensor_type)` and written through the shared idempotent write. Each row carries the baseline mean, standard deviation and count it was scored against.
- `mrt_machine_rolling_window` is not built. The scoring job computes the Baseline from `mrt_machine_hourly`.
- The thresholds, the status vocabulary, the worst-sensor rule and the Baseline parameters live in `anomaly_core`. The job spells none of them.
- The table-level tests run only with `FACTORYPULSE_DOCKER_TESTS=1`.

Known gaps owned elsewhere:

- The dashboard still reads the old name `mrt_machine_anomaly_scores` (ticket 09).
- The DAGs do not run the scoring job, and `mrt_anomaly_scores` has no quality checks. No ticket yet.
- `spark/query_analytics.py` loops over `ANALYTICS_MODELS` only. No ticket yet.

## Log

2026-10-13 · triage · - · reopened: no table written, criteria unmet · -
2026-11-08 · impl · 1c92ee6 · job writes `mrt_anomaly_scores`; host 358 passed, Spark 19 passed · -
2026-11-08 · review · e9a4514 · block (P1) · .scratch/factorypulse/closed/08-anomaly-detection/review.md
2026-11-08 · triage · 76af654 · P1 cut ratified; S1, S4, S6, P2 to the documentation pass; S2, S3, S5, S7, P3, P4, P5 -> 14 · -
2026-11-09 · triage · - · converted to the contract / Current state / Log layout · -
2026-11-09 · fix · e2bad1e · fixed P1, P2, S1, S4, S6 (documentation pass) · .scratch/factorypulse/closed/08-anomaly-detection/review.md
2026-11-09 · rereview · - · pass · fixed P1, P2, S1, S4, S6 · S2, S3, S5, S7, P3, P4, P5 -> 14 · S8, P6, P7 open, no ticket · .scratch/factorypulse/closed/08-anomaly-detection/review.md
