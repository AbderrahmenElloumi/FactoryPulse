---
garden: 02
started: 2026-11-12
status: closed
---

# Garden 02 (started 2026-11-12)

## Scope

- Gotchas: `docs/agents/gotchas/README.md`, `airflow.md`, `dbt.md`,
  `delta.md`, `docker.md`, `spark.md`, `windows-host.md`.
- Specs: `.scratch/factorypulse/spec.md` (no open tickets; every spec/code gap
  there has no owner), `.scratch/repo-release/spec.md` (open tickets 03, 04,
  05).
- `CONTEXT.md`.
- ADRs: `docs/adr/0001-event-contract-as-single-seam.md`.
- Checked against the code, the tests, and the tickets closed since garden 01:
  factorypulse 09, 10, 14; repo-release 01, 02.
- Skipped: `.scratch/design.md`, frozen working material.

## Decisions

Questions D1-D11 as the gardener asked them, with the maintainer's answers.
Each option is given as its label, then its description.

- **D1.** "Q1. CONTEXT.md, Window says: \"A rolling window moves with each
  observation; an hourly or weekly window is fixed to a calendar boundary.\" No
  code computes a rolling window. Windows are hourly or ISO-weekly. The
  Baseline (trailing hourly windows before a scored window) has its own entry.
  Edit: cut the rolling sentence, so Window reads \"A bounded span of time over
  which readings are summarised, fixed to a calendar boundary: an hour or an
  ISO week.\" Effect for readers: nobody looks for a rolling-window
  computation; the word \"rolling\" leaves the glossary. Which?" Options:
  **Cut rolling (Recommended)**: Window = calendar-bound span (hour or ISO
  week). The moving part stays in the Baseline entry. **Point rolling at
  Baseline**: Keep the word: "A rolling window moves with each scored window;
  the Baseline is one." Readers can map ticket 08's "rolling z-scores" to the
  Baseline. **Keep as is**: No change. The glossary keeps a term no code uses.
  Answer: **Cut rolling (Recommended).**
- **D2.** "Q2. CONTEXT.md has no entry for \"At-Risk Machine\", which the code
  (analytics.at_risk_machines), the dashboard heading and the README use.
  Closed review 09 left this (S3) to triage, with no ticket. Edit: add under
  Analysis \"**At-Risk Machine**: a machine whose Health Status in its latest
  window with an Anomaly Score is not nominal.\" Effect for readers: the
  dashboard term has one definition, and it says that a window without a score
  does not count. Add it?" Options: **Add the term (Recommended)**: New
  glossary entry under Analysis. Closed review 09's S3 is then settled; triage
  drops it from that review. **Leave to triage**: No glossary change in this
  garden. S3 stays open in closed review 09. Answer: **Leave to triage.**
- **D3.** First asked as: "Q3. CONTEXT.md, Quality Check: \"one named,
  falsifiable assertion about a table — a schema requirement, a value range, a
  missingness bound, or a set of allowed values.\" The code also checks a
  minimum row count, uniqueness of event_id, unit-to-sensor agreement and a sum
  compared with the fact table. The list reads as complete, so these checks
  seem to fall outside the term. Which edit?" Options: **Make it examples
  (Recommended)**: "...about a table, such as a schema requirement, a value
  range, a missingness bound, or a set of allowed values." The list stays short
  and reads as examples. **Complete the list**: Add row count, uniqueness,
  agreement between columns, agreement between tables. Exhaustive; must change
  when a new kind of check is added. **Keep as is**: No change. Answer: "Im not
  sure about this, please explain the problem even more and what consequences
  or possible conflicts could be caused by either choice." The gardener
  explained the effect of each option, then asked again: "Q3 (re-asked with
  detail). CONTEXT.md, Quality Check lists four kinds of assertion as if
  complete; the code also runs row-count, uniqueness, unit-to-sensor and
  fact-sum checks, which the glossary then excludes. The spec's Data quality
  decision owns the coverage list. \"Such as\" keeps the core definition (one
  named, falsifiable assertion about a table) and makes the list examples, with
  a looser boundary that dbt tests also fit (as they already do). Completing
  the list duplicates the spec and must change with every new kind. Keeping it
  leaves glossary and code in disagreement. Which?" Options: **Make it
  examples (Recommended)**: "...one named, falsifiable assertion about a table,
  such as a schema requirement, a value range, a missingness bound, or a set of
  allowed values." **Complete the list**: Add row count, uniqueness, agreement
  between columns, agreement between tables. Duplicates the spec's coverage
  list. **Keep as is**: No change; glossary and code keep disagreeing. Answer:
  **Make it examples (Recommended).**
