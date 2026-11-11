"""Lock the Airflow orchestration (ticket 06): the DAGs, their services, and image.

Airflow is a pure orchestrator here. Every task is a ``BashOperator`` that runs
one step of a driver script (``scripts/lake.sh``, ``scripts/dbt.sh``,
``scripts/quality.sh``), and every step runs ``docker compose run --rm
<service>``. So each task is the exact command a human types in the repository
root, and the DAG adds only scheduling, edges, retries and failure visibility.

Airflow is not installed on the host (it does not support the host's Python),
so the DAG file is loaded here against a recording stand-in for the two Airflow
imports it uses. The real parse runs inside the Airflow image: the ``DagBag``
tests at the bottom skip on the host and run there.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from factorypulse import quality

ROOT = Path(__file__).resolve().parent.parent
DAG_FILE = ROOT / "dags" / "factorypulse_dag.py"
HOST_DIR = "/srv/checkout/DataEngProj"

DAILY = "factorypulse_daily"
WEEKLY = "factorypulse_weekly"

# Each task and the driver step it runs, in pipeline order.
DAILY_STEPS = [
    ("run_batch_ingestion", "bash scripts/lake.sh batch"),
    ("check_ingestion_quality", "bash scripts/quality.sh ingestion"),
    ("run_dbt_transformations", "bash scripts/dbt.sh daily"),
    ("check_post_dbt_quality", "bash scripts/quality.sh post-dbt"),
]
WEEKLY_STEPS = [
    ("build_weekly_mart", "bash scripts/dbt.sh weekly"),
    ("check_weekly_quality", "bash scripts/quality.sh weekly"),
]


class _FakeDAG:
    """Records the tasks declared inside its ``with`` block."""

    current = None

    def __init__(self, dag_id, **kwargs):
        self.dag_id = dag_id
        self.kwargs = kwargs
        self.tasks = {}

    def __enter__(self):
        type(self).current = self
        return self

    def __exit__(self, *exc):
        type(self).current = None


class _FakeBashOperator:
    def __init__(self, task_id, **kwargs):
        self.task_id = task_id
        self.kwargs = kwargs
        self.downstream = []
        _FakeDAG.current.tasks[task_id] = self

    def __rshift__(self, other):
        self.downstream.append(other)
        return other


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    """The DAG file refuses to load without it, as compose leaves it empty."""
    monkeypatch.setenv("AIRFLOW__API_AUTH__JWT_SECRET", "test-jwt-secret")


def _load_dag_file(monkeypatch):
    """Execute the DAG file against a recording Airflow; return the module."""
    modules = {
        "airflow": types.SimpleNamespace(),
        "airflow.sdk": types.SimpleNamespace(DAG=_FakeDAG),
        "airflow.providers": types.SimpleNamespace(),
        "airflow.providers.standard": types.SimpleNamespace(),
        "airflow.providers.standard.operators": types.SimpleNamespace(),
        "airflow.providers.standard.operators.bash": types.SimpleNamespace(
            BashOperator=_FakeBashOperator
        ),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("factorypulse_dag_under_test", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dags(monkeypatch):
    """The DAG file's DAGs by id, loaded against a recording Airflow."""
    monkeypatch.setenv("FACTORYPULSE_HOST_DIR", HOST_DIR)
    module = _load_dag_file(monkeypatch)
    found = [value for value in vars(module).values() if isinstance(value, _FakeDAG)]
    return {dag.dag_id: dag for dag in found}


@pytest.mark.parametrize("value", [None, ""])
def test_the_dag_file_refuses_to_load_without_the_host_dir(monkeypatch, value):
    # Without the host path, every job service would bind empty directories
    # and fail later with an error that does not name the cause. The parse
    # error names it instead, in the UI's import errors, before any run.
    if value is None:
        monkeypatch.delenv("FACTORYPULSE_HOST_DIR", raising=False)
    else:
        monkeypatch.setenv("FACTORYPULSE_HOST_DIR", value)
    with pytest.raises(RuntimeError, match=r"FACTORYPULSE_HOST_DIR.*\.env"):
        _load_dag_file(monkeypatch)


