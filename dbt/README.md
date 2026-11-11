# FactoryPulse dbt project (ticket 05)

The analytics layer over the raw Delta lake. Four models, all plain SQL,
all materialized as Delta tables at explicit lake locations so any stage can
read them exactly like the raw lake.

| Model | Grain | Written to |
| --- | --- | --- |
| `dim_machine` | one row per machine | `s3a://factorypulse/delta/dim_machine` |
| `fct_sensor_readings_clean` | one row per event (deduplicated, typed) | `s3a://factorypulse/delta/fct_sensor_readings_clean` |
| `mrt_machine_hourly` | one row per machine per UTC hour | `s3a://factorypulse/delta/mrt_machine_hourly` |
| `mrt_machine_weekly` | one row per machine per ISO week | `s3a://factorypulse/delta/mrt_machine_weekly` |

`fct_sensor_readings_clean` is the only model that reads the raw lake
(`raw_sensor_events`); the other three read it.

## Running it

Use the driver script from the repo root — it builds the dbt image, brings up
MinIO when the run needs it, and passes the dbt command through.

```bash
./scripts/dbt.sh build      # build the dbt image (once)
./scripts/dbt.sh run        # dbt build --target lake  (models + dbt tests)
./scripts/dbt.sh daily      # the daily DAG's build: every model but tag:weekly
./scripts/dbt.sh weekly     # the weekly DAG's build: the tag:weekly models alone
./scripts/dbt.sh fixture    # offline: seeds + models + the fixture assertions
./scripts/dbt.sh query      # Spark SQL read of the marts
```

There is no standalone `test` command. Each invocation runs from a fresh
throwaway catalog (see `scripts/dbt-entrypoint.sh`), so `dbt test` on its own
finds no tables; `build` runs the models and their dbt tests in one session.

## Two targets

- **`lake`** builds the marts over the real raw events on MinIO. dbt's
  session catalog is throwaway bookkeeping; the durable output is the Delta
  directory each model pins with `location_root`, which is what the rest of
  the pipeline reads.
- **`fixture`** builds the same models over `seeds/raw_sensor_events_fixture.csv`
  with container-local Delta locations. It needs no MinIO, no Kafka and no
  network, and it is where the hourly and weekly aggregates are asserted against
  hand-computed numbers (`tests/assert_mrt_machine_*_matches_expected_fixture.sql`).

The fixture seed is contract-conforming: every row is validated with the same
`factorypulse.validator` the ingestion boundary uses, so the fixture cannot
drift from the event contract. It deliberately repeats one `event_id` to
exercise the deduplication in `fct_sensor_readings_clean`.

## Project conventions worth knowing

- Models carry `location_root=lake_root`, and dbt-spark appends the model
  identifier, so each table lands at `<lake_root>/<model>`. The schemas are
  created by a project-level `+pre-hook` (`create database if not exists
  {{ target.schema }}`) — dbt-spark never creates them, and Delta refuses an
  explicit `LOCATION` while the database is unknown.
- The run is hermetic: `scripts/dbt-entrypoint.sh` copies the project to
  `/tmp/dbt-project` inside the container before running dbt. dbt-spark's
  session method enables Hive, and Derby writes its metastore into the current
  directory — running in the bind-mounted project would persist a session
  catalog into the repo and make each run depend on the last one. Compiled SQL
  and the dbt log are symlinked back to `dbt/target/` and `dbt/logs/` for
  inspection.
- `dbt-core==1.8.7` and `dbt-spark==1.8.0` are pinned in the image (the newest
  pair with Python 3.8 wheels, which the Spark image runs).

## How the models reach Spark

dbt-spark runs with `method: session` inside the same image as the Spark jobs.
Two pieces of wiring live outside the dbt profile, because the adapter cannot
express them (see `scripts/dbt-entrypoint.sh`):

1. Connector jars arrive on `PYSPARK_SUBMIT_ARGS` — every in-process PySpark
   driver in this repo ignores `spark.jars.packages`.
2. Spark configuration is rendered to `$SPARK_CONF_DIR/spark-defaults.conf`
   from `spark/common.py::spark_conf`, the same dict the streaming and batch
   jobs use, so the analytics layer cannot drift from the ingestion layer's
   Delta/S3a/timezone settings.

Model names and lake paths also live in `src/factorypulse/analytics.py`;
`tests/test_dbt_project.py` locks that view and this project together on the
host (no JVM required).
