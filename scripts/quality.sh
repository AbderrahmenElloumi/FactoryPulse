#!/usr/bin/env bash
# FactoryPulse quality gate driver (ticket 07): Great Expectations checks over
# the lake, printed as a report naming every failed check.
#
#   ./scripts/quality.sh build       build the quality image (once)
#   ./scripts/quality.sh ingestion   check the raw lake (after ingestion)
#   ./scripts/quality.sh post-dbt    check the daily dbt models (after the dbt build)
#   ./scripts/quality.sh weekly      check the weekly mart (after the weekly build)
#   ./scripts/quality.sh all         check every table
#
# Exits non-zero when any check fails, so a driver that calls it stops there.
# Needs MinIO up (`docker compose up -d minio`).
set -euo pipefail
cd "$(dirname "$0")/.."

# JOBS and run_job: every one-off job runs through run_job.
source scripts/job.sh

check() { docker compose up -d minio; run_job quality -- "$@"; }

case "${1:-all}" in
  build)     docker compose "${JOBS[@]}" build quality;;
  ingestion) check --stage ingestion;;
  post-dbt)  check --stage post-dbt;;
  weekly)    check --stage weekly;;
  all)       check;;
  *) echo "usage: $0 {build|ingestion|post-dbt|weekly|all}"; exit 1;;
esac