@pytest.mark.parametrize("value", [None, ""])
def test_the_dag_file_refuses_to_load_without_the_jwt_secret(monkeypatch, value):
    # Without a shared secret, each Airflow process signs task tokens with its
    # own random one, and every task fails on an authentication error that
    # does not name the cause.
    monkeypatch.setenv("FACTORYPULSE_HOST_DIR", HOST_DIR)
    if value is None:
        monkeypatch.delenv("AIRFLOW__API_AUTH__JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("AIRFLOW__API_AUTH__JWT_SECRET", value)
    with pytest.raises(RuntimeError, match=r"AIRFLOW_JWT_SECRET.*\.env"):
        _load_dag_file(monkeypatch)


# --- the two DAGs and their graphs --------------------------------------------


def test_the_file_defines_a_daily_and_a_weekly_dag(dags):
    assert sorted(dags) == [DAILY, WEEKLY]


@pytest.mark.parametrize("dag_id, steps", [(DAILY, DAILY_STEPS), (WEEKLY, WEEKLY_STEPS)])
def test_tasks_run_in_a_single_chain_in_pipeline_order(dags, dag_id, steps):
    tasks = dags[dag_id].tasks
    order = [task_id for task_id, _ in steps]

    assert sorted(tasks) == sorted(order)
    for upstream, downstream in zip(order, order[1:]):
        assert [t.task_id for t in tasks[upstream].downstream] == [downstream]
    assert tasks[order[-1]].downstream == []


def test_the_raw_lake_is_checked_before_dbt_reads_it(dags):
    # ingestion -> raw lake checks -> dbt -> dbt model checks (ticket 07): a
    # failed raw check stops dbt from building on bad data.
    order = [task_id for task_id, _ in DAILY_STEPS]
    assert order.index("check_ingestion_quality") < order.index("run_dbt_transformations")


@pytest.mark.parametrize("dag_id, steps", [(DAILY, DAILY_STEPS), (WEEKLY, WEEKLY_STEPS)])
def test_every_task_runs_one_driver_step_from_the_project_directory(dags, dag_id, steps):
    # The command is what a human types in the repository root. BashOperator
    # runs in a temporary directory, so cwd is what lets the drivers and
    # `docker compose` find compose.yaml (ticket 07 hand-off).
    tasks = dags[dag_id].tasks
    for task_id, command in steps:
        assert tasks[task_id].kwargs["bash_command"] == command
        assert tasks[task_id].kwargs["cwd"] == HOST_DIR


def test_the_daily_dag_runs_every_day(dags):
    assert dags[DAILY].kwargs["schedule"] == "@daily"


def test_the_weekly_dag_runs_after_the_iso_week_has_closed(dags):
    # An ISO week runs Monday to Sunday, so the weekly mart is rolled up on
    # Monday, once the last day of the week is in the hourly mart, and after
    # the daily run at midnight.
    minute, hour, day_of_month, month, day_of_week = dags[WEEKLY].kwargs["schedule"].split()
    assert (day_of_month, month, day_of_week) == ("*", "*", "1")
    assert int(hour) > 0


@pytest.mark.parametrize("dag_id", [DAILY, WEEKLY])
def test_dags_run_one_at_a_time_without_backfilling_history(dags, dag_id):
    # One run at a time: two overlapping runs would merge into the same Delta
    # table at once. No catchup: unpausing must not queue a run per missed day.
    kwargs = dags[dag_id].kwargs
    assert kwargs["max_active_runs"] == 1
    assert kwargs["catchup"] is False


@pytest.mark.parametrize("dag_id", [DAILY, WEEKLY])
def test_a_failed_task_is_retried(dags, dag_id):
    default_args = dags[dag_id].kwargs["default_args"]
    assert default_args["retries"] >= 1
    assert default_args["retry_delay"].total_seconds() > 0


# --- the steps the tasks run exist and run a compose service -----------------


def _case_labels(script):
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    return set(re.findall(r"^\s+([a-z-]+)\)", text, re.MULTILINE))


@pytest.mark.parametrize("command", [c for _, c in DAILY_STEPS + WEEKLY_STEPS])
def test_every_scheduled_step_is_a_driver_command(command):
    _, script, step = command.split()
    assert step in _case_labels(Path(script).name)


@pytest.mark.parametrize("stage", ["ingestion", "post-dbt", "weekly"])
def test_quality_steps_are_quality_stages(stage):
    assert stage in quality.STAGES


@pytest.mark.parametrize("script", ["lake.sh", "dbt.sh", "quality.sh"])
def test_drivers_stop_at_the_first_failing_command(script):
    # A failing step must fail its task: the driver exits non-zero as soon as
    # any command in it fails, and Airflow marks the task failed.
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert 'cd "$(dirname "$0")/.."' in text


# --- a driver step owns its job container (review 06, P-1) -------------------
#
# A task is a bash process running `docker compose run --rm <service>` against
# the host daemon. When the task dies (scheduler killed, task killed), the job
# container keeps running on the host. So each step removes any one-off
# container of its service before it starts one, and removes it when it is
# killed. The drivers run here against a fake `docker` that logs its calls.

# Each scheduled step and the compose service it runs.
STEP_SERVICES = [
    ("lake.sh", "batch", "batch-ingest"),
    ("quality.sh", "ingestion", "quality"),
    ("dbt.sh", "daily", "dbt"),
    ("quality.sh", "post-dbt", "quality"),
    ("dbt.sh", "weekly", "dbt"),
    ("quality.sh", "weekly", "quality"),
]

STALE_ID = "0123stale456"

# `docker ps` prints STALE_ID when its filters include FAKE_STALE_LABEL (a
# prefix match: `factorypulse.job.run=` matches every run). With
# FAKE_LATE_JOB set to a file, that container exists only while the file
# does, and `docker rm` deletes the file.
# `docker compose run` stands in for the compose CLI: with FAKE_KILL_ON_RUN
# set to a signal, it sends that signal to its whole process group, as
# BashOperator.on_kill does, and keeps running until the signal reaches it.
# Otherwise it exits FAKE_RUN_EXIT (0 by default), as the job would.
FAKE_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_DOCKER_LOG"
case "$1" in
  ps)
    if [ -n "${FAKE_STALE_LABEL:-}" ]; then
      case "$*" in *"label=$FAKE_STALE_LABEL"*)
        if [ -z "${FAKE_LATE_JOB:-}" ] || [ -e "$FAKE_LATE_JOB" ]; then
          echo "$FAKE_STALE_ID"
        fi;;
      esac
    fi;;
  rm)
    if [ -n "${FAKE_LATE_JOB:-}" ]; then rm -f "$FAKE_LATE_JOB"; fi;;
  compose)
    case "$*" in
      *" run "*)
        if [ -n "${FAKE_KILL_ON_RUN:-}" ]; then
          trap 'echo "compose run stopped" >> "$FAKE_DOCKER_LOG"; exit 1' TERM INT
          kill -"$FAKE_KILL_ON_RUN" 0
          while :; do sleep 0.1; done
        fi
        exit "${FAKE_RUN_EXIT:-0}";;
    esac;;
