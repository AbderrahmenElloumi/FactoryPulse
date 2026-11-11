# 13: dbt and test prefactoring

**What to build:** the small structural cleanups that the quality and dashboard tickets would otherwise each have to redo, landed first so those tickets can be about their own behaviour. Nothing here changes what the pipeline computes.

**Blocked by:** None (can start immediately).

Status: `closed`

- [x] The duplicated environment fixture in the Spark and dbt test modules lives in one shared place, so a third test module does not duplicate it a third time.
- [x] The eight repeated comparison blocks in the fixture-comparison test become one reusable macro, and the test still passes.
- [x] `unit` carries a not-null test, since it is the only event-contract field without one even though the ingestion boundary already rejects a null unit.
- [x] The disagreement between the columns the cleaned-readings model filters nulls on and the columns asserted not-null is resolved in one direction, with the chosen behaviour and its reason recorded in the model.

## Current state

Decisions later tickets depend on:

- The `env` fixture lives only in `tests/conftest.py`. A new test module uses it from there (`tests/test_suite_layout.py::test_pipeline_env_fixture_is_defined_once_in_conftest`).
- Both fixture assertions compare their float statistics through the `floats_match` macro. A one-sided null is a mismatch.
- Every event-contract column of `fct_sensor_readings_clean` carries a `not_null` test (`test_every_event_contract_column_of_the_clean_fact_asserts_not_null`).
- `fct_sensor_readings_clean` filters no column on null: a null is a tripwire, not dropped data. "Nothing here changes what the pipeline computes" holds only for contract-valid data. If a null reaches the raw lake, the fact's `not_null` test fails, and `dbt build --target lake` skips `dim_machine` and the marts, which keep their last built state until the row is fixed.

## Log

2026-10-13 · triage · 11bccc7 · created from the ticket 05 review items parked in ticket 07 · -
2026-11-07 · impl · 9aa7868 · all four items; host 170 passed, 2 skipped; dbt fixture PASS=51 · -
2026-11-07 · review · 22b6305 · block (major: the one-sided-null branch of `floats_match` untested) · .scratch/factorypulse/closed/13-dbt-and-test-prefactoring/review.md
2026-11-07 · fix · 06fbaca · fixed the major with a rendered-macro test on sqlite; recorded the tripwire's effect on the marts; host 176 passed, 2 skipped · .scratch/factorypulse/closed/13-dbt-and-test-prefactoring/review.md
2026-11-07 · rereview · 10d813f · pass; minors left open · .scratch/factorypulse/closed/13-dbt-and-test-prefactoring/review.md
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
