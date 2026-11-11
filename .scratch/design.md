# FactoryPulse module design

> Working material from `codebase-design`, 2026-10-13. Its decisions now live
> in the specs and tickets. Not maintained.

Working material feeding `/to-spec` and `/to-tickets`. This document decides
module shapes, seams, and test surfaces; the specs decide behaviour, and the
tickets decide what gets built when. It is not the shipped architecture guide —
`docs/architecture-guide.md` is, and ticket 10 rewrites that from the code.

Vocabulary used strictly here: a **module** is anything with an interface and an
implementation; the **interface** is everything a caller must know, including
invariants and error modes; a **seam** is where an interface lives; an
**adapter** is something that satisfies an interface; **depth** is leverage at
the interface.

## 1. Seams at a glance

| Seam | Interface | Adapters behind it | Consumers |
| --- | --- | --- | --- |
| Event contract (row level) | `validator.validate_event(event) -> list[str]` | Python validator; JSON Schema mirror for Spark/dbt | streaming, batch, simulator, tests |
| Quality (table level) | `quality.check_table(name) -> QualityReport` | Great Expectations runner | DAG task, CLI, tests |
| Lake read (non-Spark) | `lake.read_table(name, root=None) -> DataFrame` | `deltalake` over MinIO; a local Delta directory | dashboard, quality, tests |
| Analytics registry | `analytics.analytics_path(env, model)`, table-name constants | the dbt models and `mrt_anomaly_scores` | spark jobs, dbt (via vars), tests, dashboard |
| Idempotent write | `spark.common.merge_into_delta(spark, df, path, keys)` | Delta `MERGE` | raw ingest, anomaly write |
| Release | `scripts/release.sh <version>` | `git commit-tree` plumbing | the maintainer |
| Scheduling | DAG tasks running `scripts/*.sh`, which call `docker compose run` | the compose services | Airflow |

Two seams deliberately stay separate: row-level contract validation runs
in-flight inside Spark on every event, while table-level expectations run in
batch and produce a named report. They differ in granularity, so they do not
share an interface. Unifying them would be an abstraction with one adapter.

## 2. Modules

### `contract.py` — vocabulary authority

Owns `EVENT_FIELDS`, `SENSOR_TYPES`, `SENSOR_UNITS`, `SENSOR_RANGES`,
`ALLOWED_UNITS`, `STATUSES`. It is the sole source of the status vocabulary:
`anomaly_core`, the quality expectations and the dashboard import `STATUSES`
rather than spelling the three strings.

### `validator.py` — row-level seam

`validate_event(event) -> list[str]`, empty list meaning valid, never raising on
malformed input. It returns results instead of raising, so callers decide
whether to route or fail.

### `analytics.py` — the analytics-layer registry

The one place that names every table and builds every lake path, so nothing
else invents a table name. `tests/test_dbt_project.py` locks it against the dbt
models. Each table has a column tuple in `TABLE_COLUMNS`, so the dashboard and
quality checks can assert they received the columns they expect.

### `lake.py` — the lake read seam

Interface:

- `read_table(name: str, root: Optional[str] = None) -> pandas.DataFrame`
- `storage_options() -> dict[str, str]`

Behind it: reading MinIO credentials and endpoint from the environment,
normalising the endpoint (the container sees `minio:9000`, the host sees
`localhost:9000`), choosing the `s3a`/`s3` scheme, reading the Delta log through
`deltalake`, and returning columns in the order `analytics.py` declares.

Error modes are part of the interface and are the reason this module exists:
a missing table raises `LakeTableMissing`, and a built table without a declared
column raises `LakeColumnsMissing`. The dashboard then renders "this table has
not been built yet" instead of an empty chart, and a quality check fails with a
reason instead of passing vacuously. There is no `table_exists`:
`LakeTableMissing` answers the same question.

Ticket 09 moves the dashboard onto this module. Today
`dashboard.delta_table_exists` returns `True` unconditionally and
`read_delta_table` swallows every exception into an empty frame.

Deliberate detail: the `deltalake` import stays **inside** the functions. The
Spark image runs Python 3.8 and exposes no `deltalake`; a module-level import
would break anything that touches this file in that container.