esac
exit 0
"""

# Stands in for `airflow scheduler`: logs how it was started and with which
# job owner, then runs until SIGTERM, or exits on its own with
# FAKE_SCHEDULER_EXIT. On SIGTERM it waits for its running task, as the
# LocalExecutor does: the task ends once its job container is removed
# (`docker rm`). If that never happens, it is SIGKILLed: exit 137.
# The task can also still be on its way to its job when the stop arrives:
#   - FAKE_TASK_AFTER_STOP: the task runs this driver step after the stop.
#   - FAKE_LATE_JOB: the task starts its job container (the file) 0.5 s
#     after the stop, and ends once that container is removed.
FAKE_AIRFLOW = """#!/usr/bin/env bash
echo "airflow $* owner=${FACTORYPULSE_JOB_OWNER:-}" >> "$FAKE_DOCKER_LOG"
if [ -n "${FAKE_SCHEDULER_EXIT:-}" ]; then exit "$FAKE_SCHEDULER_EXIT"; fi
stopping() {
  echo "airflow scheduler stopping" >> "$FAKE_DOCKER_LOG"
  if [ -n "${FAKE_TASK_AFTER_STOP:-}" ]; then
    bash $FAKE_TASK_AFTER_STOP
    echo "task exit $?" >> "$FAKE_DOCKER_LOG"
    exit 0
  fi
  if [ -n "${FAKE_LATE_JOB:-}" ]; then
    sleep 0.5
    touch "$FAKE_LATE_JOB"
    echo "late job started" >> "$FAKE_DOCKER_LOG"
  fi
  for _ in $(seq 100); do
    if [ -n "${FAKE_LATE_JOB:-}" ]; then
      [ -e "$FAKE_LATE_JOB" ] || exit 0
    else
      grep -q "^rm -f " "$FAKE_DOCKER_LOG" && exit 0
    fi
    sleep 0.1
  done
  exit 137
}
trap stopping TERM
# FAKE_STOP_AT_START: the stop arrives while scripts/scheduler.sh starts us.
if [ -n "${FAKE_STOP_AT_START:-}" ]; then kill -TERM "$PPID"; fi
while :; do sleep 0.1; done
"""


def _bash():
    """Git Bash or a Unix bash; never the WSL launcher, which has its own PATH."""
    found = shutil.which("bash")
    if not found or re.search(r"system32|WindowsApps", found, re.IGNORECASE):
        pytest.skip("needs a bash that shares this PATH (Git Bash on Windows)")
    return found


def _fakes(tmp_path, **fake_env):
    """Fake `docker` and `airflow` on PATH; return (env, the shared call log)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, text in [("docker", FAKE_DOCKER), ("airflow", FAKE_AIRFLOW)]:
        with open(bin_dir / name, "w", newline="") as handle:
            handle.write(text)
        (bin_dir / name).chmod(0o755)
    log = tmp_path / "docker.log"
    log.touch()
    env = dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        FAKE_DOCKER_LOG=log.as_posix(),
        FAKE_STALE_ID=STALE_ID,
        COMPOSE_PROJECT_NAME="",
        FACTORYPULSE_JOB_OWNER="",
        FACTORYPULSE_JOB_STOP_FLAG="",
    )
    env.update(fake_env)
    return env, log


