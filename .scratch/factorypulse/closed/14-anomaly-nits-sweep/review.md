---
ticket: .scratch/factorypulse/closed/14-anomaly-nits-sweep/ticket.md
verdict: pass
---

# Review: ticket 14 — Anomaly nits sweep

**Final verdict:** pass, on the re-review of `0cebba5` (range `fd5a390..0cebba5`).

**Standards:** no documented standard is broken; S1 to S6 are fixed. Two `minor` judgement calls stay open (S7, S8).

**Spec:** all seven checklist items are met and each has a test. P1 and P3 are fixed; triage fixed P2. One `minor` stale contract fact stays open (P4).

Runs: host suite 378 passed, 32 skipped. `FACTORYPULSE_DOCKER_TESTS=1` on `tests/test_anomaly_detection.py`: 46 passed in 90 s, both seeds.

## Open findings

- **S7 · minor · 2026-11-10** — open, no ticket. Possible Divergent Change. The statistics helpers `_two_sided_t_tail`, `_poisson_quantile`, `_expected_chance_criticals` and `_t_tail_by_integration` (`tests/test_anomaly_detection.py:80-147`) live in the Spark fixture test module. That module now changes for the bar's maths and for the fixture lake. Move the helpers and their two host tests to a test helper module.
- **S8 · minor · 2026-11-10** — open, no ticket. `_nan_hour_temperature` (`tests/test_anomaly_detection.py:349-360`) reads the mart through `DeltaTable(...).to_pyarrow_table()` (`:358`), not `lake.read_table` like the rest of the module. The reason is real: `lake.read_table` returns pandas, which shows a null as NaN, so it would hide the null this test must catch. No comment says so. Writing rules: "Why code does something unusual: a code comment next to it". Add the one-line reason.
- **P4 · minor · 2026-11-10** — open, no ticket. Contract item 7 says the opt-in run takes "about 45 s". With two seeds it takes about 100 s, and the module docstring says so (`tests/test_anomaly_detection.py:13`). The code is right; the contract's example number is stale. Triage corrects it.

## Coverage

Checklist item to test (`tests/test_anomaly_detection.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. NaN mean or standard deviation gives no score; the job drops a NaN average | `tests/test_anomaly_core.py::test_z_score_is_none_without_a_usable_baseline`; `test_a_nan_hourly_average_has_no_score_row_and_leaves_the_baseline_usable`; `test_score_table_holds_one_row_per_machine_window_and_scored_sensor` |
| 2. `ANOMALY_SCORE_KEYS` in `analytics` | `test_score_table_is_keyed_on_machine_window_and_sensor` |
| 3. Status names imported; `STATUSES` in severity order | `tests/test_anomaly_core.py::test_statuses_are_in_severity_order_mildest_first` |
| 4. Log counts merged rows, no second UDF run | `tests/test_spark_common.py::test_merge_into_delta_returns_the_rows_the_merge_wrote`; `test_job_logs_the_rows_its_merge_wrote`; `test_rerunning_the_job_leaves_the_same_rows` |
| 5. "Score low" chance bar written down | `test_known_normal_machines_score_low`; `test_two_sided_t_tail_matches_the_integrated_density`; `test_poisson_quantile_is_the_smallest_count_reaching_the_level` |
| 6. Second fixture seed | every Spark test, ids `[seed8]` and `[seed2026]`; `tests/test_anomaly_core.py::test_a_thinner_baseline_calls_more_normal_readings_critical` |
| 7. Opt-in run time | module docstring of `tests/test_anomaly_detection.py` (measured 90 s) |

Rejection branches:

| Branch | Tests |
| --- | --- |
| `z_score`: NaN mean or standard deviation | `tests/test_anomaly_core.py::test_z_score_is_none_without_a_usable_baseline` |
| `z_score`: no value or a NaN value | `tests/test_anomaly_core.py::test_z_score_is_none_without_a_value` |
| Job: NaN hourly average | `test_a_nan_hourly_average_has_no_score_row_and_leaves_the_baseline_usable` (asserts the mart holds NaN, not null) |
| Job: null hourly average | `test_a_window_without_a_reading_has_no_score_row` |
| `merge_into_delta`: duplicate source key counted once | `tests/test_spark_common.py::test_merge_into_delta_returns_the_rows_the_merge_wrote` |
