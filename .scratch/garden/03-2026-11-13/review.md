---
garden: .scratch/garden/03-2026-11-13/garden.md
verdict: pass
---

# Review: garden 03, re-review of c3dd052

Range: `a9ebf1a..c3dd052`, one `REGARDEN:` commit. It changes
`.scratch/factorypulse/spec.md` and the garden record. Both paths are allowed
for a `REGARDEN:` commit.

Spec source: the garden record's `## Decisions`, D1-D3, and the gardener's job.
Standards source: the workflow writing rules, `docs/agents/issue-tracker.md`
§Garden record, `docs/agents/gotchas/README.md` §Entry rule.

Severity for a docs-only change: a false statement of present fact in a living
doc, or a question that hid an effect of its edit, is `major`. An imprecise
statement, or a framing error that leaves the answer unchanged, is `minor`.

**Standards:** pass. Three `minor` findings (S1, S2, S3). D3 records its
question, options and answer; G2 is edited in place; the `## Log` line matches
§Garden record. **Spec:** pass. P1 and P2 are fixed: every phrase of the new
coverage list states a check the code runs, and no kind of check is missing.
Two `minor` findings (P3, P4). `tests/test_documentation.py` passes
(27 passed, 1 skipped: the Docker-daemon test).

## Open findings

- **P3 · minor · 2026-11-13** — `.scratch/garden/03-2026-11-13/garden.md:48-49`
  (D1). The stated effect, "the spec names every refusal a release can hit and
  the one tool it needs", overstates the edit. The script also refuses with
  "docker compose cannot read compose.yaml", "cannot scan compose.yaml with
  $python" and "cannot reach public" (`scripts/release.sh:164-168,178`; tested
  at `tests/test_release.py:283-290`). The release also needs a Python for the
  compose scan (`release.sh:155-168`) and `gh` to close credited pull requests
  (`release.sh:217-223`). The edited spec text lists checks, not refusals, and
  every check it names exists (`release.sh:136-183`), so the spec stays true.
  The answer does not change.
- **P4 · minor · 2026-11-13** — `.scratch/factorypulse/spec.md:96` (G2, D3).
  "The fact agrees with the raw lake" and "dim_machine and both marts agree
  with the fact" use "agree" for two different relations. The fact against the
  raw lake is one-way: every fact `event_id` is in the raw lake, and the fact
  has no more rows than the raw lake has events
  (`src/factorypulse/quality/expectations.py:125-136`). The dim and marts
  against the fact is equality: the same machine set, and `reading_count` sums
  to the fact's row count (`expectations.py:141-161`). Both statements are
  true; a reader can take the first as equality. Violated: Writing rules, "one
  term for one thing".
- **S1 · minor · 2026-11-13** — `.scratch/repo-release/spec.md:73-74` (G1). "A
  release tree with every required path and no excluded one" introduces
  "release tree". The spec calls the same thing the public tree (stories 20-21,
  `spec.md:52-53`; "What the public tree contains", `spec.md:123`). The script's
  refusal text says "release tree" (`scripts/release.sh:149,151`), which is the
  likely source. Violated: Writing rules, "one term for one thing".
- **S2 · minor · 2026-11-13** — `.scratch/repo-release/spec.md:74` (G1). The
  agreed text adds the file name `compose.yaml` to `spec.md`. Violated: Writing
  rules, Target documents, `spec.md` holds "no file paths". The spec already
  names `scripts/release.sh` and `.env.example`, and D1 showed the exact text,
  so triage decides whether the rule or the agreed text gives way.
- **S3 · minor · 2026-11-13** — `.scratch/factorypulse/spec.md:96` (G2, D3).
  "Both marts" means `mrt_machine_hourly` and `mrt_machine_weekly`. The
  `CONTEXT.md` glossary entry Mart (`CONTEXT.md:38-39`) also counts anomaly
  scores, and the spec names `mrt_anomaly_scores` on the next line
  (`spec.md:97`). That table has no quality checks
  (`expectations.py:204-210`; `tests/test_data_quality.py:236-237`). Naming
  the hourly and weekly marts removes the doubt. Violated: Writing rules, use
  the `CONTEXT.md` glossary words.

## Coverage

Each `G` change to its evidence:

- G1 `.scratch/repo-release/spec.md:72-80`: matches D1's chosen text word for
  word. Each named check exists in the preflight block
  (`scripts/release.sh:136-183`): on `main` (`:136`), clean tree (`:137`),
  version (`:139-141`), changelog heading (`:143-145`), excluded and required
  paths (`:147-152`), embedded credential (`:169-170`), undeclared variable
  (`:172-175`), `public` remote and tag (`:177-179`), suite (`:181-183`). The
  compose checks parse `docker compose config --no-interpolate` output
  (`:164-165`); the header (`:11-12`) says no daemon is needed. Named reason
  and no side effects: `tests/test_release.py:294-308`. Wording: S1, S2.
  Framing: P3.
- G2 `.scratch/factorypulse/spec.md:96`: matches D3's chosen text word for
  word. Table-level: built and stores every declared column
  (`src/factorypulse/quality/__init__.py:72-78`; `tests/test_data_quality.py:216-233,479-486`);
  row count (`expectations.py:50-51`, upper bound on the fact `:125-129`);
  the fact against the raw lake (`:125-136`); `dim_machine`, the hourly and
  the weekly mart against the fact (`_against_the_fact` `:141-161`, wired at
  `:168,190,208-209`; `tests/test_data_quality.py:383-419`). Column-level:
  never null (`:43-45`), value ranges (`:82-90,169-173`, mart statistics
  `:180-198`), allowed values (`:57-71`), unique `event_id` (`:131`),
  unit-to-sensor (`:72-80`), machine-to-site (`:104-112`). No check uses a
  percentage bound. D3's stated effect holds. Wording: P4, S3.
- G3 `docs/agents/gotchas/windows-host.md:12-15`: `README.md:144` is
  `## Tests`, and its `pip install` line is `README.md:151`. Fixes S1 of
  garden 02's review.
- Checked and unchanged: the docker entry forbidding `${VAR:?message}`
  (`docs/agents/gotchas/docker.md:10`) and the release guard that accepts that
  form (`scripts/release.sh:60,73`) do not contradict each other. `CONTEXT.md`
  "Release" (`CONTEXT.md:64-65`) matches the script. ADR 0001 is not edited.

No `G` change adds build status to a spec or leaves a gotcha or `CONTEXT.md`
false about the code.