def _run_bash(args, env):
    # Its own session: the fake compose signals its whole process group.
    return subprocess.run(
        [_bash(), *args], cwd=ROOT, env=env, capture_output=True, text=True,
        timeout=60, start_new_session=True,
    )


def _service_label(service):
    return f"com.docker.compose.service={service}"


def _drive(tmp_path, script, step, stale_label="", kill_on_run="", **fake_env):
    """Run one driver step against the fake docker; return (exit code, calls).

    A container is stale when the step's lookup filters on STALE_LABEL."""
    env, log = _fakes(
        tmp_path, FAKE_STALE_LABEL=stale_label, FAKE_KILL_ON_RUN=kill_on_run, **fake_env
    )
    result = _run_bash([f"scripts/{script}", step], env)
    return result.returncode, log.read_text(encoding="utf-8").splitlines()


def _index(calls, predicate):
    hits = [i for i, call in enumerate(calls) if predicate(call)]
    assert hits, f"no matching docker call in {calls}"
    return hits


def _is_run(service):
    return lambda call: call.startswith("compose ") and " run --rm " in call and (
        f" {service} " in f"{call} "
    )


def _is_remove(call):
    return call == f"rm -f {STALE_ID}"


@pytest.mark.parametrize("script, step, service", STEP_SERVICES)
def test_a_step_removes_a_stale_job_container_of_its_service_before_starting(
    tmp_path, script, step, service
):
    code, calls = _drive(tmp_path, script, step, stale_label=_service_label(service))

    assert code == 0, calls
    [run] = _index(calls, _is_run(service))
    removes = _index(calls, _is_remove)
    assert removes[0] < run


@pytest.mark.parametrize("script, step, service", STEP_SERVICES)
def test_a_step_looks_for_stale_containers_by_project_one_off_and_service(
    tmp_path, script, step, service
):
    # Only this project's one-off containers of this service: never the
    # long-running services, another service's job, or another project.
    code, calls = _drive(tmp_path, script, step)

    assert code == 0, calls
    first_lookup = _index(calls, lambda call: call.startswith("ps "))[0]
    [run] = _index(calls, _is_run(service))
    assert first_lookup < run
    lookup = calls[first_lookup]
    assert "-aq" in lookup.split()
    assert "label=com.docker.compose.project=factorypulse" in lookup
    assert "label=com.docker.compose.oneoff=True" in lookup
    assert f"label=com.docker.compose.service={service}" in lookup


@pytest.mark.parametrize("script, step, service", STEP_SERVICES)
def test_a_step_with_no_stale_container_removes_nothing(tmp_path, script, step, service):
    code, calls = _drive(
        tmp_path, script, step, stale_label=_service_label("some-other-service")
    )

    assert code == 0, calls
    assert not [call for call in calls if call.startswith("rm ")]
    _index(calls, _is_run(service))


