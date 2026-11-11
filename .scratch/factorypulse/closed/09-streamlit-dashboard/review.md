---
ticket: .scratch/factorypulse/closed/09-streamlit-dashboard/ticket.md
verdict: pass
---

# Review: ticket 09 — Streamlit dashboard

**Final verdict:** pass, on the re-review of `d5f6458` (range `05af0b8..d5f6458`).

**Standards:** no documented standard is broken. The S3 rename is fixed. Three `minor` findings stay open (S1, S2, and the glossary question in S3).

**Spec:** all three checklist items are met and each has a test. P1 is fixed: rows without a `z_score` no longer decide a machine's health status. Three `minor` findings stay open (P2 to P4).

Runs: host suite 393 passed, 32 skipped. Live: `docker compose up -d streamlit` ran the fixed `latest_machine_status`, and `/_stcore/health` answered `ok`. On the live lake, `machine_health_kpis` gave Machines 8, Nominal 6, Warning 1, Critical 1, Unscored 0. 192 of 342 score rows have a null `z_score`.

## Open findings

- **P2 · minor · 2026-11-10** — open, no ticket. The error path renders the page title next to the error. `st.title` (`src/factorypulse/dashboard.py:24`) runs before the reads (`:25-31`). The tests check one error, no chart and no table (`tests/test_streamlit_dashboard.py:299-302`), not the title. Move the title after the reads, or keep the ticket's wording "shows as one error naming it".
- **P3 · minor · 2026-11-10** — open, no ticket. `sensor_trend` returns `{sensor}_max` (`src/factorypulse/analytics.py:241`, `:248`), and nothing renders it: the dashboard plots `_avg` only (`src/factorypulse/dashboard.py:40`). Ticket: "The trends plot the hourly average". `tests/test_streamlit_dashboard.py:226` pins the extra column. Drop the column, or plot it.
- **P4 · minor · 2026-11-10** — open, no ticket. The `streamlit` service hard-codes the MinIO credentials (`compose.yaml:331-332`). `spec.md` Deployment: "MinIO credentials come from the environment, templated in `.env.example` and interpolated by compose." The other services do the same (`compose.yaml:34-35`, `:191-192`, `:308-309`). Triage decides.
- **S1 · minor · 2026-11-10** — open, no ticket. Possible Duplicated Code. `compose.yaml` holds four copies of the five-line `MINIO_*` environment block (`:32-36`, `:189-193`, `:306-310`, `:329-333`). An `x-minio-env` anchor at the compose root holds it once (`docs/agents/gotchas/docker.md`: anchors go at the root). The same edit resolves P4 if triage wants `${MINIO_ACCESS_KEY:-}` interpolation.
- **S2 · minor · 2026-11-10** — open, no ticket. Possible Duplicated Code. `_compose_service` (`tests/test_streamlit_dashboard.py:337-341`) copies `tests/test_data_quality.py:570`. Move one copy to `tests/conftest.py` and call it from both.
- **S3 · minor · 2026-11-10** — open, no ticket. "At-risk machine" is a term with no `CONTEXT.md` entry. Triage decides whether the glossary takes it (Writing rules: "use the `CONTEXT.md` glossary words").

## Coverage

Checklist item to test (`tests/test_streamlit_dashboard.py`):

| Checklist item | Tests |
| --- | --- |
| 1. Starting the app serves a dashboard that reads the lake | `test_app_shows_kpis_trends_and_at_risk_machines_from_the_lake` (AppTest over a fixture Delta lake); live run above |
| 2. KPIs, temperature/vibration trends, at-risk list from anomaly scores | `test_app_shows_kpis_trends_and_at_risk_machines_from_the_lake`, `test_latest_machine_status_takes_each_machines_latest_window`, `test_at_risk_machines_lists_non_nominal_latest_status_worst_first`, `test_machine_health_kpis_count_machines_by_latest_status`, `test_no_scores_means_no_machine_at_risk_and_every_machine_unscored`, `test_a_machine_with_no_scored_window_is_unscored_not_nominal`, `test_an_unscored_latest_window_keeps_the_last_scored_status`, `test_a_window_with_one_scored_sensor_is_a_scored_window`, `test_sensor_trend_is_one_hourly_series_per_machine_in_time_order` |
| 3. One command, no Spark process | `test_streamlit_service_serves_the_app_from_its_own_light_image`, `test_dashboard_image_is_python_with_pinned_readers_not_spark`, `test_dashboard_imports_no_spark`; live run above |
| Status vocabulary from the contract | `test_dashboard_spells_no_status_string` |

Rejection branches:

| Branch | Tests |
| --- | --- |
| Status outside `contract.STATUSES` | `test_a_status_outside_the_contract_vocabulary_is_rejected` |
| Sensor type outside the contract | `test_sensor_trend_rejects_a_sensor_type_outside_the_contract` |
| Table not built (each of the three) | `test_app_names_a_table_that_has_not_been_built_instead_of_an_empty_chart` |
| Built table lacks a declared column | `test_app_names_a_built_table_that_lacks_a_declared_column` |
| Machine with no scored window | `test_a_machine_with_no_scored_window_is_unscored_not_nominal` |
| Latest window has no score | `test_an_unscored_latest_window_keeps_the_last_scored_status` |
