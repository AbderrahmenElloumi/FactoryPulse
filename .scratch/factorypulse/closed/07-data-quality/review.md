---
ticket: .scratch/factorypulse/closed/07-data-quality/ticket.md
verdict: pass
---

# Review: ticket 07 — Great Expectations data quality

**Final verdict:** pass, on the first review of `f66aee0` (range `10d813f..f66aee0`).

**Standards:** no hard violation; ADR 0001 holds, because every allowed value, unit and range comes from `factorypulse.contract`. Nine `minor` judgement calls stay open (S1-S7, S9, S10). S8 (the stage names spelled in several files) is tracked as review 06 S-7.

**Spec:** all three checklist items hold, and the ticket 05 findings 1 and 2 are addressed. P1 (the DAG command had no project directory) moved to ticket 06, which fixed it. P2-P4 stay open as `minor`.

## Open findings

- **S1 · minor · 2026-11-08** — open, no ticket. Outcomes are keyed by check name (`src/factorypulse/quality/__init__.py:80`), so two checks with one name collapse and a pass can hide a failure. Names are unique today; nothing asserts it.
- **S2 · minor · 2026-11-08** — open, no ticket. Every raw `event_id` goes into one `ExpectColumnValuesToBeInSet` config (`src/factorypulse/quality/expectations.py:132-136`), so the suite grows with the lake. A set difference in pandas would keep it small.
- **S3 · minor · 2026-11-08** — open, no ticket. A null `site_id` fails both "site_id is never null" and "each machine reports from one site" (`src/factorypulse/quality/expectations.py:102-112`): one bad row, two failed checks.
- **S4 · minor · 2026-11-08** — open, no ticket. `docker/quality.Dockerfile:7` uses `python:3.12-slim`, while `docker/producer.Dockerfile:2` uses `python:3.11-slim`. The quality image runs as root.
- **S5 · minor · 2026-11-08** — open, no ticket. `scripts/quality.sh` has git mode `100755`; the other scripts are `100644` and run through `bash`.
- **S6 · minor · 2026-11-08** — open, no ticket. The MinIO client environment block appears three times (`compose.yaml:31-35`, `:188-192`, `:305-309`). An `x-` anchor would hold it once.
- **S7 · minor · 2026-11-08** — open, no ticket. The `LakeTableMissing` and `LakeColumnsMissing` branches are near-identical (`src/factorypulse/quality/__init__.py:75-78`). A shared base error in `src/factorypulse/lake.py` would make them one branch.
- **S9 · minor · 2026-11-08** — open, no ticket. `src/factorypulse/quality/expectations.py:180-184` builds the `<sensor>_avg` / `<sensor>_max` names by string formatting instead of reading `analytics.MACHINE_HOURLY_COLUMNS`. A rename still fails loudly at check time.
- **S10 · minor · 2026-11-08** — open, no ticket. The defaults of `QualityReport.details` and `QualityReport.checked` (`src/factorypulse/quality/__init__.py:41-42`) are used by no caller.
- **P2 · minor · 2026-11-08** — open, no ticket. The fact's row check has an upper bound only (`src/factorypulse/quality/expectations.py:124-129`), which "event_id is unique" and "every event_id is in raw_sensor_events" already imply. A fact that drops events passes, and so do the marts. A lower bound from the raw Delta version the dbt build read would close the gap.
- **P3 · minor · 2026-11-08** — open, no ticket. Checklist item 1 asks for "schema"; `src/factorypulse/lake.py:105-107` checks only that the declared columns exist. No check asserts column types.
- **P4 · minor · 2026-11-08** — open, no ticket. Missingness is zero-tolerance only. The marts' per-sensor statistics have no missingness check (`src/factorypulse/quality/expectations.py:189`), so a mart whose `temperature_avg` is null in every row passes.

## Coverage

Checklist item to test (`tests/test_data_quality.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. Raw lake: schema, ranges, missingness, allowed values | `test_known_bad_raw_row_fails_the_named_check[*]`, `test_empty_raw_lake_fails_the_row_count_check`, `test_table_without_a_declared_column_fails_a_named_check`; `tests/test_lake.py::test_built_table_missing_a_declared_column_raises_a_named_error` |
| 1. dbt tables: the same properties, and uniqueness and relationships that can fail | `test_known_bad_dbt_row_fails_the_named_check[*]` (20 cases over 4 tables) |
| 2. Report names the failed checks | `test_report_names_every_failed_check_in_definition_order`, `test_failed_value_check_quotes_the_offending_values`, `test_failed_table_level_check_quotes_the_observed_value`, `test_check_that_cannot_be_evaluated_fails_with_the_reason`, `test_cli_exits_nonzero_and_names_each_failed_check`, `test_cli_exits_zero_and_says_pass_when_every_check_passes` |
| 2. Runs in the pipeline | `test_stages_check_the_raw_lake_then_the_daily_models_then_the_weekly_mart`, `test_cli_without_a_selection_checks_every_stage_in_pipeline_order`, `test_quality_service_runs_the_cli_in_its_own_light_image`, `test_quality_driver_runs_one_stage_through_the_service`, `test_dbt_lake_build_is_followed_by_the_post_dbt_checks`, `test_lake_demo_checks_the_raw_lake_after_ingesting`; `tests/test_airflow_dag.py::test_the_raw_lake_is_checked_before_dbt_reads_it`, `::test_quality_steps_are_quality_stages` |
| 3. Known-bad data fails, good data passes | `test_good_raw_lake_passes_every_check`, `test_good_dbt_table_passes_every_check[4 tables]`, the two known-bad parametrizations |

Seams, rejection branches and error paths:

- Substitute runner without Great Expectations: `test_report_mapping_works_without_great_expectations_installed`, `test_report_passes_when_every_check_passes`, `test_run_all_reports_each_table_in_the_order_given`.
- No runner result counts as failed: `test_check_the_runner_returned_no_result_for_counts_as_failed`.
- Table or reference not built: `test_table_that_has_not_been_built_fails_a_named_check_without_running`, `test_dbt_table_whose_reference_is_not_built_fails_a_named_check`, `test_cli_fails_when_a_table_is_not_built`.
- Table with no checks: `test_table_with_no_checks_is_rejected`, `test_cli_rejects_a_table_with_no_checks`.
- No dedicated test, each sharing a tested path: the weekly mart losing a machine (same checks as the hourly case); a reference table built without a declared column (same branch as the tested case). A lake error other than "missing" propagates as a traceback with a non-zero exit, as ticket 12 decided.