def _label(call, key):
    """The value of label KEY in a `compose run` call or a `ps` filter."""
    found = re.findall(rf"(?:--label |label=){re.escape(key)}=(\S+)", call)
    assert len(found) == 1, f"no single {key} label in {call!r}"
    return found[0]


@pytest.mark.parametrize("signal, code", [("TERM", 143), ("INT", 130)])
@pytest.mark.parametrize("script, step, service", STEP_SERVICES)
def test_a_killed_step_removes_its_own_job_container_and_fails(
    tmp_path, script, step, service, signal, code
):
    # BashOperator.on_kill sends SIGTERM to the task's process group, Ctrl-C
    # sends SIGINT to the terminal's. Bash runs its trap only once its
    # foreground `docker compose run` has exited, which it does because it
    # gets the signal too. The trap then removes the container that run left,
    # and the step exits 128 + the signal number, so the task fails.
    # `factorypulse.job.run=` matches the lookup of any run's container.
    exit_code, calls = _drive(
        tmp_path, script, step, stale_label="factorypulse.job.run=", kill_on_run=signal
    )

    assert exit_code == code, calls
    [run] = _index(calls, _is_run(service))
    [stopped] = _index(calls, lambda call: call == "compose run stopped")
    [removed] = _index(calls, _is_remove)
    assert run < stopped < removed
    # Only this run's container (review 06, R-2): a late trap must never
    # remove the container of a retry that has started since.
    [lookup] = [call for call in calls[stopped:removed] if call.startswith("ps ")]
    assert _label(lookup, "factorypulse.job.run") == _label(calls[run], "factorypulse.job.run")


def test_every_step_run_carries_its_own_run_label(tmp_path):
    first = _drive(tmp_path / "a", "lake.sh", "batch")[1]
    second = _drive(tmp_path / "b", "lake.sh", "batch")[1]

    labels = [
        _label(calls[_index(calls, _is_run("batch-ingest"))[0]], "factorypulse.job.run")
        for calls in (first, second)
    ]
    assert labels[0] != labels[1]


@pytest.mark.parametrize("owner, label", [("", "hand"), ("airflow", "airflow")])
def test_a_step_labels_its_job_container_with_who_started_it(tmp_path, owner, label):
    # The scheduler marks its tasks' containers, so that stopping it removes
    # those and never a job a human started by hand.
    _, calls = _drive(tmp_path, "lake.sh", "batch", FACTORYPULSE_JOB_OWNER=owner)

    [run] = _index(calls, _is_run("batch-ingest"))
    assert _label(calls[run], "factorypulse.job.owner") == label


def test_a_killed_step_removes_its_container_whatever_its_owner_is_called(tmp_path):
    # The owner comes from the environment and is part of the run label; a
    # quote or a space in it must not break the removal (review 06, U-2).
    code, calls = _drive(
        tmp_path, "lake.sh", "batch", stale_label="factorypulse.job.run=", kill_on_run="TERM",
        FACTORYPULSE_JOB_OWNER="o'brien x",
    )

    assert code == 143, calls
    [run] = _index(calls, _is_run("batch-ingest"))
    [removed] = _index(calls, _is_remove)
    assert run < removed
    assert "--label factorypulse.job.owner=o'brien x " in calls[run]


def test_a_failed_job_fails_run_job_itself(tmp_path):
    # The job's exit code is run_job's, so a caller without `set -e` still
    # fails (review 06, U-1).
    env, _ = _fakes(tmp_path, FAKE_RUN_EXIT="3")
    result = _run_bash(
        ["-c", 'source scripts/job.sh; run_job batch-ingest; echo "status $?"'], env
    )

    assert "status 3" in result.stdout.splitlines(), result.stderr


@pytest.mark.parametrize("script, step, service", STEP_SERVICES)
def test_a_step_refuses_to_start_its_job_once_the_scheduler_is_stopping(
    tmp_path, script, step, service
):
    # scripts/scheduler.sh creates the stop flag before it signals Airflow. A
    # task still on its way to its job must not start one (review 06, T-1).
    flag = tmp_path / "stopping"
    flag.touch()
    code, calls = _drive(tmp_path, script, step, FACTORYPULSE_JOB_STOP_FLAG=flag.as_posix())

    assert code != 0, calls
    assert not [call for call in calls if _is_run(service)(call)]


