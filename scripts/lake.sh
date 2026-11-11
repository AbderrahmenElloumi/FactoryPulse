#!/usr/bin/env bash
# FactoryPulse lake driver (ticket 04): drives the tracer bullet end to end.
#
#   ./scripts/lake.sh build     build the producer + spark images (once)
#   ./scripts/lake.sh produce   publish N simulator events → Kafka + MinIO snapshot
#   ./scripts/lake.sh stream    run the structured-streaming ingester (Ctrl-C to stop)
#   ./scripts/lake.sh batch     batch-ingest the backfill snapshot into the lake
#   ./scripts/lake.sh query     Spark SQL read of the raw Delta lake
#   ./scripts/lake.sh anomaly   score the hourly mart into mrt_anomaly_scores
#                               (needs the dbt marts: ./scripts/dbt.sh run)
#   ./scripts/lake.sh demo      produce → stream → query → batch → query → stop → quality
#                               (the full loop, ending with the raw lake checks)
#   ./scripts/lake.sh all       the whole pipeline once: the platform, demo, the
#                               dbt models and their checks, the anomaly scores
set -euo pipefail
cd "$(dirname "$0")/.."

# JOBS and run_job: every one-off job runs through run_job.
source scripts/job.sh

build()    { docker compose "$@" build producer streamer batch-ingest query; }
produce()  { run_job producer -- "$@"; }
stream()   { docker compose up -d streamer && docker compose logs -f --no-log-prefix streamer; }
batch()    { run_job batch-ingest; }
query()    { run_job query; }
anomaly()  { docker compose up -d minio; run_job anomaly-detection; }
stop()     { docker compose stop streamer; }

demo() {
  echo "== produce ==";               produce
  echo "== stream (up) ==";           docker compose up -d streamer
  echo "   waiting for the streamer to drain the topic..."; sleep 25
  echo "== query ==";                 query
  echo "== batch ==";                 batch
  echo "== batch again (idempotency) =="; batch
  echo "== query ==";                 query
  echo "== stop ==";                  stop
  echo "== quality (raw lake) ==";    bash scripts/quality.sh ingestion
}

all() {
  echo "== platform ==";              docker compose up -d --build
  demo
  echo "== dbt ==";                   bash scripts/dbt.sh run
  echo "== anomaly ==";               anomaly
  echo "dashboard: http://localhost:8501"
}

case "${1:-demo}" in
  build)   shift; build "$@";;
  produce) shift; produce "$@";;
  stream)  stream;;
  batch)   batch;;
  query)   query;;
  anomaly) anomaly;;
  stop)    stop;;
  demo)    demo;;
  all)     all;;
  *) echo "usage: $0 {build|produce|stream|batch|query|anomaly|stop|demo|all}"; exit 1;;
esac