Deletion test: remove it and the endpoint, credentials, and existence logic
reappear in the dashboard and again in the quality runner, with a third
divergent answer about what a missing table means.

There is no `settings.py`. A module holding only configuration values is
shallow — its interface is as complex as its implementation. Folding those
values into the module whose behaviour needs them gives the same single owner
of credentials with a smaller surface.

### `quality/` — the table-level quality seam

Interface:

- `check_table(name: str) -> QualityReport`
- `run_all(tables: Sequence[str]) -> list[QualityReport]`

Both take an optional lake `root` and an optional `runner`. `QualityReport`
carries `table`, `failed: tuple[str, ...]` (each a named, human-readable
check), the evidence per failed check, and a `passed` property. Behind the
interface: building the Great Expectations 1.x context, wiring a pandas
datasource over the Delta read from `lake.py`, the per-table expectation
definitions, and mapping GE's result object into that report.

Internal seams: `quality/expectations.py` holds the definitions,
`quality/ge_runner.py` holds the Great Expectations adapter. Tests drive
`check_table` against a fixture Delta table, and substitute a fake runner to
test the report mapping without Great Expectations installed.

Expectation coverage: `raw_sensor_events` gets declared columns, row count,
not-null on every contract field, allowed sensor types, units and statuses,
unit-to-sensor agreement, range checks, and one site per machine; the mart
checks assert the properties dbt cannot guarantee by construction (the dbt
`unique` and `relationships` tests are tautological — they assert what
`group by` already produced).

CLI: `python -m factorypulse.quality --stage <stage>` or `--tables ...` prints
the report and exits non-zero on any failure, so the DAG task and a human use
the same path.

### `anomaly_core.py` — pure scoring

Interface:

- `Z_WARNING`, `Z_CRITICAL` module constants
- `z_score(value, mean, stddev, baseline_count) -> Optional[float]`
- `classify(z) -> str` returning a `contract.STATUSES` member
- `machine_status(sensor_statuses: Iterable[str]) -> str` — severity rollup

The rollup belongs in the pure module, where it is testable, with the rule
"worst sensor wins" stated once. This module holds the thresholds; the Spark job
imports them and spells none.

### `spark/anomaly_detection.py` — the scoring job (thin)

`compute_anomaly_scores(hourly_df)` returns a DataFrame; `main()` writes it to
`mrt_anomaly_scores` through `merge_into_delta` keyed on
`(machine_id, window_start, sensor_type)`.

The windowing, the sensor filter and the machine rollup column live here; no
threshold or status string is spelled out in this file. The windowing
parameters are split by owner. `SCORED_SENSORS`, `BASELINE_HOURS` and
`MIN_BASELINE_WINDOWS` are part of the scoring rule, so they live in
`anomaly_core`. `WINDOW_SECONDS`, the length of a scored window, stays in the
job.

### `spark/common.py` — the idempotent write seam

`merge_into_delta(spark, source_df, path, keys)` is the one write path for raw
ingest and the anomaly write. It puts the "re-running must not duplicate"
guarantee in one place. A frame missing a key column raises `MergeKeyError`
rather than producing a silently wrong merge.

### `dashboard.py` — the Streamlit adapter (split)

Rendering only: it calls `lake.read_table`, then pure functions in
`analytics.py` (`machine_kpis`, `hourly_trend`, `at_risk_machines`), then draws
with Plotly. Charts per the spec's Dashboard decision. `delta_table_exists` and
`read_delta_table` are deleted in favour of `lake.py`.

The computations move to `analytics.py` so they are testable without Streamlit
and without a lake: fixture frames in, frames out.

### `dags/factorypulse_dag.py` — scheduling only

Two DAGs: daily (batch ingest, dbt run, quality checks) and weekly (weekly mart
plus quality checks). Tasks are `BashOperator`s running `scripts/lake.sh`,
`scripts/dbt.sh` and `scripts/quality.sh`, which call
`docker compose run --rm <service>` through the mounted socket.

Design constraint worth stating: **the DAG owns no logic the command line
lacks.** Every task is a script a human can run by hand, because a DAG that
hides logic makes the pipeline undebuggable and untestable outside Airflow. The
DAG contributes scheduling, dependency edges, retries, and failure visibility —
nothing else.