def test_a_step_starts_its_job_while_the_scheduler_is_not_stopping(tmp_path):
    flag = tmp_path / "stopping"
    code, calls = _drive(tmp_path, "lake.sh", "batch", FACTORYPULSE_JOB_STOP_FLAG=flag.as_posix())

    assert code == 0, calls
    _index(calls, _is_run("batch-ingest"))


def test_the_stale_container_lookup_names_this_compose_project():
    # The project label is the compose file's `name:`; a different value
    # would make the lookup match nothing.
    match = re.search(r"^name:\s*(\S+)\s*$", _compose_text(), re.MULTILINE)
    assert match and match.group(1) == "factorypulse"


def test_the_stale_container_lookup_follows_a_project_name_override(tmp_path):
    # COMPOSE_PROJECT_NAME renames the project for compose; the lookup must
    # follow it, or it would find nothing and leave the orphans running.
    _, calls = _drive(tmp_path, "lake.sh", "batch", COMPOSE_PROJECT_NAME="other")

    lookup = calls[_index(calls, lambda call: call.startswith("ps "))[0]]
    assert "label=com.docker.compose.project=other" in lookup


# --- a scheduler stop removes its tasks' job containers (re-review 06, R-1) --
#
# On SIGTERM, Airflow's LocalExecutor waits for the running tasks and never
# calls on_kill, and each task's bash runs in a session of its own, so no
# signal reaches it. The job container would run on, and Docker would SIGKILL
# the scheduler at the end of the grace period. scripts/scheduler.sh runs
# `airflow scheduler` and removes the job containers its tasks started.


def _run_scheduler(tmp_path, **fake_env):
    """Start scripts/scheduler.sh, SIGTERM it once Airflow is up (unless the
    fake scheduler exits on its own); return (exit code, calls)."""
    env, log = _fakes(tmp_path, FAKE_STALE_LABEL="factorypulse.job.owner=airflow", **fake_env)
    harness = (
        'bash scripts/scheduler.sh & pid=$!\n'
        'until grep -q "^airflow scheduler" "$FAKE_DOCKER_LOG"; do sleep 0.1; done\n'
        '[ -n "${FAKE_SCHEDULER_EXIT:-}${FAKE_STOP_AT_START:-}" ] || kill -TERM "$pid"\n'
        'wait "$pid"\n'
    )
    result = _run_bash(["-c", harness], env)
    return result.returncode, log.read_text(encoding="utf-8").splitlines()


def _airflow_job_removals(calls):
    """Indices of the `docker rm` calls; every lookup is for Airflow's jobs."""
    lookups = [call for call in calls if call.startswith("ps ")]
    assert lookups, calls
    for lookup in lookups:
        assert "-aq" in lookup.split()
        assert "label=com.docker.compose.project=factorypulse" in lookup
        assert "label=com.docker.compose.oneoff=True" in lookup
        assert "label=factorypulse.job.owner=airflow" in lookup
    return [i for i, call in enumerate(calls) if _is_remove(call)]


def test_stopping_the_scheduler_removes_its_tasks_job_containers(tmp_path):
    code, calls = _run_scheduler(tmp_path)

    assert code == 0, calls
    # Its tasks inherit the owner, so their containers carry the label.
    assert "airflow scheduler owner=airflow" in calls
    assert "airflow scheduler stopping" in calls
    assert _airflow_job_removals(calls), calls


def test_a_scheduler_that_exits_on_its_own_leaves_no_job_container(tmp_path):
    # A crash ends the container, and every task with it: their job
    # containers go too, and the scheduler's exit code is kept.
    code, calls = _run_scheduler(tmp_path, FAKE_SCHEDULER_EXIT="3")

    assert code == 3, calls
    started = calls.index("airflow scheduler owner=airflow")
    assert [i for i in _airflow_job_removals(calls) if i > started], calls


def test_a_stop_that_arrives_as_the_scheduler_starts_still_stops_it(tmp_path):
    # Review 06, U-3: the stop trap is in place before the scheduler starts,
    # so an early SIGTERM stops the scheduler and removes its tasks' jobs
    # instead of killing the script and leaving the scheduler running.
    code, calls = _run_scheduler(tmp_path, FAKE_STOP_AT_START="1")

    assert code == 0, calls
    assert "airflow scheduler stopping" in calls
    assert _airflow_job_removals(calls), calls


