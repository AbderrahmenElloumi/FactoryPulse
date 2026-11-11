#!/usr/bin/env bash
# Dev helper: wipe the Delta lake + streaming checkpoints from MinIO so a
# tracer-bullet run starts clean. Objects only under the compose project's
# dev bucket; nothing outside it is touched.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T minio sh -c '
  mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1
  mc rm --force --recursive --yes local/factorypulse/delta/  >/dev/null 2>&1 || true
  mc rm --force --recursive --yes local/factorypulse/checkpoints/ >/dev/null 2>&1 || true
  echo "lake reset: delta/ and checkpoints/ removed from bucket factorypulse"
'