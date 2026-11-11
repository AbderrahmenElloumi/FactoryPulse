"""Lock the documentation and repository invariants (ticket 10).

The README and the architecture guide describe what the repository contains,
with no placeholder tokens. Compose reads every credential from the
environment, templated in `.env.example`. Generated data, credentials and
local environments are never tracked.

The MinIO refusal test starts a container: run it with

    FACTORYPULSE_DOCKER_TESTS=1 python -m pytest tests/test_documentation.py
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from factorypulse import analytics
from factorypulse.quality.expectations import CHECKED_TABLES

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "architecture-guide.md"
DOCS = [README, GUIDE]

# Compose settings that carry a credential, and the variable each reads.
CREDENTIAL_SETTINGS = {
    "MINIO_ACCESS_KEY": "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY": "MINIO_SECRET_KEY",
    "MINIO_ROOT_USER": "MINIO_ACCESS_KEY",
    "MINIO_ROOT_PASSWORD": "MINIO_SECRET_KEY",
    "AIRFLOW__API_AUTH__JWT_SECRET": "AIRFLOW_JWT_SECRET",
}
SECRET_VARIABLES = ["MINIO_SECRET_KEY", "AIRFLOW_JWT_SECRET"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _env_example() -> dict:
    pairs = re.findall(r"^([A-Z][A-Z0-9_]*)=(.*)$", _read(ROOT / ".env.example"), re.MULTILINE)
    return dict(pairs)


# ---- README contents -------------------------------------------------------


def test_readme_has_an_architecture_diagram():
    assert "```mermaid" in _read(README)


def test_readme_has_a_single_command_quickstart():
    assert re.search(r"^bash scripts/lake\.sh all$", _read(README), re.MULTILINE)


def test_the_quickstart_runs_every_stage_in_order():
    text = _read(ROOT / "scripts" / "lake.sh")
    match = re.search(r"^all\(\)\s*\{(.*?)^\}", text, re.MULTILINE | re.DOTALL)
    assert match, "scripts/lake.sh defines no all() function"
    # The echo banners name the stages too: drop them, then compare commands.
    body = re.sub(r'echo\s+"[^"]*"\s*;?', "", match.group(1))
    commands = [c.strip() for c in re.split(r"[;\n]", body) if c.strip()]
    assert commands == [
        "docker compose up -d --build",  # the platform, the streamer, the dashboard
        "demo",  # produce, stream, batch, the raw lake checks
        "bash scripts/dbt.sh run",  # the models and their checks
        "anomaly",  # the anomaly scores
    ]
    assert re.search(r"^\s*all\)\s*all;;", text, re.MULTILINE)


def test_readme_has_a_tech_stack_rationale():
    assert re.search(r"^## Tech-stack rationale$", _read(README), re.MULTILINE)


def test_readme_has_virtualenv_and_pytest_instructions():
    readme = _read(README)
    assert "python -m venv .venv" in readme
    assert "pip install -e ." in readme
    assert "python -m pytest" in readme


def test_readme_points_at_the_release_process():
    # The repository goes public through a separate release repository,
    # not by flipping this one's visibility.
    assert "`.scratch/repo-release/spec.md`" in _read(README)


# ---- Documentation honesty -------------------------------------------------


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_docs_carry_no_placeholder_tokens(doc):
    found = re.findall(r"<USER>|<REPO>|your-username|[Pp]laceholder|TODO", _read(doc))
    assert found == []


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_every_path_the_docs_name_exists(doc):
    spans = re.findall(r"`([^`\s]+)`", _read(doc))
    paths = [s for s in spans if "/" in s and not s.startswith(("http", "s3a:", "/"))]
    paths += [s for s in spans if re.fullmatch(r"[\w.-]+\.(py|sh|yaml|toml|md|txt)", s)]
    assert paths, "the doc names no repository path"
    missing = [p for p in paths if not (ROOT / p.rstrip("/")).exists()]
    assert missing == []


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_every_lake_table_the_docs_name_is_registered(doc):
    named = set(re.findall(r"\b(?:raw|dim|fct|mrt)_[a-z_]+\b", _read(doc)))
    assert named, "the doc names no lake table"
    assert named <= set(analytics.TABLE_COLUMNS)


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_docs_claim_checks_on_every_table_only_when_every_table_has_them(doc):
    tables = {analytics.RAW_EVENTS_TABLE, *analytics.REGISTERED_TABLES}
    if tables - set(CHECKED_TABLES):
        assert not re.search(r"\bevery\s+table\b", _read(doc), re.IGNORECASE)


def test_docs_do_not_name_the_rejected_rolling_window_mart():
    for doc in DOCS:
        assert "rolling_window" not in _read(doc), doc.name


# ---- Credentials -----------------------------------------------------------


def test_compose_reads_every_credential_from_the_environment():
    compose = _read(ROOT / "compose.yaml")
    settings = re.findall(
        rf"^\s*({'|'.join(CREDENTIAL_SETTINGS)}):\s*(.*)$", compose, re.MULTILINE
    )
    # Spark jobs (one anchor), producer, quality, streamlit, minio, minio-init,
    # and the Airflow anchor.
    assert len(settings) >= 13
    for setting, value in settings:
        variable = CREDENTIAL_SETTINGS[setting]
        assert value == f"${{{variable}:-}}", (setting, value)


@pytest.mark.parametrize(
    "path", ["compose.yaml", "scripts/reset-lake.sh", "src/factorypulse/producer.py"]
)
def test_no_secret_value_is_embedded_outside_env_example(path):
    text = _read(ROOT / path)
    example = _env_example()
    for variable in SECRET_VARIABLES:
        assert example[variable] not in text, (path, variable)


def test_env_example_declares_every_variable_compose_interpolates():
    interpolated = set(re.findall(r"(?<!\$)\$\{(\w+)", _read(ROOT / "compose.yaml")))
    assert {"MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "AIRFLOW_JWT_SECRET"} <= interpolated
    assert interpolated <= set(_env_example())


def test_env_example_gives_every_credential_a_value():
    example = _env_example()
    for variable in set(CREDENTIAL_SETTINGS.values()):
        assert example.get(variable), variable


needs_docker = pytest.mark.skipif(
    os.environ.get("FACTORYPULSE_DOCKER_TESTS") != "1",
    reason="needs the Docker daemon and the MinIO image; set FACTORYPULSE_DOCKER_TESTS=1",
)


@needs_docker
def test_minio_refuses_to_start_without_credentials(tmp_path):
    # An empty env file stands in for a missing .env: compose interpolates
    # the credentials to empty strings, and MinIO must refuse them rather
    # than fall back to its built-in default login.
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_SETTINGS.values()}
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(empty), "run", "--rm", "--no-deps", "-T", "minio"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "MINIO_ACCESS_KEY and MINIO_SECRET_KEY are not set" in result.stdout + result.stderr


# ---- Repository invariants -------------------------------------------------


def test_pull_request_template_uses_the_name_github_detects():
    github = ROOT / ".github"
    assert (github / "pull_request_template.md").is_file()
    templates = [p.name for p in github.iterdir() if "template" in p.name.lower() and p.is_file()]
    assert templates == ["pull_request_template.md"]


def test_gitignore_excludes_local_state_and_generated_data():
    ignored = set(_read(ROOT / ".gitignore").splitlines())
    assert {".env", ".venv/", "__pycache__/", "data/", "dbt/target/"} <= ignored


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_no_credential_generated_data_or_local_environment_is_tracked():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    forbidden = re.compile(r"(^|/)(\.env$|\.venv/|__pycache__/|data/|dbt/target/|dbt/logs/)")
    assert [p for p in tracked if forbidden.search(p)] == []