def test_a_stopping_scheduler_removes_a_job_container_started_after_the_stop(tmp_path):
    # Review 06, T-1: a task can be between its start and `docker compose
    # run` when the stop arrives, so its container appears after the first
    # removal. The script keeps removing until the scheduler has exited;
    # otherwise the scheduler waits for that task until SIGKILL (137).
    late = tmp_path / "late-job"
    code, calls = _run_scheduler(tmp_path, FAKE_LATE_JOB=late.as_posix())

    assert code == 0, calls
    started = calls.index("late job started")
    assert [i for i in _airflow_job_removals(calls) if i > started], calls
    assert not late.exists()


def test_a_task_that_reaches_its_job_after_the_stop_does_not_start_it(tmp_path):
    # Every task inherits the stop flag from scripts/scheduler.sh, which
    # creates it before it signals Airflow: a step that reaches run_job
    # afterwards fails without starting its job container.
    code, calls = _run_scheduler(tmp_path, FAKE_TASK_AFTER_STOP="scripts/lake.sh batch")

    assert code == 0, calls
    [ended] = [call for call in calls if call.startswith("task exit ")]
    assert ended != "task exit 0", calls
    assert not [call for call in calls if _is_run("batch-ingest")(call)]


def test_the_scheduler_service_runs_airflow_through_the_stop_script():
    service = _service("airflow-scheduler")
    assert 'command: ["bash", "${FACTORYPULSE_HOST_DIR:-/opt/factorypulse}/scripts/scheduler.sh"]' in service
    # The tasks need time after the removal to report their failure.
    assert re.search(r"^\s+stop_grace_period:\s*1m\s*$", service, re.MULTILINE)


def _function_body(script, name):
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    one_line = re.search(rf"^{name}\(\)\s*\{{(.*)\}}\s*$", text, re.MULTILINE)
    assert one_line, f"scripts/{script} has no one-line {name}()"
    return one_line.group(1)


def test_daily_dbt_step_builds_every_model_except_the_weekly_grain():
    body = _function_body("dbt.sh", "daily")
    assert "docker compose up -d minio" in body
    assert 'dbt_run "build --target lake --exclude tag:weekly"' in body


def test_weekly_dbt_step_builds_only_the_weekly_grain():
    # `cautious`: the weekly mart's relationships test also references
    # dim_machine, which a weekly-only run does not build, so it stays out.
    body = _function_body("dbt.sh", "weekly")
    assert "docker compose up -d minio" in body
    assert (
        'dbt_run "build --target lake --select tag:weekly --indirect-selection cautious"' in body
    )


def test_quality_driver_runs_the_weekly_stage_through_the_service():
    text = (ROOT / "scripts" / "quality.sh").read_text(encoding="utf-8")
    assert re.search(r"^\s*weekly\)\s+check --stage weekly;;", text, re.MULTILINE)


def test_the_full_lake_build_checks_both_dbt_stages():
    body = _function_body("dbt.sh", "run")
    built = body.index('dbt_run "build --target lake"')
    assert built < body.index("scripts/quality.sh post-dbt")
    assert built < body.index("scripts/quality.sh weekly")


# --- the Airflow services and image ------------------------------------------


def _compose_text():
    return (ROOT / "compose.yaml").read_text(encoding="utf-8")


def _block(pattern):
    match = re.search(pattern, _compose_text(), re.MULTILINE)
    assert match, f"compose.yaml has no block matching {pattern!r}"
    return match.group(1)


def _service(name):
    return _block(rf"^  {name}:\n((?:    .*\n|\n)+)")


def _airflow_common():
    return _block(r"^x-airflow-common: &airflow-common\n((?:  .*\n|\n)+)")


AIRFLOW_SERVICES = ["airflow-init", "airflow-webserver", "airflow-scheduler", "airflow-dag-processor"]


@pytest.mark.parametrize("name", AIRFLOW_SERVICES)
def test_airflow_services_share_one_image_and_their_own_profile(name):
    # Own profile: `docker compose up -d` brings up the platform only.
    service = _service(name)
    assert "<<: *airflow-common" in service
    common = _airflow_common()
    assert "dockerfile: docker/airflow.Dockerfile" in common
    assert 'profiles: ["airflow"]' in common


def test_airflow_runs_the_local_executor_over_sqlite():
    common = _airflow_common()
    assert "AIRFLOW__CORE__EXECUTOR: LocalExecutor" in common
    assert "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: sqlite:////opt/airflow/airflow.db" in common
    assert "AIRFLOW__CORE__LOAD_EXAMPLES: \"false\"" in common
    # The metadata database and task logs outlive the containers.
    assert "airflow-data:/opt/airflow" in common


