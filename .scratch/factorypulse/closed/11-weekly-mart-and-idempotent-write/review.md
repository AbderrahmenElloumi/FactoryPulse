---
ticket: .scratch/factorypulse/closed/11-weekly-mart-and-idempotent-write/ticket.md
verdict: pass
---

# Review: ticket 11 — Weekly mart and the idempotent write seam

**Final verdict:** pass, on the re-review of `9a47403` (range `a4d8292..9a47403`, a test-only fix round).

**Standards:** no hard violations. Judgement calls on the fake MERGE tests and the registry naming stay open as `minor` (S1-S6).

**Spec:** all five checklist items hold. The two `major` coverage gaps (vacuous duplicate-source test, untested empty-keys branch) are fixed. Item 4 rests on a static check, and five other `minor` findings stay open (P1-P6).

## Open findings

- **S1 · minor · 2026-11-07** — open, no ticket. `analytics_path` resolves any registered table, including the Spark-written `mrt_anomaly_scores`, but its name promises an analytics model (`src/factorypulse/analytics.py:168-177`). Rename it, or split the Spark-written lookup.
- **S2 · minor · 2026-11-07** — open, no ticket. The weekly fixture assertion repeats the hourly one: the same `cast` block and the same `full outer join` (`dbt/tests/assert_mrt_machine_weekly_matches_expected_fixture.sql:12-82` against `assert_mrt_machine_hourly_matches_expected_fixture.sql:12-76`). The float comparison is already the `floats_match` macro; a macro over `(model, key, date expression)` would hold the rest.
- **S3 · minor · 2026-11-07** — open, no ticket. The comment in `test_merge_into_delta_collapses_duplicate_source_keys` says Delta rejects the MERGE, but the target is empty, so the failure there is a double insert (`tests/test_spark_common.py:311`). Reword the comment.
- **S4 · minor · 2026-11-07** — open, no ticket. `key_of` in `FakeMergeSpark.sql` repeats the key tuple built in `FakeFrame.dropDuplicates` (`tests/test_spark_common.py:181-182` and `:221`). One module-level helper would serve both.
- **S5 · minor · 2026-11-07** — open, no ticket. The duplicate-source test reads the private view name `_merge_source` (`tests/test_spark_common.py:324`), so renaming the view in `spark/common.py:185` breaks the test.
- **S6 · minor · 2026-11-07** — open, no ticket. `test_merge_into_delta_accepts_a_duplicated_source_key_already_in_the_target` names the fake's view, not the behaviour (`tests/test_spark_common.py:327`). `docs/agents/gotchas/delta.md` cites the name, so a rename edits both.
- **P1 · minor · 2026-11-07** — open, no ticket. Checklist item 4 (weekly re-run leaves the count unchanged) is proven only by a text check for `materialized='table'` and the absence of `insert into` / `merge into` (`tests/test_dbt_project.py:224-232`). No test re-runs the build.
- **P2 · minor · 2026-11-07** — open, no ticket. Weekly `<sensor>_avg` columns are the unweighted mean of hourly averages (`dbt/models/marts/mrt_machine_weekly.sql:65-71`; `dbt/seeds/expected_mrt_machine_weekly.csv:2` expects vibration `1.6`, not the per-reading `1.733`). The model comment says so; the column names do not. Weight by `reading_count`, or name the metric.
- **P3 · minor · 2026-11-07** — open, no ticket. `dropDuplicates(keys)` keeps an arbitrary row when one key carries different values (`spark/common.py:185`), so a replay in another order can change row content. Document the rule, or make a conflicting duplicate a loud error.
- **P4 · minor · 2026-11-07** — open, no ticket. The `spark/query_analytics.py` docstring says every registered table is read (`:3-6`), but the loop reads `ANALYTICS_MODELS` only (`:31`), so `mrt_anomaly_scores` is never read. `dbt/README.md:28` calls the query a read of "the marts". Say which tables it reads, or read `REGISTERED_TABLES`.
- **P5 · minor · 2026-11-07** — open, no ticket. `dbt/README.md:14-15` says the other three models read `fct_sensor_readings_clean`; `mrt_machine_weekly` reads `mrt_machine_hourly`.
- **P6 · minor · 2026-11-07** — open, no ticket. The fake MERGE compares keys with Python `==`, so a NULL key matches a NULL key (`tests/test_spark_common.py:181-189`). Delta never matches NULL keys. No test uses NULL keys today. Make NULL never match, or state the limit in the fake's docstring.

## Coverage

Checklist item to test (`tests/test_spark_common.py` for items 1-2, `tests/test_dbt_project.py` for items 3-5, unless named):

| Checklist item | Tests |
| --- | --- |
| 1. One shared merge path for raw ingest and anomaly write | `test_raw_ingest_and_anomaly_write_share_the_merge_helper`, `test_merge_into_delta_upserts_by_the_requested_keys`, `test_merge_into_delta_supports_composite_keys`; `tests/test_anomaly_detection.py::test_rerunning_the_job_leaves_the_same_rows` (opt-in Docker) |
| 2. Batch re-run leaves the row count unchanged | `test_merge_into_delta_is_idempotent_when_the_same_range_is_replayed`, `test_merge_into_delta_updates_a_replayed_row_instead_of_duplicating_it`, `test_merge_into_delta_collapses_duplicate_source_keys`, `test_merge_into_delta_accepts_a_duplicated_source_key_already_in_the_target` |
| 3. Machine × ISO week mart exists, rolls up, is queryable | `test_weekly_mart_is_registered_with_its_iso_week_columns`, `test_weekly_mart_rolls_up_from_the_hourly_mart`, `test_every_analytics_model_has_a_sql_file`, `test_weekly_fixture_assertion_compares_the_model_to_the_expected_seed`, `test_expected_weekly_fixture_covers_every_machine_week_of_the_seed`, `test_query_job_reads_the_analytics_paths_shared_module`; dbt `assert_mrt_machine_weekly_matches_expected_fixture` |
| 4. Weekly re-run leaves the row count unchanged | `test_weekly_mart_key_is_deterministic`, `test_schema_yml_declares_a_primary_key_per_model`, dbt `unique` test on `machine_week_key` (static only, P1) |
| 5. Registry lock covers the new mart and its columns | `test_weekly_mart_is_registered_with_its_iso_week_columns`, `test_model_sql_column_lists_match_the_column_contracts`, `test_expected_weekly_fixture_header_is_the_model_column_contract`, `test_analytics_path_resolves_the_spark_written_anomaly_table` |

Rejection branches and error paths:

- Empty key list raises `MergeKeyError`, no SQL runs: `test_merge_into_delta_rejects_an_empty_key_list`.
- Missing key column raises `MergeKeyError`, no SQL runs: `test_merge_into_delta_rejects_a_frame_missing_a_key_column`.
- Duplicate source keys collapsed before the MERGE: `test_merge_into_delta_collapses_duplicate_source_keys`, `test_merge_into_delta_accepts_a_duplicated_source_key_already_in_the_target`. Deleting the `dropDuplicates` call fails both.
- Unknown table rejected by `analytics_path`: `tests/test_dbt_project.py::test_analytics_path_rejects_unknown_models`.

Real runs at `4946b79`: `dbt build --target lake` twice left `mrt_machine_weekly` at 8 rows; a second identical `batch-ingest` over overlapping snapshots left `raw_sensor_events` at 4003 rows. Host suite at `9a47403`: 148 passed, 2 skipped.