- **D4.** "Q4. CONTEXT.md intro ends: \"This file defines concepts, never which
  module implements them — naming an implementation here is how it previously
  came to describe behaviour that had not been built.\" The clause after the
  dash is story (Writing rules: no story). Effect for readers of each option is
  in the option text. Which?" Options: **Present-tense reason (Recommended)**:
  "...never which module implements them: a module name here goes stale and can
  describe behaviour that is not built." The rule keeps its reason, without the
  history. **Cut the clause**: End at "never which module implements them." The
  rule stays; readers lose the reason. **Keep as is**: No change; the story
  stays. Answer: **Present-tense reason (Recommended).**
- **D5.** "Q5. .scratch/factorypulse/spec.md user story 22 asks for a dashboard
  that \"shows machine health KPIs, rolling temperatures, and anomaly flags\".
  The dashboard plots the hourly average of temperature and vibration per
  machine; closed ticket 09 decided \"The trends plot the hourly average\". No
  open ticket owns rolling temperatures, and factorypulse has no open tickets.
  Edit: replace \"rolling temperatures\" with \"hourly temperature and
  vibration trends\". Effect for readers: the story matches the built
  dashboard; nobody reads a rolling-temperature chart as owed. Which?" Options:
  **Edit the story (Recommended)**: Story 22 says "hourly temperature and
  vibration trends", as ticket 09 decided. **Open a ticket**: Keep the story;
  triage writes a factorypulse ticket for a rolling-temperature view. The spec
  stays a target the code does not meet yet. **Keep as is**: No change; the gap
  stays with no owner. Answer: **Edit the story (Recommended).**
- **D6.** "Q6. .scratch/factorypulse/spec.md Deployment decision says \"single
  `compose.yaml` (or `docker-compose.yml`)\". The repository uses compose.yaml,
  and tests and scripts read that name. Edit: cut \"(or
  `docker-compose.yml`)\". Effect for readers: the file name reads as decided,
  not open. Cut it?" Options: **Cut the alternative (Recommended)**: "single
  `compose.yaml` with services: ..." **Keep as is**: No change. Answer: **Cut
  the alternative (Recommended).**
- **D7.** "Q7. .scratch/repo-release/spec.md Implementation Decisions, Secrets:
  \"Every credential currently embedded in compose moves to `.env.example` and
  is interpolated from the environment.\" The move is done (closed ticket 10);
  \"currently ... moves\" reads as pending work (build status). Edit: \"No
  credential is embedded in compose: each one is templated in `.env.example`
  and interpolated from the environment.\" The rest of the paragraph stays.
  Effect for readers: a standing rule, not an unfinished move. Open ticket 03
  still owns which interpolation forms the release guard accepts. Change it?"
  Options: **Rewrite as rule (Recommended)**: Present-tense rule; same meaning.
  **Keep as is**: No change. Answer: **Rewrite as rule (Recommended).**
