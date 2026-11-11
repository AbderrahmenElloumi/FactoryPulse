"""Lock the release script's contract (repo-release ticket 01).

`scripts/release.sh <version>` publishes `main` to the `public` remote as one
squashed commit per release. Each test builds a throwaway development
repository and a local bare repository that stands in for `public`, so no test
touches the network. The suite command is stubbed with `RELEASE_TEST_CMD`:
the real suite would run this file again.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "release.sh"

IDENTITY = {
    "GIT_AUTHOR_NAME": "Release Test",
    "GIT_AUTHOR_EMAIL": "release@example.invalid",
    "GIT_COMMITTER_NAME": "Release Test",
    "GIT_COMMITTER_EMAIL": "release@example.invalid",
}

# The smallest tree that passes every content check of the release script.
VALID_TREE = {
    "README.md": "# Fixture\n",
    "CHANGELOG.md": "# Changelog\n\n## [0.1.0] - 2026-11-11\n\n### Added\n\n- First release.\n",
    "pyproject.toml": '[project]\nname = "fixture"\nversion = "0.1.0"\n',
    "compose.yaml": "services:\n  minio:\n    environment:\n      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-}\n",
    ".env.example": "MINIO_SECRET_KEY=dev-pass\n",
    "CONTEXT.md": "# Glossary\n",
    "src/fixture/__init__.py": "",
    "tests/test_fixture.py": "",
    "dbt/dbt_project.yml": "name: fixture\n",
    "dags/fixture_dag.py": "",
    "scripts/run.sh": "#!/usr/bin/env bash\n",
    "docker/app.Dockerfile": "FROM scratch\n",
    "docs/adr/0001-decision.md": "# Decision\n",
    "docs/agents/issue-tracker.md": "# Tracker\n",
    ".scratch/design.md": "# Design\n",
    ".scratch/feature/spec.md": "# Spec\n",
    ".scratch/feature/issues/01-ticket.md": "# Ticket\n",
}


def _bash():
    # On Windows, `bash` on PATH can be WSL's; use the bash that ships with git.
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    if git is None:
        return None
    for parent in Path(git).resolve().parents:
        candidate = parent / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


BASH = _bash()
pytestmark = pytest.mark.skipif(
    BASH is None or shutil.which("git") is None, reason="needs git and bash"
)


def _git(repo, *args, check=True):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **IDENTITY},
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def _write(repo, files):
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)


def _commit(repo, message, force=False):
    _git(repo, "add", "-A", *(["-f", "."] if force else []))
    _git(repo, "commit", "-q", "-m", message)


def _release(repo, *args, **env):
    return subprocess.run(
        [BASH, str(SCRIPT), *args],
        cwd=repo,
        env={**os.environ, **IDENTITY, "RELEASE_TEST_CMD": "true", **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def _refs(repo):
    return _git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout


def _state(work, public):
    """Everything a refused release must leave unchanged."""
    return (
        _refs(work),
        _refs(public),
        _git(work, "status", "--porcelain").stdout,
        _git(work, "symbolic-ref", "HEAD").stdout,
    )


@pytest.fixture
def repos(tmp_path):
    """A development repository on `main` and an empty bare `public` remote."""
    public = tmp_path / "public.git"
    work = tmp_path / "work"
    _git(tmp_path, "init", "-q", "--bare", str(public))
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    _git(work, "config", "core.autocrlf", "false")
    _write(work, VALID_TREE)
    _commit(work, "first")
    _git(work, "remote", "add", "public", public.as_posix())
    return work, public


def _bump(work, version):
    _write(
        work,
        {
            "pyproject.toml": f'[project]\nname = "fixture"\nversion = "{version}"\n',
            "CHANGELOG.md": f"# Changelog\n\n## [{version}] - 2026-11-12\n\n- Next.\n\n"
            + VALID_TREE["CHANGELOG.md"].split("\n", 2)[2],
        },
    )
    _commit(work, f"bump {version}")


def _published(work, version):
    result = _release(work, version)
    assert result.returncode == 0, result.stderr
    return result


def _rev(repo, rev):
    return _git(repo, "rev-parse", rev).stdout.strip()


# ---- Dry-run ---------------------------------------------------------------


def test_dry_run_builds_a_root_commit_of_mains_tree_when_public_is_empty(repos):
    work, public = repos
    before = _state(work, public)

    result = _release(work, "--dry-run", "0.1.0")

    assert result.returncode == 0, result.stderr
    commit = result.stdout.split("release commit: ")[1].split()[0]
    assert _rev(work, f"{commit}^{{tree}}") == _rev(work, "main^{tree}")
    assert _git(work, "rev-list", "--parents", "-n", "1", commit).stdout.split() == [commit]
    assert "dry run: nothing pushed" in result.stdout
    assert _state(work, public) == before


def test_dry_run_parents_the_release_commit_on_the_public_tip(repos):
    work, public = repos
    _published(work, "0.1.0")
    _write(work, {"src/fixture/core.py": "VALUE = 2\n"})
    _bump(work, "0.2.0")
    tip = _rev(public, "main")
    before = _refs(public)

    result = _release(work, "--dry-run", "0.2.0")

    assert result.returncode == 0, result.stderr
    commit = result.stdout.split("release commit: ")[1].split()[0]
    assert _rev(work, f"{commit}^{{tree}}") == _rev(work, "main^{tree}")
    assert _git(work, "rev-list", "--parents", "-n", "1", commit).stdout.split() == [commit, tip]
    assert _refs(public) == before


# ---- Publishing ------------------------------------------------------------


def test_publishing_creates_one_commit_and_one_tag_and_leaves_development_untouched(repos):
    work, public = repos
    # Branches and tags; the remote-tracking ref for `public` may move.
    development = _git(work, "for-each-ref", "refs/heads", "refs/tags").stdout

    result = _published(work, "0.1.0")

    assert _git(work, "for-each-ref", "refs/heads", "refs/tags").stdout == development
    assert _git(public, "rev-list", "--count", "main").stdout.strip() == "1"
    assert _git(public, "tag", "--list").stdout.split() == ["v0.1.0"]
    assert _rev(public, "v0.1.0^{commit}") == _rev(public, "main")
    assert _rev(public, "main^{tree}") == _rev(work, "main^{tree}")
    assert "published v0.1.0 to public" in result.stdout


def test_public_history_is_one_commit_per_release_and_cannot_merge_with_development(repos, tmp_path):
    work, public = repos
    _published(work, "0.1.0")
    _bump(work, "0.2.0")
    _published(work, "0.2.0")

    assert _git(public, "rev-list", "--count", "main").stdout.strip() == "2"
    assert _git(public, "tag", "--list").stdout.split() == ["v0.1.0", "v0.2.0"]
    _git(work, "fetch", "-q", "public")
    assert _git(work, "merge-base", "main", "public/main", check=False).returncode == 1
    into_development = _git(work, "merge", "--no-edit", "public/main", check=False)
    assert "refusing to merge unrelated histories" in into_development.stderr

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", public.as_posix(), str(clone))
    _git(clone, "fetch", "-q", work.as_posix(), "main:development")
    into_public = _git(clone, "merge", "--no-edit", "development", check=False)
    assert "refusing to merge unrelated histories" in into_public.stderr


# ---- Refusals --------------------------------------------------------------


def _dirty(work):
    _write(work, {"README.md": "# Edited\n"})


def _wrong_branch(work):
    _git(work, "checkout", "-q", "-b", "dev")


def _changelog_without_heading(work):
    _write(work, {"pyproject.toml": '[project]\nname = "fixture"\nversion = "0.2.0"\n'})
    _commit(work, "bump without changelog")


def _embedded_credential(work):
    _write(work, {"compose.yaml": VALID_TREE["compose.yaml"] + "      MINIO_ROOT_USER: admin\n"})
    _commit(work, "embed credential")


def _undeclared_variable(work):
    _write(
        work,
        {"compose.yaml": VALID_TREE["compose.yaml"] + "      JWT: ${AIRFLOW_JWT_SECRET:-}\n"},
    )
    _commit(work, "interpolate undeclared variable")


def _no_public_remote(work):
    _git(work, "remote", "remove", "public")


def _unreachable_public(work):
    _git(work, "remote", "set-url", "public", (work.parent / "missing.git").as_posix())


REFUSALS = {
    "dirty working tree": (_dirty, "0.1.0", {}),
    "not on main": (_wrong_branch, "0.1.0", {}),
    "test suite failed": (None, "0.1.0", {"RELEASE_TEST_CMD": "false"}),
    "version mismatch: pyproject.toml says 0.1.0": (None, "0.2.0", {}),
    "no changelog heading for 0.2.0": (_changelog_without_heading, "0.2.0", {}),
    "credential embedded in compose.yaml: MINIO_ROOT_USER": (_embedded_credential, "0.1.0", {}),
    ".env.example does not declare: AIRFLOW_JWT_SECRET": (_undeclared_variable, "0.1.0", {}),
    "no remote named public": (_no_public_remote, "0.1.0", {}),
    "cannot reach public": (_unreachable_public, "0.1.0", {}),
}


@pytest.mark.parametrize("reason", REFUSALS)
@pytest.mark.parametrize("dry_run", [False, True], ids=["publish", "dry-run"])
def test_release_refuses_a_broken_state_with_a_named_reason_and_no_side_effects(
    repos, reason, dry_run
):
    work, public = repos
    breaker, version, env = REFUSALS[reason]
    if breaker:
        breaker(work)
    before = _state(work, public)

    result = _release(work, *(["--dry-run"] if dry_run else []), version, **env)

    assert result.returncode == 1
    assert f"release refused: {reason}" in result.stderr
    assert _state(work, public) == before


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "data/readings.parquet",
        "dbt/.user.yml",
        "src/fixture.egg-info/PKG-INFO",
        "build/lib/fixture/__init__.py",
        "dist/fixture-0.1.0.tar.gz",
        ".venv/pyvenv.cfg",
        ".vscode/settings.json",
    ],
    ids=[
        "credentials",
        "generated-data",
        "dbt-user-file",
        "egg-info",
        "build-output",
        "dist-output",
        "virtual-environment",
        "editor-state",
    ],
)
@pytest.mark.parametrize("dry_run", [False, True], ids=["publish", "dry-run"])
def test_release_refuses_a_tree_that_would_publish_an_excluded_path(repos, path, dry_run):
    work, public = repos
    _write(work, {path: "x\n"})
    _commit(work, f"track {path}", force=True)
    before = _state(work, public)

    result = _release(work, *(["--dry-run"] if dry_run else []), "0.1.0")

    assert result.returncode == 1
    assert f"release refused: excluded path in release tree: {path}" in result.stderr
    assert _state(work, public) == before


@pytest.mark.parametrize(
    "path",
    [
        "src/fixture/__init__.py",
        "tests/test_fixture.py",
        "dbt/dbt_project.yml",
        "dags/fixture_dag.py",
        "scripts/run.sh",
        ".scratch/design.md",
        ".scratch/feature/spec.md",
        ".scratch/feature/issues/01-ticket.md",
        "CONTEXT.md",
        "docs/adr/0001-decision.md",
    ],
)
@pytest.mark.parametrize("dry_run", [False, True], ids=["publish", "dry-run"])
def test_release_refuses_a_tree_missing_published_content(repos, path, dry_run):
    work, public = repos
    _git(work, "rm", "-q", path)
    _commit(work, f"drop {path}")
    before = _state(work, public)

    result = _release(work, *(["--dry-run"] if dry_run else []), "0.1.0")

    assert result.returncode == 1
    assert "release refused: missing from release tree: " in result.stderr
    assert _state(work, public) == before


def test_release_refuses_a_version_already_tagged_on_public(repos):
    work, public = repos
    _published(work, "0.1.0")
    before = _state(work, public)

    result = _release(work, "0.1.0")

    assert result.returncode == 1
    assert "release refused: v0.1.0 already tagged on public" in result.stderr
    assert _state(work, public) == before


@pytest.mark.parametrize("args", [[], ["v0.1.0"], ["0.1"], ["--dry-run"]])
def test_release_refuses_a_missing_or_malformed_version(repos, args):
    work, public = repos
    before = _state(work, public)

    result = _release(work, *args)

    assert result.returncode == 2
    assert "usage: scripts/release.sh [--dry-run] <X.Y.Z>" in result.stderr
    assert _state(work, public) == before


# ---- The repository's own tree ---------------------------------------------


def test_the_repository_tree_passes_every_release_check(tmp_path):
    # Copy what the next commit would hold (tracked and new, unignored files)
    # into a fresh repository on `main`, then dry-run the release against an
    # empty stand-in for `public`.
    listed = _git(
        ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
    ).stdout.split("\0")
    work = tmp_path / "work"
    for name in filter(None, listed):
        source = ROOT / name
        if source.is_file():
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    public = tmp_path / "public.git"
    _git(tmp_path, "init", "-q", "--bare", str(public))
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "core.autocrlf", "false")
    _commit(work, "snapshot")
    _git(work, "remote", "add", "public", public.as_posix())
    version = next(
        line.split('"')[1]
        for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
        if line.startswith("version = ")
    )

    result = _release(work, "--dry-run", version)

    assert result.returncode == 0, result.stderr
