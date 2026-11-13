---
garden: .scratch/garden/02-2026-11-12/garden.md
verdict: pass
---

# Review: garden 02, re-review of fix round 0c0776b

Range: `e4593a6..0c0776b`, one `REGARDEN:` commit. It changes docs only:
`.scratch/factorypulse/spec.md` (one line) and the garden record.

Spec source: the garden record's `## Decisions`, D1-D11, and the gardener's
job. The Spec axis checks each `G` change against the code and its decision,
and each question's framing.

Standards source: the workflow writing rules, `docs/agents/issue-tracker.md`
§Garden record, `docs/agents/gotchas/README.md` §Entry rule.

Severity for a docs-only change: a false statement of present fact in a living
doc, or a question that hid an effect of its edit, is `major`. An imprecise
statement, or a framing error that leaves the answer unchanged, is `minor`.

**Standards:** pass. One `minor` finding still open (S1). D11, G11 and the
`## Log` line match §Garden record. The new spec line uses glossary words
(Baseline, z-score) and names no file or code symbol. **Spec:** pass. G11
applies D11's chosen text word for word, and the text is true of the tests.
Three `minor` findings open (P2, P3, P4). `tests/test_documentation.py`
passes (24 passed, 1 skipped).

## Open findings

- **P2 · minor · 2026-11-12** — `.scratch/garden/02-2026-11-12/garden.md:67-71`
  (D3, re-asked). The question says "The spec's Data quality decision owns the
  coverage list" and "Completing the list duplicates the spec". The spec's
  list (`.scratch/factorypulse/spec.md:96`) omits the `event_id` uniqueness
  check (`src/factorypulse/quality/expectations.py:131`) and the checks
  against the fact table (`expectations.py:141-160`). The stated trade-off is
  inaccurate; the chosen "such as" wording holds either way. The spec's
  coverage list is a gap no open ticket owns: triage decides.
- **P3 · minor · 2026-11-12** — `.scratch/garden/02-2026-11-12/garden.md:136-137`
  (D9) and `:166-168` (D10, re-asked). D9 says the spec's Data quality decision
  reads "at ingestion and after transformation"; it reads "at ingestion and
  post-dbt" (`.scratch/factorypulse/spec.md:96`). D10 says "only the script,
  tests/test_release.py and the architecture guide" name `scripts/release.sh`;
  `scripts/import-contribution.sh:11` names it too. Neither error changes the
  answer.
- **P4 · minor · 2026-11-12** — `.scratch/garden/02-2026-11-12/garden.md:188-191`
  (D11). The "Fix the term only" option says "mocked/fixtured" is something
  "the tests do not do". `tests/test_anomaly_core.py:105` overrides
  `MIN_BASELINE_WINDOWS` through pytest's `monkeypatch` fixture. The
  override value comes from the module (`MIN_BASELINE_WINDOWS // 2`), so the
  chosen spec line (`.scratch/factorypulse/spec.md:105`) stays true. The
  question's statement about these three parameters holds; the option's
  general claim about the tests does not. The answer does not change.
- **S1 · minor · 2026-11-12** — `docs/agents/gotchas/windows-host.md:15`.
  The entry points at "the README's virtualenv steps". The README has no
  section of that name: the `venv` and `pip install` lines are under
  `## Tests` (`README.md:144-151`). G2 (`garden.md:202-205`) repeats the
  name. Violated: Writing rules, "one term for one thing"; a pointer names its
  target as the target names itself.

## Coverage

Each `G` change to its evidence:

- G1 `docs/agents/gotchas/dbt.md:21-25`: `pip show jinja2` in `.venv` gives
  "Required-by: altair, great_expectations, pydeck"; `altair` and `pydeck`
  come with `streamlit`. No requirements file or `pyproject.toml` declares
  `jinja2`. The entry has 5 lines, with rule, reason and detect string.
- G2 `docs/agents/gotchas/windows-host.md:12-15`: the README's install line
  (`README.md:151`) matches the text it replaces. Pointer wording: S1.
- G3 `CONTEXT.md:4-5`: matches D4's recommended text.
- G4 `CONTEXT.md:45-46`: windows are hourly (`spark/anomaly_detection.py`,
  `WINDOW_SECONDS`) or ISO weeks (`mrt_machine_weekly`); no code computes a
  rolling window. Matches D1. No open spec uses "rolling" after G11.
- G5 `CONTEXT.md:58-60`: the code also checks row count, uniqueness,
  unit-to-sensor agreement and sums against the fact table
  (`src/factorypulse/quality/expectations.py:50-160`). Matches D3. Framing: P2.
- G6 `.scratch/factorypulse/spec.md:15`: the checked tables are exactly the
  raw table and the dbt tables, with no check on `mrt_anomaly_scores`
  (`src/factorypulse/quality/expectations.py:204-212`;
  `tests/test_data_quality.py:499`). Matches D9 and story 18
  (`spec.md:53`). Framing: P3.
- G7 `.scratch/factorypulse/spec.md:63`: the dashboard plots the hourly
  average of temperature and vibration per machine
  (`src/factorypulse/dashboard.py:18,36-40`). Matches D5.
- G8 `.scratch/factorypulse/spec.md:99`: `compose.yaml` exists and no
  `docker-compose.yml` does; tests read `compose.yaml`
  (`tests/test_airflow_dag.py:697`, `tests/test_data_quality.py:571`).
  Matches D6.
- G9 `.scratch/repo-release/spec.md:109-110`: every credential in
  `compose.yaml` is `${VAR:-}` (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`,
  `AIRFLOW_JWT_SECRET`), and `.env.example` templates each one. Matches D7.
- G10 `.scratch/repo-release/spec.md:160-161`: `.scratch/factorypulse/issues/`
  does not exist (ticket 10 is in `closed/`); Out of Scope keeps the CI/CD
  home (`spec.md:151-152`). Matches D8.
- G11 `.scratch/factorypulse/spec.md:105`: matches D11's chosen text word for
  word. The Baseline's length is `BASELINE_HOURS` and the z-score thresholds
  are `Z_WARNING` and `Z_CRITICAL` (`src/factorypulse/anomaly_core.py:24-33`).
  Both anomaly test files import them (`tests/test_anomaly_core.py:13-23`,
  `tests/test_anomaly_detection.py:30,35`), and the boundary cases are built
  from them (`tests/test_anomaly_core.py:114-121`). No test uses a literal
  Baseline length or threshold. Framing: P4.
- No-edit decisions: D2 and D10 produce no change, as answered.
- Checked and unchanged: the gotcha index lists all six area files; ADR 0001
  is not edited.

No `G` change adds build status to a spec. No `G` change leaves a gotcha or
`CONTEXT.md` false about the code.
