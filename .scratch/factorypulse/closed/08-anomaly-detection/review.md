---
ticket: .scratch/factorypulse/closed/08-anomaly-detection/ticket.md
verdict: pass
---

# Review: ticket 08 — Anomaly detection

**Final verdict:** pass, on the re-review of `e2bad1e` (range `a7b0801..e2bad1e`, a documentation-only round).

**Standards:** every claim the documentation pass makes matches the code; the new Delta gotcha fits 5 lines and the index lists it. One stale paragraph stays open as a `minor` (S8).

**Spec:** P1 (the ratified cut of `mrt_machine_rolling_window`) and P2 (the design signatures) are fixed; two `minor` design inconsistencies stay open (P6, P7). S2, S3, S5, S7, P3, P4, P5 moved to ticket 14.

## Open findings

- **S8 · minor · 2026-11-09** — open, no ticket. `.scratch/design.md:142-144` says the job "currently discards the frame, so no table is ever produced". `main()` writes the frame through `merge_into_delta` (`spark/anomaly_detection.py:121`). Violates "write what is true now". Delete the sentence.
- **P6 · minor · 2026-11-09** — open, no ticket. `.scratch/design.md:146` puts "the sensor filter" in the job, and `:147-150` puts `SCORED_SENSORS` in `anomaly_core` (`src/factorypulse/anomaly_core.py:20`). The `anomaly_core` interface list (`.scratch/design.md:125-128`) omits `SCORED_SENSORS`, `BASELINE_HOURS` and `MIN_BASELINE_WINDOWS`. List the three constants in the interface, and say that the job applies the filter.
- **P7 · minor · 2026-11-09** — open, no ticket. `.scratch/design.md:58` and `:224` cite `spec.md:93` for the table name. Line 93 is the object-storage decision; the anomaly detection decision is `spec.md:97`. Cite the decision by name, not by line.

## Coverage

Checklist item to test (`tests/test_anomaly_detection.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. Rolling z-scores per machine over a time window | `test_baseline_covers_only_the_trailing_window_before_the_scored_one`, `test_baseline_forgets_windows_older_than_the_baseline_hours`, `test_windows_without_enough_baseline_have_no_score`, `test_each_window_is_one_hour_long`, `test_scored_sensors_are_vibration_and_temperature_from_the_contract`, `test_every_scored_sensor_has_an_hourly_average_to_score`; `tests/test_anomaly_core.py::test_z_score_measures_deviation_in_standard_deviations` |
| 2. Queryable table, score and status per machine and window | `test_score_table_holds_one_row_per_machine_window_and_scored_sensor`, `test_score_table_declares_its_columns_for_lake_readers`, `test_score_table_is_keyed_on_machine_window_and_sensor`, `test_rerunning_the_job_leaves_the_same_rows`; `tests/test_anomaly_core.py::test_classify_maps_the_z_score_magnitude_to_a_contract_status`, `::test_machine_status_is_the_worst_sensor_status`, `::test_machine_status_accepts_any_iterable` |
| 3. Seeded labelled fixtures: normal low, anomalies high | `test_known_normal_machines_score_low`, `test_injected_anomalies_score_high`, `test_spiked_machines_score_low_before_the_spike` |
| 4. Scores join earlier analytics tables | `test_scores_join_to_the_hourly_mart_and_the_machine_dimension` |

Rejection branches and error paths:

- `z_score` gives no score: `tests/test_anomaly_core.py::test_z_score_is_none_below_the_minimum_baseline_windows`, `::test_z_score_is_none_without_a_value`, `::test_z_score_is_none_without_a_usable_baseline`.
- `classify(None)` is nominal: `tests/test_anomaly_core.py::test_classify_treats_a_window_without_a_score_as_nominal`.
- `machine_status` rejects bad input: `tests/test_anomaly_core.py::test_machine_status_rejects_an_unknown_status`, `::test_machine_status_rejects_no_sensor_statuses`.
- `analytics_path` rejects an unregistered table: `test_analytics_path_rejects_an_unregistered_table_under_an_explicit_root`.
- A null hourly average writes no row: `test_a_window_without_a_reading_has_no_score_row`.
- `merge_into_delta` at a fresh location: `tests/test_spark_common.py::test_merge_into_delta_creates_a_new_table_with_the_source_columns`. The silent column drop on an existing table has no test; the Delta gotcha records it.

Host suite: `.venv/Scripts/python.exe -m pytest -q` gives 358 passed, 19 skipped. Spark fixture tests: `FACTORYPULSE_DOCKER_TESTS=1 pytest tests/test_anomaly_detection.py` gives 19 passed. The scoring code is unchanged since `1c92ee6`.
