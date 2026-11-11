#!/usr/bin/env bash
# FactoryPulse dbt driver (ticket 05): the analytics layer over the raw lake.
#
#   ./scripts/dbt.sh build     build the dbt image (once; builds the Spark
#                              image too, since dbt shares that runtime)
#   ./scripts/dbt.sh debug     dbt debug against the lake target
#   ./scripts/dbt.sh run       dbt build --target lake  (models + dbt tests),
#                              then the quality checks of every model (ticket 07)
#   ./scripts/dbt.sh daily     the daily DAG's build: every model except the
#                              weekly grain (`tag:weekly`)
#   ./scripts/dbt.sh weekly    the weekly DAG's build: the weekly grain alone
#   ./scripts/dbt.sh fixture   dbt build --target fixture (offline: seeds, the
#                              models, and the hourly fixture assertion)
#   ./scripts/dbt.sh query     Spark SQL read of the three marts
#
# The lake target needs MinIO up (`docker compose up -d minio`); the fixture
# target needs nothing at all — it builds into container-local Delta paths, so
# the hourly aggregate is asserted with no network, no MinIO and no Kafka.
#
# No standalone `test`: the entrypoint runs each invocation from a fresh
# throwaway catalog (see scripts/dbt-entrypoint.sh), so `dbt test` alone finds
# no tables. `build` runs the models and their dbt tests together in one session.
set -euo pipefail
cd "$(dirname "$0")/.."

# JOBS and run_job: every one-off job runs through run_job.
source scripts/job.sh

# The dbt service is one-shot: DBT_ARGS is the command the entrypoint runs.
#
# DBT_ARGS is word-split by the dbt service's compose command, which passes
# `$$DBT_ARGS` unquoted to the entrypoint, so every argument must be a single
# shell word: the fixture vars are spelled as JSON rather than as YAML, because
# `{lake_root: /tmp/fp-fixture}` would split in two and dbt would reject
# `{lake_root:` as invalid YAML.
FIXTURE_VARS='--vars {"lake_root":"/tmp/fp-fixture"}'

dbt_run() {
  local args="$1"
  run_job dbt -e DBT_ARGS="$args"
}

build()   { docker compose "${JOBS[@]}" build dbt; }
debug()   { docker compose up -d minio; dbt_run "debug --target lake"; }
run()     { docker compose up -d minio; dbt_run "build --target lake"; bash scripts/quality.sh post-dbt; bash scripts/quality.sh weekly; }
# The scheduled builds (ticket 06). `cautious` keeps out a test that also
# references a model the run does not build: the weekly mart's relationships
# test reads dim_machine, which is absent from a weekly-only session catalog.
daily()   { docker compose up -d minio; dbt_run "build --target lake --exclude tag:weekly"; }
weekly()  { docker compose up -d minio; dbt_run "build --target lake --select tag:weekly --indirect-selection cautious"; }
fixture() { dbt_run "build --target fixture $FIXTURE_VARS"; }
query()   { docker compose up -d minio; run_job query-analytics; }

case "${1:-fixture}" in
  build)   build;;
  debug)   debug;;
  run)     run;;
  daily)   daily;;
  weekly)  weekly;;
  fixture) fixture;;
  query)   query;;
  *) echo "usage: $0 {build|debug|run|daily|weekly|fixture|query}"; exit 1;;
esac