- **D8.** "Q8. .scratch/repo-release/spec.md Further Notes has three stale
  items: (a) \"Blocked by:
  `../factorypulse/issues/10-documentation-repo.md`\": dead path, ticket 10 is
  closed; (b) \"The retracted v1.0.0 tag means the first version published here
  will be v1.0.0, earned rather than declared.\": story; v1.0.0 and v1.0.1 are
  published; (c) the CI/CD note repeats Out of Scope (\"this feature directory
  is where they will be specified\"). Edit: cut (a), (b) and (c); Further Notes
  keeps \"Tags live only in the public repository, so a version number always
  means exactly one thing.\" Effect for readers: no dead link, no
  pending-sounding first release, CI/CD's home stated once. Which?" Options:
  **Cut all three (Recommended)**: Further Notes holds only the tag rule. **Cut
  (a) and (b) only**: Keep the CI/CD note next to the tag rule, as a second
  pointer. **Keep as is**: No change. Answer: **Cut all three (Recommended).**
- **D9.** "Q9. .scratch/factorypulse/spec.md Solution: \"Great Expectations
  enforces data quality at each stage.\" The code checks the raw lake and the
  dbt tables (raw_sensor_events, dim_machine, fct_sensor_readings_clean,
  mrt_machine_hourly, mrt_machine_weekly). The anomaly stage's table,
  mrt_anomaly_scores, has no quality check. The spec's own Data quality
  decision and story 18 say \"at ingestion and after transformation\". No open
  ticket owns a check on mrt_anomaly_scores. Edit: \"Great Expectations
  enforces data quality at ingestion and after transformation.\" Effect for
  readers: the Solution matches the decision; nobody reads anomaly-score checks
  as owed. Which?" Options: **Edit the Solution (Recommended)**: Solution says
  "at ingestion and after transformation", as the decision and story 18 do.
  **Open a ticket**: Keep "at each stage"; triage writes a ticket for checks on
  mrt_anomaly_scores. **Keep as is**: No change; the gap stays with no owner.
  Answer: **Edit the Solution (Recommended).**
- **D10.** First asked as: "Q10. .scratch/repo-release/spec.md Implementation
  Decisions, The release script: \"`scripts/release.sh <version>` performs
  preflight checks ...\". Writing rules: a spec has no file paths. Edit: \"The
  release script takes the version as its one argument and performs preflight
  checks ...\"; the rest stays. Effect for readers: the spec does not go stale
  if the script moves; the path stays in the README, the script header and
  closed ticket 01. Which?" Options: **Cut the path (Recommended)**: "The
  release script takes the version as its one argument and performs preflight
  checks ..." **Keep as is**: Keep the path: the command is what story 4 asks
  for, and the README and tests name it the same. Answer: "When you say story 4
  and README and tests name it, how do they do so ? I do not see the problem
  here". The question was wrong on three facts: story 4 names no path, and
  neither the README nor closed ticket 01 names the script. The README sends
  readers to this spec for the release process, and story 7 asks that the
  release step be documented in the spec. The gardener corrected the facts,
  changed the recommendation, and asked again: "Q10 (re-asked, corrected).
  .scratch/repo-release/spec.md, The release script: \"`scripts/release.sh
  <version>` performs preflight checks ...\". The writing rule says a spec has
  no file paths. But story 7 asks that the release step be documented in the
  spec so a future session can follow it, and the README sends readers to this
  spec for the release process. The README and closed ticket 01 do not name the
  script; only the script, tests/test_release.py and the architecture guide do.
  Cutting the path leaves the spec's release step with no command to run.
  Which?" Options: **Keep the path (Recommended)**: Story 7 makes the command
  part of the decision; the spec stays the place to learn how to release. No
  edit. **Cut the path**: "The release script takes the version as its one
  argument ...". Follows the no-path rule; a reader finds the command in the
  architecture guide or scripts/. Answer: **Keep the path (Recommended).**
- **D11.** "Q11. .scratch/factorypulse/spec.md, Testing Decisions, Development
  workflow (TDD), ends: \"Parameters like rolling-window size and z-score
  threshold are mocked/fixtured, never hardcoded in tests.\" Garden 02 cut
  \"rolling\" from the CONTEXT.md glossary (D1), so this spec line now uses a
  term the glossary does not define. The code has no rolling-window size: the
  parameter is the Baseline's length (BASELINE_HOURS). The tests do not mock
  these parameters either: they import BASELINE_HOURS, Z_WARNING and
  Z_CRITICAL from the module under test. Edit: \"Parameters such as the
  Baseline's length and the z-score thresholds come from the module under
  test, never from literals in tests.\" Effect for readers: the spec uses the
  glossary's word, matches how the tests work, and nobody looks for a
  rolling-window parameter or a mock. Which?" Options: **Rewrite to match
  (Recommended)**: "Parameters such as the Baseline's length and the z-score
  thresholds come from the module under test, never from literals in tests."
  Glossary term and test practice both fixed. **Fix the term only**:
  "Parameters such as the Baseline's length and the z-score thresholds are
  mocked/fixtured, never hardcoded in tests." Glossary term fixed;
  "mocked/fixtured" stays, which the tests do not do. **Keep as is**: No
  change. The spec keeps "rolling-window size", a term the glossary no longer
  defines and the code does not have. Answer: **Rewrite to match
  (Recommended).**

## Changes

- **G1** `docs/agents/gotchas/dbt.md`: the macro-rendering entry says that
  `streamlit` and `great_expectations` bring `jinja2`, not `streamlit` alone.
  `pip show jinja2` names `altair` and `pydeck` (both `streamlit` dependencies)
  and `great_expectations`.
- **G2** `docs/agents/gotchas/windows-host.md`: the `.venv` rebuild entry
  points at the `pip install` line of the README's virtualenv steps instead of
  repeating it. The README owns the install command; the interpreter path is a
  host fact and stays.
- **G3** `CONTEXT.md`: the intro gives a present-tense reason for "never which
  module implements them" instead of a story, per D4.
- **G4** `CONTEXT.md`: Window drops the rolling window; a window is an hour or
  an ISO week, per D1.
- **G5** `CONTEXT.md`: Quality Check lists its kinds as examples ("such as"),
  per D3.
- **G6** `.scratch/factorypulse/spec.md`: Solution says data quality is
  enforced at ingestion and after transformation, not at each stage, per D9.
- **G7** `.scratch/factorypulse/spec.md`: user story 22 asks for hourly
  temperature and vibration trends, not rolling temperatures, per D5.
- **G8** `.scratch/factorypulse/spec.md`: Deployment names `compose.yaml` only,
  per D6.
- **G9** `.scratch/repo-release/spec.md`: Secrets is a standing rule, not a
  pending move, per D7.
- **G10** `.scratch/repo-release/spec.md`: Further Notes keeps only the tag
  rule; the dead `Blocked by` path, the first-release story and the repeated
  CI/CD note are cut, per D8.
- **G11** `.scratch/factorypulse/spec.md`: Testing Decisions, Development
  workflow, names the Baseline's length and the z-score thresholds, taken from
  the module under test, instead of a mocked rolling-window size, per D11.
- Checked and unchanged: every other gotcha entry and the gotcha index; the
  other `CONTEXT.md` terms; the `scripts/release.sh` path in the repo-release
  spec, per D10. `docs/adr/0001-event-contract-as-single-seam.md` agrees with
  the code (`test_schema_sync.py`) and is not edited.

## Log

2026-11-12 · garden · - · G1-G10; D1-D10 asked · -
2026-11-12 · review · - · block (P1) · .scratch/garden/02-2026-11-12/review.md
2026-11-12 · regarden · - · fixed P1 (D11, G11) · .scratch/garden/02-2026-11-12/review.md
2026-11-12 · rereview · - · pass; P1 fixed; P2, P3, P4, S1 minor open · .scratch/garden/02-2026-11-12/review.md
