# 06: Airflow orchestration & idempotent batch seam

**What to build:** scheduled automation — Airflow DAGs that run the daily batch/backfill job and the weekly aggregation on their own with idempotent Delta Lake MERGE semantics and surrogate key uniqueness enforcement, with failures visible and retriable.

**Blocked by:** 11 Weekly mart and the idempotent write seam.

Status: `closed`

- [x] Airflow DAGs schedule the daily batch/backfill job and the weekly aggregation automatically.
- [x] A DAG run completes end to end and moves the pipeline forward using idempotent Delta Lake MERGE statements.
- [x] Failures are visible in the Airflow UI, and a failed task can be rerun safely without duplicating lake records.

## Implementation Decisions

Absorbed from the former ticket 12, which described the same unit of work and has
been removed rather than left as a second file claiming it.

- **Orchestration tooling:** Airflow with LocalExecutor in Docker over a SQLite
  metadata database, matching the zero-budget local constraint.
- **Airflow is a pure orchestrator.** It holds no compute. Tasks are
  `BashOperator`s that invoke `docker compose run --rm <service>` for the Spark
  batch job, the dbt run, and the quality checks. This re-uses the compose
  services that already exist and are already idempotent, instead of duplicating
  their dependencies inside the Airflow image.
- **The DAG owns no logic the command line lacks.** Every task must be
  reproducible by hand through the existing scripts, because a DAG that hides
  logic makes the pipeline undebuggable outside Airflow. The DAG contributes
  scheduling, dependency edges, retries, and failure visibility.
- **Idempotency seam:** the write path merges rather than appends, through one
  shared Delta MERGE helper used by both raw ingestion and the anomaly write.
  dbt marts use deterministic surrogate keys such as `machine_hour_key`, so a
  re-run overwrites the same rows.
- **"Weekly aggregation" means a weekly mart.** It is a real second grain
  (`mrt_machine_weekly`, per machine per ISO week, rolled up from the hourly
  mart), not a weekly re-run of the hourly mart, which would advance nothing.
- **Weekly runs also re-check quality**, so a bad week fails visibly rather than
  silently producing an empty mart.

## Testing Decisions

- **Test philosophy:** validate external, observable behaviour at stage
  boundaries, never internal structure.
- **DAG parsing tests:** assert both DAGs import and parse without error and
  expose the expected task graph and dependencies.
- **Idempotency tests:** running batch ingestion and the dbt models twice over
  the same range produces zero duplicate records — asserted by row counts and by
  the surrogate key's uniqueness, not by inspecting the merge statement.
- **Prior art:** `tests/test_airflow_dag.py` (DAG parsing),
  `tests/test_spark_common.py` (the merge path).

## Current state

Decisions later tickets depend on:

- `dags/factorypulse_dag.py` holds two DAGs. `factorypulse_daily` runs `@daily`: batch ingestion, the raw-lake checks, the daily dbt build, the daily model checks. `factorypulse_weekly` runs on Monday at 02:00 UTC: the weekly mart, then its checks. Both have 2 retries 5 minutes apart, one active run at a time, no catchup, and start unpaused.
- Every task is a `BashOperator` that runs one driver step (`scripts/lake.sh`, `scripts/dbt.sh` or `scripts/quality.sh`) from the repository root. The root is `FACTORYPULSE_HOST_DIR`, the path the Docker daemon knows the repository by, set in `.env`. The DAG file refuses to load without it.
- Every driver step starts its one-off container through `run_job` in `scripts/job.sh`. `run_job` keeps one writer per compose service, labels the container with its owner and its run, and refuses to start a job once the Airflow scheduler is stopping. A new job service goes through `run_job` too.
- The scheduler runs through `scripts/scheduler.sh`. When the scheduler stops or exits, the script removes the job containers its tasks started.
- The Airflow services are in the compose profile `airflow` and share the image `docker/airflow.Dockerfile`: `airflow-init`, `airflow-webserver`, `airflow-scheduler` and `airflow-dag-processor`. The spec names only the webserver and the scheduler; Airflow 3 needs the other two. `airflow-webserver` runs Airflow 3's `api-server`, with the UI on `127.0.0.1:8080` and no login. The executor is LocalExecutor over SQLite in the `airflow-data` volume, with `PARALLELISM=1`.
- The weekly grain is the dbt models tagged `weekly` (`analytics.WEEKLY_MODELS`; every other model is in `analytics.DAILY_MODELS`). The daily build excludes the tag. The weekly build selects it alone, with `--indirect-selection cautious`. The weekly mart reads the hourly mart from its lake path, not through `ref()`.
- A quality stage holds only tables built together: `ingestion` is the raw lake, `post-dbt` the daily models, `weekly` the weekly mart. `scripts/dbt.sh run`, the full manual build, checks both dbt stages.
- Raw ingestion is at least once: the stream appends, and the fact deduplicates. `tests/test_pipeline_idempotency.py` therefore asserts that a rerun adds no row and no copy of any key, and that the dbt surrogate keys stay unique. Whether the spec accepts this is review finding T-5.
- Three test groups do not run in the default host suite. `tests/test_pipeline_idempotency.py` needs the running Airflow stack (`FACTORYPULSE_STACK_TESTS=1`). `tests/test_scheduler_stop.py` starts a throwaway Airflow (`FACTORYPULSE_DOCKER_TESTS=1`). The `DagBag` tests run only where Airflow is installed, in the Airflow image.

## Log

2026-09-10 · triage · 623463b · created · -
2026-10-05 · triage · c27a32c · contract asks for idempotent MERGE semantics · -
2026-10-06 · impl · 50e0d50 · stub DAG; boxes ticked · -
2026-10-11 · triage · 62c8e76 · closed · -
2026-10-13 · triage · da3af0b · reopened: print-stub tasks, no weekly DAG, no Airflow service; absorbs the former ticket 12 · -
2026-10-13 · triage · 11bccc7 · blocked by 11 · -
2026-11-08 · impl · 6a867be · daily and weekly DAGs, Airflow services; closes the review 07 project-directory hand-off; host 278 passed, 4 skipped · -
2026-11-08 · review · 5ae7dae · block (P-1) · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-08 · fix · 00f94f0 · fixed P-1 for reruns, and the first review's minor findings; host 313 passed, 4 skipped · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-08 · rereview · fc7e5d6 · block (R-1) · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-08 · fix · e164501 · fixed R-1, R-2, R-3, R-4, S-1 to S-5; host 325 passed, 5 skipped · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-08 · rereview · c811de7 · block (T-1) · fixed R-2, R-3, R-4, S-1 to S-5; R-1 fixed for a running job only · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-08 · fix · a189e48 · fixed T-1 to T-4, U-1 to U-5; host 337 passed, 6 skipped · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-08 · rereview · e070dd0 · pass · fixed R-1, T-1 to T-4, U-1 to U-5 · T-5 for triage · P-2 to P-5, V-1 to V-8, W-1 to W-3 and three unnumbered minors open, no ticket · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md; V-3 fixed by the gotcha split (f6a800c); the unnumbered minors are S-6 to S-8 · .scratch/factorypulse/closed/06-airflow-orchestration/review.md