def test_airflow_dags_are_unpaused_so_they_run_on_their_own():
    assert 'AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "false"' in _airflow_common()


def test_tasks_reach_the_api_server_that_runs_the_ui():
    common = _airflow_common()
    assert "AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-webserver:8080/execution/" in common
    # The secret is read from .env, as the design asks for credentials.
    assert "AIRFLOW__API_AUTH__JWT_SECRET: ${AIRFLOW_JWT_SECRET:-" in common
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^AIRFLOW_JWT_SECRET=\S+", example, re.MULTILINE)


def test_the_ui_is_published_on_localhost_only():
    # The UI runs without a login (local dev), so it must not face the network.
    service = _service("airflow-webserver")
    assert "command: api-server" in service
    assert '"127.0.0.1:8080:8080"' in service


def test_the_scheduler_runs_compose_against_the_host_daemon_from_the_project_path():
    # The scheduler's LocalExecutor runs the tasks. `docker compose` there
    # talks to the host daemon through its socket, and the daemon resolves
    # every relative bind mount (`./spark`, `./src`, `./dbt`) on the host.
    # So the repository is mounted at the path the daemon knows it by, and
    # the same path is the tasks' working directory.
    service = _service("airflow-scheduler")
    assert "scripts/scheduler.sh" in service
    assert "/var/run/docker.sock:/var/run/docker.sock" in service
    assert "- .:${FACTORYPULSE_HOST_DIR:-/opt/factorypulse}" in service
    # No fallback path reaches the DAG file: unset, it stays empty, and the
    # DAG file refuses to load with a message naming the knob. The mount
    # keeps a fallback only so that compose.yaml stays valid without .env.
    assert "FACTORYPULSE_HOST_DIR: ${FACTORYPULSE_HOST_DIR:-}\n" in _airflow_common()


def test_every_airflow_process_reads_the_repository_dags():
    assert "./dags:/opt/airflow/dags:ro" in _airflow_common()


def test_init_migrates_the_metadata_database_before_anything_starts():
    assert "airflow db migrate" in _service("airflow-init")
    for name in ["airflow-webserver", "airflow-scheduler", "airflow-dag-processor"]:
        assert "airflow-init: { condition: service_completed_successfully }" in _service(name)


def test_the_host_dir_knob_is_templated_in_env_example():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^FACTORYPULSE_HOST_DIR=", example, re.MULTILINE)


def test_airflow_image_is_pinned_airflow_plus_the_compose_cli():
    dockerfile = (ROOT / "docker" / "airflow.Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM apache/airflow:slim-\d+\.\d+\.\d+-python3\.12$", dockerfile, re.MULTILINE)
    # A release tag, as for every other base image: a floating `29-cli`
    # changes the compose CLI under the scheduler on the next build.
    copies = re.findall(r"^COPY --from=(\S+) ", dockerfile, re.MULTILINE)
    assert len(copies) == 2
    assert all(re.fullmatch(r"docker:\d+\.\d+\.\d+-cli", image) for image in copies), copies
    assert "cli-plugins/docker-compose" in dockerfile


# --- the real parse, inside the Airflow image --------------------------------


def _dagbag(monkeypatch):
    models = pytest.importorskip("airflow.models", reason="Airflow runs in its image, not on the host")
    monkeypatch.setenv("FACTORYPULSE_HOST_DIR", HOST_DIR)
    # Airflow 3 dropped `include_examples`; examples are off by config instead.
    return models.DagBag(dag_folder=str(DAG_FILE.parent))


def test_dagbag_loads_both_dags_without_errors(monkeypatch):
    dagbag = _dagbag(monkeypatch)
    assert dagbag.import_errors == {}
    assert {DAILY, WEEKLY} <= set(dagbag.dags)


@pytest.mark.parametrize("dag_id, steps", [(DAILY, DAILY_STEPS), (WEEKLY, WEEKLY_STEPS)])
def test_dagbag_exposes_the_task_chain(monkeypatch, dag_id, steps):
    dag = _dagbag(monkeypatch).dags[dag_id]
    order = [task_id for task_id, _ in steps]
    assert sorted(dag.task_ids) == sorted(order)
    for upstream, downstream in zip(order, order[1:]):
        assert dag.get_task(upstream).downstream_task_ids == {downstream}
