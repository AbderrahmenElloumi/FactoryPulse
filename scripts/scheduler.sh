#!/usr/bin/env bash
# FactoryPulse Airflow scheduler (ticket 06): `airflow scheduler`, plus the
# removal of the job containers its tasks started once it stops.
#
# On SIGTERM (`docker compose stop`), Airflow's LocalExecutor waits for the
# running tasks and never calls BashOperator.on_kill. Each task's bash runs
# in a session of its own, so the signal never reaches it, and its job
# container would keep running on the host. So on SIGTERM or SIGINT this
# script:
#
#   1. creates the stop flag, so that a task that reaches run_job from now on
#      fails without starting its job container,
#   2. sends SIGTERM to the scheduler, which stops scheduling and waits, and
#   3. until the scheduler has exited, removes every job container labelled
#      `factorypulse.job.owner=airflow`, every few seconds. A task can be
#      between the flag check and `docker compose run` when the stop
#      arrives, so its container can appear after the first removal.
#
# Each task's `docker compose run` then exits non-zero, its step fails, and
# the scheduler exits once the tasks have reported it. The task is retried on
# the next start. When the scheduler exits on its own, its tasks end with the
# container, so their job containers are removed as well.
#
# The scheduler runs in a process group of its own (`set -m`): dumb-init
# signals this script's group, and the scheduler hears the stop from here.
set -uo pipefail

# Every task inherits the owner, and run_job labels its container with it.
export FACTORYPULSE_JOB_OWNER=airflow
# Every task inherits the stop flag's path, and run_job checks it. A new
# directory per start, so that no flag from an earlier stop is left over.
FACTORYPULSE_JOB_STOP_FLAG="$(mktemp -d)/stopping"
export FACTORYPULSE_JOB_STOP_FLAG
source "$(dirname "$0")/job.sh"

# Seconds between two removals while the scheduler stops.
SWEEP_SECONDS=2

remove_airflow_jobs() {
  remove_jobs "Airflow's" "$JOB_OWNER_LABEL=airflow"
}

scheduler=
stopping=
stop() {
  [ -n "$stopping" ] && return
  stopping=1
  : > "$FACTORYPULSE_JOB_STOP_FLAG"
  if [ -n "$scheduler" ]; then kill -TERM "$scheduler" 2>/dev/null; fi
}
# Installed before the scheduler starts, so that no early signal is lost.
trap stop TERM INT

set -m
airflow scheduler &
scheduler=$!
set +m
# A signal that came before `scheduler=$!` had no scheduler to stop.
if [ -n "$stopping" ]; then kill -TERM "$scheduler" 2>/dev/null; fi

# `wait` returns early when a trapped signal arrives.
until [ -n "$stopping" ]; do
  wait "$scheduler"
  status=$?
  if [ -z "$stopping" ]; then
    remove_airflow_jobs
    exit "$status"
  fi
done

while kill -0 "$scheduler" 2>/dev/null; do
  remove_airflow_jobs
  sleep "$SWEEP_SECONDS"
done
wait "$scheduler"
status=$?
remove_airflow_jobs
exit "$status"
