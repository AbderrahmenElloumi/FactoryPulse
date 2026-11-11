---
ticket: .scratch/factorypulse/closed/13-dbt-and-test-prefactoring/ticket.md
verdict: pass
---

# Review: ticket 13 — dbt and test prefactoring

**Final verdict:** pass, on the re-review of `06fbaca` (range `6a52dd1..06fbaca`, a test-only fix round). No file under `dbt/` changed since `9aa7868`, so the first review's dbt fixture build (PASS=51) still holds.

**Standards:** no hard violations. Judgement calls on test naming, duplicated rationale and narrow text locks stay open as `minor` (S1-S11).

**Spec:** all four checklist items hold. The `major` (untested one-sided-null branch of `floats_match`) is fixed, and a `spark-sql` run confirmed the sqlite stand-in gives the same rows as Spark. Two `minor` findings stay open (P1, P2).

## Open findings

- **S1 · minor · 2026-11-07** — open, no ticket. The `floats_match` parameters `actual`, `expected` and `tolerance` are never overridden (`dbt/macros/floats_match.sql:12`). Small surface; keeping them is acceptable.
- **S2 · minor · 2026-11-07** — open, no ticket. The same eight-column list is passed to `floats_match` in both fixture assertions (`dbt/tests/assert_mrt_machine_hourly_matches_expected_fixture.sql:77-82`, `assert_mrt_machine_weekly_matches_expected_fixture.sql:83-88`) and repeats `analytics.MACHINE_*_COLUMNS`. `test_fixture_assertions_compare_every_sensor_statistic_through_the_macro` keeps the copies in step.
- **S3 · minor · 2026-11-07** — open, no ticket. Sensor statistics are found by the suffixes `_avg` and `_max` (`tests/test_dbt_project.py:462`). A future `_min` or `_p95` column drops out of the lock silently. A named `SENSOR_STATISTIC_COLUMNS` in `analytics.py` would carry the concept.
- **S4 · minor · 2026-11-07** — open, no ticket. `test_clean_fact_filters_no_null_the_schema_asserts_against` is hard to parse, and its comment points at "the not_null tests above", which depends on test order (`tests/test_dbt_project.py:357-361`).
- **S5 · minor · 2026-11-07** — open, no ticket. That test's comment (`tests/test_dbt_project.py:358-363`) repeats the model comment (`dbt/models/marts/fct_sensor_readings_clean.sql:32-37`). Keep the reason in the model and point to it.
- **S6 · minor · 2026-11-07** — open, no ticket. The `tests/test_suite_layout.py` docstring states a general rule for shared fixtures (`:3-6`), but the lock checks only `^def env\(` in top-level test modules (`:14-20`). It misses `@pytest.fixture(name="env")` over another function name and a copy in a subdirectory. Narrow the docstring or broaden the check.
- **S7 · minor · 2026-11-07** — open, no ticket. `_declared_tests((MODEL_DIR / "schema.yml").read_text(...))` is repeated inline (`tests/test_dbt_project.py:329,337,347`). One helper would read the file once.
- **S8 · minor · 2026-11-07** — open, no ticket. The module docstring says text assertions on the SQL are deliberate (`tests/test_dbt_project.py:11-14`); the `floats_match` tests run rendered SQL. Name them as the exception.
- **S9 · minor · 2026-11-07** — open, no ticket. `jinja2` is imported at module level (`tests/test_dbt_project.py:24`) but declared nowhere: it arrives through `streamlit`, and the venv rebuild recipe in `docs/agents/gotchas/windows-host.md` does not list it. If it goes missing, every test in the module fails at collection. Add it to the recipe, or use `pytest.importorskip("jinja2")`.
- **S10 · minor · 2026-11-07** — open, no ticket. The reason "`where not (null)` drops the row" appears three times: `dbt/macros/floats_match.sql:7-9`, `tests/test_dbt_project.py:439-440` and `docs/agents/gotchas/dbt.md:23-25`.
- **S11 · minor · 2026-11-07** — open, no ticket. `_floats_match_reports` takes column names from `actual` and binds `expected` values by position (`tests/test_dbt_project.py:420-424`), and its regex requires the exact closer `{%- endmacro %}` (`:418`). Reordered keys bind the wrong values silently; a harmless edit to `{% endmacro %}` fails with "defines no floats_match macro".
- **P1 · minor · 2026-11-07** — open, no ticket. The null-filter lock matches only `(\w+)\s+is\s+not\s+null` on comment-stripped lines (`tests/test_dbt_project.py:364-366`). It misses `isnotnull(x)`, `not x is null` and `nvl` / `coalesce` filters, and `split("--")` cuts a `--` inside a string literal.
- **P2 · minor · 2026-11-07** — open, no ticket. The tolerance boundary is not pinned: the mutant `<=` to `<` survives every case (`dbt/macros/floats_match.sql:15`). Not a declared branch; real mart values almost never land on it.

## Coverage

Checklist item to test (`tests/test_dbt_project.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. `env` defined once | `tests/test_suite_layout.py::test_pipeline_env_fixture_is_defined_once_in_conftest` (narrow, S6) |
| 2. One macro, fixture test still passes | `test_fixture_assertions_compare_every_sensor_statistic_through_the_macro`; dbt `assert_mrt_machine_hourly_matches_expected_fixture` and `assert_mrt_machine_weekly_matches_expected_fixture` (fixture build PASS=51) |
| 3. `unit` not-null | `test_every_event_contract_column_of_the_clean_fact_asserts_not_null`; dbt `not_null_fct_sensor_readings_clean_unit` |
| 4. Null filter and not-null assertions agree, reason in the model | `test_clean_fact_filters_no_null_the_schema_asserts_against` (narrow, P1); comment in `fct_sensor_readings_clean.sql` |

Macro branches:

- Values within tolerance match: `test_floats_match_reports_drift_and_one_sided_null[1.0-1.0-False]`, `[1.0-1.00005-False]`.
- Both null match: `[None-None-False]`.
- Drift beyond tolerance is reported: `[1.0-1.001-True]`.
- A one-sided null is reported: `[None-1.0-True]`, `[1.0-None-True]`. The `coalesce` to `or` mutant fails these.
- Every column must match: `test_floats_match_requires_every_column_to_match`.

Host suite at `06fbaca`: 176 passed, 2 skipped.
