---
ticket: .scratch/repo-release/closed/01-release-pipeline/ticket.md
verdict: pass
---

# Review: 01 release pipeline

**Final verdict:** pass, on the re-review of `6e27db3` (range `2d7642a..6e27db3`).

**Standards:** no documented standard is broken. S2 is fixed: the ticket's `## Current state` describes the invocation in prose. Three `minor` findings from the first review stay open (S1, S3, S4). Two new `minor` judgement calls (S5, S6). The close rewrites the excluded-paths bullet: `EXCLUDED` covers more than `.gitignore` lists (`.vscode`, `.idea`, `.mypy_cache`), so "mirror" was false.

**Spec:** all eight checklist items are met. P1 is fixed: the `cannot reach public` case points `public` at a missing bare repository, passes every earlier check, and refuses at `scripts/release.sh:81`. P2 is fixed: `EXCLUDED` (`scripts/release.sh:33`) covers every generated, credential and editor entry of `.gitignore`, and matches no tracked path. P6 is fixed: both path tests run in publish and dry-run modes. Four `minor` findings stay open (P3, P4, P5, P7).

Runs: `tests/test_release.py` 64 passed. `git remote -v` shows `origin` on FactoryPulse-prv and `public` on FactoryPulse. The current `main` tracks `.claude/settings.local.json`, so a release from `main` refuses on the excluded path until `dev` is promoted.

## Open findings

- **P3 · minor · 2026-11-11** — moved to `.scratch/repo-release/issues/03-credential-guard-defaults.md`. `scripts/release.sh:45`, `:70`. The embedded-credential guard passes any value that starts with `${`, so `MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-factorypulse-dev-pass}` publishes a secret as a default. It also passes quoted list items (`- "MINIO_ROOT_PASSWORD=admin"`), quoted keys, and names outside its list (`*_PASSWD`, a DSN with `user:pass@`). Spec: "No credential is embedded in the compose file". The current `compose.yaml` passes honestly.
- **P4 · minor · 2026-11-11** — moved to `.scratch/repo-release/issues/03-credential-guard-defaults.md`. `scripts/release.sh:74-75`. The drift check sees only `${VAR}`. It misses `$VAR` without braces, and drops `$$${VAR}` (an escaped dollar before a real interpolation). Spec: "the release refuses if the two sets drift apart."
- **P5 · minor · 2026-11-11** — open, no ticket. `scripts/release.sh:36-42`. `REQUIRED` has no entry for `spark/` (the Spark jobs are source) and none for `docs/agents/gotchas/`; `^docs/agents/` is met by any one file. Spec: "The source, … the gotcha files included."
- **P7 · minor · 2026-11-11** — open, no ticket. `docs/architecture-guide.md:17`. The guide describes `scripts/` as "driver scripts that run one compose service per step, and their shared job runner". `release.sh` is neither, so the guide is false about `scripts/`.
- **S1 · minor · 2026-11-11** — open, no ticket. Possible Duplicated Code. `_bash()` (`tests/test_release.py:49-60`) repeats `tests/test_airflow_dag.py:329` with a different strategy. `_write` (`tests/test_release.py:83`) repeats `tests/test_scheduler_stop.py:123`. `tests/test_suite_layout.py:3-4`: "A copy in a test module drifts". The rule names fixtures, not helpers.
- **S3 · minor · 2026-11-11** — open, no ticket. Possible Speculative Generality. `scripts/release.sh:84-92`. The suite has three fallbacks (`.venv/Scripts`, `.venv/bin`, bare `python3`). The ticket fixes Git Bash as the host, which needs only the first.
- **S4 · minor · 2026-11-11** — open, no ticket. `tests/test_release.py:410-414` parses the version with `line.split('"')[1]`. The project requires Python 3.11+, so `tomllib` reads `pyproject.toml` without a hand parser.
- **S5 · minor · 2026-11-11** — open, no ticket. Possible Duplicated Code. The `dry_run` parametrize and `_release(work, *(["--dry-run"] if dry_run else []), …)` appear three times (`tests/test_release.py:280`/`:290`, `:320`/`:327`, `:349`/`:356`). Fix: one module-level `DRY_RUN` mark and a `dry_run=` keyword on `_release`.
- **S6 · minor · 2026-11-11** — open, no ticket. Possible Data Clumps. The excluded-path cases keep paths and ids in two parallel lists (`tests/test_release.py:299-318`) that must stay in the same order by hand. Fix: `pytest.param(path, id=...)` per case.

## Coverage

Checklist item to test (`tests/test_release.py`):

| Checklist item | Tests |
| --- | --- |
| 1. Public repository and `public` remote | no test (external state); `gh repo view` reported public, empty on the first review; `git remote -v` |
| 2. Refusals with named reason and no side effects, publish and dry-run | `test_release_refuses_a_broken_state_with_a_named_reason_and_no_side_effects` [dirty working tree, not on main, test suite failed, version mismatch, no changelog heading, credential embedded, undeclared variable, no remote named public, cannot reach public] |
| 3. Dry-run tree and single parent | `test_dry_run_builds_a_root_commit_of_mains_tree_when_public_is_empty`, `test_dry_run_parents_the_release_commit_on_the_public_tip` |
| 4. One commit and one tag, development untouched | `test_publishing_creates_one_commit_and_one_tag_and_leaves_development_untouched` |
| 5. One commit per release, unmergeable both ways | `test_public_history_is_one_commit_per_release_and_cannot_merge_with_development` (the `merge-base` assertion carries the proof) |
| 6. No embedded credential, drift refused | refusal cases of item 2, `test_the_repository_tree_passes_every_release_check` (guard gaps P3, P4) |
| 7. Published content, publish and dry-run | `test_release_refuses_a_tree_missing_published_content`, `test_the_repository_tree_passes_every_release_check` (gaps P5) |
| 8. Exclusions refused, publish and dry-run | `test_release_refuses_a_tree_that_would_publish_an_excluded_path` [credentials, generated-data, dbt-user-file, egg-info, build-output, dist-output, virtual-environment, editor-state] |

Rejection branches:

| Branch | Tests |
| --- | --- |
| Missing or malformed version (exit 2) | `test_release_refuses_a_missing_or_malformed_version` |
| Version already tagged on public | `test_release_refuses_a_version_already_tagged_on_public` |
| `cannot reach public` | `test_release_refuses_a_broken_state_with_a_named_reason_and_no_side_effects[cannot reach public-*]` |
