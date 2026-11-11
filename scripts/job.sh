# FactoryPulse job runner, sourced by the drivers (lake.sh, dbt.sh, quality.sh)
# and by the Airflow scheduler (scheduler.sh).
#
# A driver step owns the one-off containers of its compose service. A step is
# a bash process running `docker compose run --rm <service>` against the
# Docker daemon. If that process dies (an Airflow task killed, the scheduler
# killed), the job container keeps running on the host, and a retry would
# start a second writer next to it. So `run_job`:
#
#   - refuses to start a job once the Airflow scheduler is stopping (the stop
#     flag, see scheduler.sh), and
#   - removes any one-off container of the service before starting one, and
#   - labels its container with a run id and its owner (`airflow` when the
#     scheduler started it, `hand` otherwise), and
#   - on SIGTERM (BashOperator.on_kill) or SIGINT (Ctrl-C), removes the
#     container of its own run, then exits 143 or 130, and
#   - otherwise returns the exit code of the job.
#
# Bash runs a trap only after its foreground command has exited. The removal
# on a signal therefore relies on `docker compose run` getting the signal too
# and exiting: on_kill and Ctrl-C both signal the whole process group. A
# signal sent to the bash process alone waits until the job ends.
#
# One writer per service at a time is the rule, both ways: a step started by
# hand while Airflow runs the same service removes the scheduled job, and
# Airflow retries it; a scheduled step or retry removes a job of the same
# service started by hand. A step removes the old container rather than
# failing fast, because the container a dead step leaves can hang forever:
# a retry that waited for it would never run.

JOBS=(--profile lake-jobs)

# The compose project: `name:` in compose.yaml, unless COMPOSE_PROJECT_NAME
# overrides it for compose too.
JOB_PROJECT="${COMPOSE_PROJECT_NAME:-factorypulse}"

# The labels run_job puts on its container: who started it, and which run.
JOB_OWNER_LABEL=factorypulse.job.owner
JOB_RUN_LABEL=factorypulse.job.run

# Who starts the jobs: scheduler.sh sets `airflow` for every task.
JOB_OWNER="${FACTORYPULSE_JOB_OWNER:-hand}"

# remove_jobs WHAT LABEL...: remove this project's one-off containers that
# carry every LABEL (key=value); WHAT names them in the log.
remove_jobs() {
  local what="$1" label ids
  local filters=(
    --filter "label=com.docker.compose.project=$JOB_PROJECT"
    --filter "label=com.docker.compose.oneoff=True"
  )
  shift
  for label in "$@"; do
    filters+=(--filter "label=$label")
  done
  ids=$(docker ps -aq "${filters[@]}")
  if [ -n "$ids" ]; then
    echo "removing $what job container(s): ${ids//$'\n'/ }" >&2
    # Word splitting is wanted: one argument per container id.
    # shellcheck disable=SC2086
    docker rm -f $ids >/dev/null
  fi
}

# The service and run of the job run_job is running, for its signal traps.
JOB_SERVICE=
JOB_RUN=

# job_killed CODE: remove the container of this run, then exit CODE.
job_killed() {
  remove_jobs "$JOB_SERVICE" "$JOB_RUN_LABEL=$JOB_RUN"
  exit "$1"
}

# run_job SERVICE [RUN OPTIONS...] [-- COMMAND ARGS...]:
# `docker compose run --rm RUN OPTIONS... SERVICE COMMAND ARGS...`.
run_job() {
  local service="$1" options=() status=0
  shift
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do
    options+=("$1")
    shift
  done
  [ $# -gt 0 ] && shift

  # scheduler.sh creates this file before it stops Airflow. A task that gets
  # here afterwards would start a container the scheduler no longer waits for.
  if [ -n "${FACTORYPULSE_JOB_STOP_FLAG:-}" ] && [ -e "$FACTORYPULSE_JOB_STOP_FLAG" ]; then
    echo "the Airflow scheduler is stopping: $service job not started" >&2
    return 1
  fi

  JOB_SERVICE="$service"
  JOB_RUN="$JOB_OWNER-$$-$RANDOM$RANDOM"
  remove_jobs "stale $service" "com.docker.compose.service=$service"
  trap 'job_killed 143' TERM
  trap 'job_killed 130' INT
  docker compose "${JOBS[@]}" run --rm \
    --label "$JOB_OWNER_LABEL=$JOB_OWNER" --label "$JOB_RUN_LABEL=$JOB_RUN" \
    ${options[@]+"${options[@]}"} "$service" "$@" || status=$?
  trap - TERM INT
  return "$status"
}
