"""Stopping the Airflow scheduler removes its tasks' job containers (ticket 06).

Re-review 06, R-1: on SIGTERM, Airflow's LocalExecutor waits for its running
tasks and never calls ``BashOperator.on_kill``, so a job container started by
a task would outlive a ``docker compose stop``. ``scripts/scheduler.sh`` runs
the scheduler and removes those containers itself. Second re-review 06, T-1:
a task can also be on its way to its job when the stop arrives, and start its
container after the first removal.

These tests run the real thing on the Docker daemon: a throwaway Airflow
(project image, LocalExecutor, SQLite) whose scheduler runs through
``scripts/scheduler.sh``, and a one-task DAG whose task runs a long job
through ``run_job``, as the pipeline's steps do. The scheduler is stopped with
its compose grace period, either once the job container runs or while the
task still waits before ``run_job``. Each test asserts that no job container
is left and that the scheduler exited on its own, before SIGKILL. The
stand-in job sleeps, so no lake and no pipeline image is needed, only the
Airflow image (``docker compose --profile airflow build``). Each container is
capped at 1 CPU and 1 GB; each test takes about a minute, so they are opt-in:

    FACTORYPULSE_DOCKER_TESTS=1 python -m pytest tests/test_scheduler_stop.py
"""

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FACTORYPULSE_DOCKER_TESTS") != "1",
    reason="starts a throwaway Airflow on Docker; set FACTORYPULSE_DOCKER_TESTS=1",
)

ROOT = Path(__file__).resolve().parent.parent
# The image the airflow-* services of compose.yaml run.
IMAGE = re.search(
    r"^\s+image:\s*(factorypulse/airflow:\S+)\s*$",
    (ROOT / "compose.yaml").read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)
AIRFLOW_PROJECT = "fpprobe-airflow"
JOBS_PROJECT = "fpprobe-jobs"

AIRFLOW_COMPOSE = f"""\
name: {AIRFLOW_PROJECT}
x-airflow: &airflow
  image: {IMAGE}
  mem_limit: 1g
  cpus: 1
  environment:
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: sqlite:////opt/airflow/airflow.db
    AIRFLOW__CORE__LOAD_EXAMPLES: "false"
    AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "false"
    AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://api:8080/execution/
    AIRFLOW__API_AUTH__JWT_SECRET: fpprobe-secret
    AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS: "true"
    COMPOSE_PROJECT_NAME: {JOBS_PROJECT}
  volumes:
    - airflow-data:/opt/airflow
    - ./dags:/opt/airflow/dags:ro
services:
  init:
    <<: *airflow
    entrypoint: ["/bin/bash", "-c"]
    command: ["airflow db migrate"]
  api:
    <<: *airflow
    command: api-server
    depends_on:
      init: {{ condition: service_completed_successfully }}
  dag-processor:
    <<: *airflow
    command: dag-processor
    depends_on:
      init: {{ condition: service_completed_successfully }}
  scheduler:
    <<: *airflow
    command: ["bash", "/probe/scripts/scheduler.sh"]
    stop_grace_period: 1m
    volumes:
      - airflow-data:/opt/airflow
      - ./dags:/opt/airflow/dags:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - {(ROOT / "scripts").as_posix()}:/probe/scripts:ro
      - ./jobs:/probe/jobs:ro
      - ./out:/probe/out
    depends_on:
      init: {{ condition: service_completed_successfully }}
volumes:
  airflow-data:
"""

# The job the task starts: a container that runs until it is removed.
JOBS_COMPOSE = f"""\
services:
  sleeper:
    image: {IMAGE}
    entrypoint: ["sleep", "600"]
    mem_limit: 64m
    profiles: ["lake-jobs"]
"""

DAG = """\
from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

with DAG("probe_stop", schedule="@once", start_date=datetime(2026, 1, 1), catchup=False):
    BashOperator(task_id="long_job", bash_command={command!r}, cwd="/probe/jobs")
"""

# The task starts its job at once.
RUNS_JOB = "source /probe/scripts/job.sh && run_job sleeper"
# The task is still on its way to its job for 20 s: it marks that it waits.
WAITS_THEN_RUNS_JOB = "touch /probe/out/waiting && sleep 20 && " + RUNS_JOB


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as handle:
        handle.write(text)


def _docker(*args, timeout=120):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout,
    )


def _job_containers(*extra):
    result = _docker(
        "ps", "-aq", "--filter", f"label=com.docker.compose.project={JOBS_PROJECT}", *extra
    )
    return result.stdout.split()


def _until(condition, what):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(3)
    pytest.fail(f"{what} never happened")


@pytest.fixture
def start_probe(tmp_path):
    """Start the throwaway Airflow with a DAG whose task runs COMMAND; return
    the compose arguments that address it."""
    compose = ["compose", "-p", AIRFLOW_PROJECT, "-f", str(tmp_path / "compose.yaml")]

    def start(command):
        _write(tmp_path / "compose.yaml", AIRFLOW_COMPOSE)
        _write(tmp_path / "jobs" / "compose.yaml", JOBS_COMPOSE)
        _write(tmp_path / "dags" / "probe_dag.py", DAG.format(command=command))
        (tmp_path / "out").mkdir()
        up = _docker(*compose, "up", "-d", "api", "dag-processor", "scheduler", timeout=300)
        assert up.returncode == 0, up.stderr
        return compose

    try:
        yield start
    finally:
        _docker(*compose, "down", "-v", "--remove-orphans", timeout=300)
        leftovers = _job_containers()
        if leftovers:
            _docker("rm", "-f", *leftovers)


def _stop_scheduler_and_check(compose):
    started = time.monotonic()
    stop = _docker(*compose, "stop", "scheduler", timeout=180)
    took = time.monotonic() - started
    assert stop.returncode == 0, stop.stderr

    assert _job_containers() == [], "a job container outlived the scheduler"
    scheduler = _docker(*compose, "ps", "-aq", "scheduler").stdout.split()
    assert scheduler, "no scheduler container to inspect"
    code = _docker("inspect", "-f", "{{.State.ExitCode}}", *scheduler).stdout.strip()
    # 137 is SIGKILL at the end of the grace period: the scheduler waited for
    # a task that never ended.
    assert code != "137", f"scheduler SIGKILLed after {took:.0f} s"
    assert took < 60


def test_stopping_the_scheduler_removes_the_running_job_container(start_probe):
    compose = start_probe(RUNS_JOB)
    _until(
        lambda: _job_containers(
            "--filter", "label=factorypulse.job.owner=airflow", "--filter", "status=running"
        ),
        "the probe task starting its job container",
    )

    _stop_scheduler_and_check(compose)


def test_stopping_the_scheduler_before_its_task_starts_the_job_leaves_no_job(
    start_probe, tmp_path
):
    # The stop arrives while the task is still on its way to run_job, so no
    # job container exists yet when scripts/scheduler.sh first removes them.
    compose = start_probe(WAITS_THEN_RUNS_JOB)
    _until(lambda: (tmp_path / "out" / "waiting").exists(), "the probe task starting")
    assert _job_containers() == []

    _stop_scheduler_and_check(compose)