### `mrt_machine_weekly` (dbt model)

`mrt_machine_weekly`: machine × ISO week, rolled up from the hourly mart. This
is what "weekly aggregation" means; a weekly DAG re-running the hourly mart
would advance nothing.

It pins `location_root` like every model, and it has entries in `analytics.py`
and in the fixture-locked test.

### `scripts/release.sh` — the release seam (new)

Interface: `scripts/release.sh <version>`. Behind it: preflight (clean tree, on
`main`, tests green, `pyproject.toml` version equals the argument, CHANGELOG has
that heading), building the next public commit with `git commit-tree` from
`main`'s tree with the public tip as parent, tagging, pushing to `public main`.
Any failed preflight exits with a named reason and no side effects.

## 3. Artifacts

- Files: `src/factorypulse/lake.py`, `src/factorypulse/quality/`,
  `scripts/release.sh`, `tests/conftest.py`, `dbt/macros/floats_match.sql`,
  `dbt/models/marts/mrt_machine_weekly.sql`.
- Compose services: `airflow-init`, `airflow-webserver`, `airflow-scheduler`,
  `airflow-dag-processor`, `anomaly-detection`, `quality`, `streamlit`.
- Images: `docker/airflow.Dockerfile` (Airflow plus the compose CLI),
  `docker/quality.Dockerfile` (Python 3.12, `great_expectations`,
  `deltalake`).
- Environment: MinIO credentials templated into `.env.example` and referenced as
  `${...}` from compose; one `MINIO_ENDPOINT` knob, set per service, with a
  `localhost` default for host runs. `.env` stays gitignored.

## 4. Corrections left

All in `dashboard.py`, owned by ticket 09:

- `delta_table_exists` and `read_delta_table` — replaced by `lake.py`; both lie
  in opposite directions.
- Unused imports `DeltaTable` and `Optional`.
- It reads `mrt_machine_anomaly_scores`; the table is `mrt_anomaly_scores`.

## 5. Ticket mapping

- **06 Airflow orchestration:** DAGs, compose Airflow services, Airflow image,
  DAG parse tests.
- **07 Data quality:** `quality/` package, quality image and service.
- **08 Anomaly detection:** `anomaly_core` changes, the scoring job writing
  `mrt_anomaly_scores`, seeded labelled fixtures asserting low scores for
  normal machines and high for injected anomalies.
- **09 Dashboard:** dashboard split into rendering plus `analytics.py`
  computations, Plotly charts, the Streamlit compose service.
- **10 Documentation:** `docs/architecture-guide.md` rewritten from the code,
  `CONTEXT.md` re-audited, CHANGELOG and README aligned to reality.
- **11 Weekly mart and idempotent write:** `merge_into_delta`,
  `mrt_machine_weekly`, its `analytics.py` entries, idempotency tests.
- **12 Lake read module:** `lake.py`.
- **13 dbt and test prefactoring:** `tests/conftest.py`, the `floats_match`
  macro, the `unit` not-null test.
- **14 Anomaly nits sweep:** the deferred minor findings of the ticket 08
  review.
- **repo-release/01:** `scripts/release.sh`, public repo creation, remotes,
  labels, the contribution-import flow, and the public README pass.

## 6. Test surfaces

Each module is tested through its own interface:

- `lake.py` — a fixture Delta table written to a local path; `read_table`
  returns declared columns, `read_table` on a missing name raises
  `LakeTableMissing`. The local path is the second adapter, which is what makes
  the seam real rather than hypothetical.
- `analytics.py` — the dbt-lock test, covering every mart.
- `anomaly_core.py` — pure functions, seeded fixtures, threshold boundaries at
  exactly 2.0 and 3.0.
- `quality/check_table` — a fixture table with one known-bad row fails with a
  named check; a clean table passes; report mapping tested against a fake
  runner.
- `spark/anomaly_detection.py` — asserted through the table it writes, not
  through its internals.
- DAGs — parse cleanly and expose the expected task graph.
- `release.sh` — a dry-run mode that builds the commit and reports it without
  pushing, so the plumbing is testable.
