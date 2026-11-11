---
ticket: .scratch/factorypulse/closed/10-documentation-repo/ticket.md
verdict: pass
---

# Review: ticket 10 — Documentation & repository

**Final verdict:** pass, on the re-review of `13c7fa5` (range `537209f..13c7fa5`).

**Standards:** no documented standard is broken. Two `minor` findings stay open (S1, S2). The close rewrites the ticket's quality-claim bullet as a decision, so it no longer restates the test and the README. This ticket fixes closed review 09 P4 (hard-coded `streamlit` credentials); triage drops it. Closed review 09 S1 (the `MINIO_*` block repeated in five services) still applies.

**Spec:** all four checklist items are met. P1 is fixed: the README says Great Expectations checks the raw lake and the dbt models (`README.md:7-8`, `:175`), which matches `CHECKED_TABLES` (`src/factorypulse/quality/expectations.py:212`). P2 is fixed: `test_the_quickstart_runs_every_stage_in_order` compares the commands of `all()` to the exact stage list. Four `minor` findings stay open (P3 to P6).

Runs: host suite 413 passed, 33 skipped. Mutations, reverted after the run: "every table" put back in the README fails `test_docs_claim_checks_on_every_table_only_when_every_table_has_them`; the `anomaly` call removed from `scripts/lake.sh` fails `test_the_quickstart_runs_every_stage_in_order`. `bash scripts/lake.sh all` was not rerun.

## Open findings

- **P3 · minor · 2026-11-11** — open, no ticket. The quickstart is two commands: `cp .env.example .env`, then `bash scripts/lake.sh all` (`README.md:70`, `:76`). Ticket: "a setup guide (single command to run everything)". Without `.env`, MinIO refuses to start and `docker compose up -d --build` (`scripts/lake.sh:42`) fails; the variable names show in the `minio` log, not in the output of `lake.sh`. Triage decides whether `all` creates `.env` from `.env.example` when `.env` is absent.
- **P4 · minor · 2026-11-11** — open, no ticket. The README states the release process in the present tense: "Releases reach a separate public repository", "Issues and pull requests arrive on the public repository" (`README.md:183-186`). The release pipeline and the inbound channel are repo-release tickets 01 and 02, both `ready-for-agent`. `.scratch/repo-release/spec.md` story 11: "describe what is built rather than what is intended". Fix: "Releases will reach …", or state that the release process is specified, not built.
- **P5 · minor · 2026-11-11** — open, no ticket. Two README tests check only a marker: `test_readme_has_an_architecture_diagram` checks for a ` ```mermaid ` fence (`tests/test_documentation.py:52-53`), `test_readme_has_a_tech_stack_rationale` checks for the heading (`:76-77`). An empty diagram or an empty section passes. Fix: assert the diagram names each stage, and the rationale table has a row per technology.
- **P6 · minor · 2026-11-11** — open, no ticket. `test_docs_claim_checks_on_every_table_only_when_every_table_has_them` matches one phrase, `\bevery\s+table\b` (`tests/test_documentation.py:123`). "every lake table", "all tables" and "each table" pass it while `mrt_anomaly_scores` has no check. Story 11 as in P4. Fix: match `\b(every|each|all)\s+(\w+\s+)?tables?\b`, or rename the test to the phrase it guards.
- **S1 · minor · 2026-11-11** — open, no ticket. Possible Mysterious Name. `test_no_secret_value_is_embedded_outside_env_example` scans three hand-picked files (`tests/test_documentation.py:147-154`), not the repository. A dev secret added to `spark/`, `dags/` or another script passes. Fix: scan `git ls-files` with `tests/` excluded (`factorypulse-dev-pass` sits in `tests/conftest.py:12`, `tests/test_lake.py:107`, `:131`, `tests/test_spark_common.py:60`), or rename the test to what it checks.
- **S2 · minor · 2026-11-11** — open, no ticket. Possible Duplicated Code. `{analytics.RAW_EVENTS_TABLE, *analytics.REGISTERED_TABLES}` (`tests/test_documentation.py:121`) redefines "every lake table"; the test above uses `set(analytics.TABLE_COLUMNS)` for the same set (`:116`). Fix: use one source in both tests.

## Coverage

Checklist item to test (`tests/test_documentation.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. Hosted on GitHub, private | no test (external state); `gh repo view` reported `FactoryPulse-prv` as `PRIVATE` on the first review |
| 2. README: architecture diagram | `test_readme_has_an_architecture_diagram` (marker only, P5) |
| 2. README: single-command setup guide | `test_readme_has_a_single_command_quickstart`, `test_the_quickstart_runs_every_stage_in_order`, `test_readme_has_virtualenv_and_pytest_instructions` |
| 2. README: tech-stack rationale | `test_readme_has_a_tech_stack_rationale` (heading only, P5) |
| 3. Going public | `test_readme_points_at_the_release_process` |
| 4. Credentials excluded | `test_compose_reads_every_credential_from_the_environment`, `test_no_secret_value_is_embedded_outside_env_example` (three files, S1), `test_env_example_declares_every_variable_compose_interpolates`, `test_env_example_gives_every_credential_a_value` |
| 4. Generated data and local state excluded | `test_gitignore_excludes_local_state_and_generated_data`, `test_no_credential_generated_data_or_local_environment_is_tracked` |
| 4. Cloud usage excluded | no test; no cloud endpoint or SDK in `compose.yaml`, `docker/` or the requirements (the AWS SDK jar serves S3a to MinIO) |
| Docs name only real paths, tables and checks | `test_docs_carry_no_placeholder_tokens`, `test_every_path_the_docs_name_exists`, `test_every_lake_table_the_docs_name_is_registered`, `test_docs_claim_checks_on_every_table_only_when_every_table_has_them` (one phrase, P6), `test_docs_do_not_name_the_rejected_rolling_window_mart` |
| PR template name | `test_pull_request_template_uses_the_name_github_detects` |

Rejection branches:

| Branch | Tests |
| --- | --- |
| MinIO with empty credentials | `test_minio_refuses_to_start_without_credentials` (`FACTORYPULSE_DOCKER_TESTS=1`) |
| DAG file with unset or empty JWT secret | `tests/test_airflow_dag.py::test_the_dag_file_refuses_to_load_without_the_jwt_secret` |
| DAG file with unset or empty host directory | `tests/test_airflow_dag.py::test_the_dag_file_refuses_to_load_without_the_host_dir` |
| `scripts/lake.sh` with no `all()` | `test_the_quickstart_runs_every_stage_in_order` (assertion names the missing function) |
