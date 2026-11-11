---
ticket: .scratch/agent-docs/closed/02-condense-closed-tickets/ticket.md
verdict: pass
---

# Review: ticket 02 — Condense the closed tickets and reviews

**Final verdict:** pass, on the first review of `ca7842e` (range `1cfbc14..434e406`; `434e406` is a triage amendment of the criteria and `docs/agents/issue-tracker.md`).

**Standards:** no hard violation in the condensed files. Three `minor` calls stay open (S1-S3). The story and the duplicated facts in ticket 02's own `## Current state` are cut by the close.

**Spec:** every checklist item holds. Two `minor` findings stay open (P1, P2).

## Open findings

- **S1 · minor · 2026-11-09** — open, no ticket. The IDs this round assigned in review 06, `S-6` to `S-8` (`.scratch/factorypulse/closed/06-airflow-orchestration/review.md:20-22`), break the `S1`, `S2`… format of `docs/agents/issue-tracker.md` §Review file. The same lines and `:31-32` extend the severity with "accepted risk", "possible Shotgun Surgery" or "coverage"; the allowed values are `blocker`, `major`, `minor`. The older IDs (`P-2`, `T-5`, `V-1`, `W-1`) keep their original form by §Review file.
- **S2 · minor · 2026-11-09** — open, no ticket. At-least-once raw ingestion (the stream appends, the fact deduplicates) is stated in `.scratch/factorypulse/closed/04-source-to-lake/ticket.md:16` and again in `.scratch/factorypulse/closed/06-airflow-orchestration/ticket.md:62`. Writing rules: "State each fact once". Ticket 04 owns it; ticket 06 can name it.
- **S3 · minor · 2026-11-09** — open, no ticket. `.scratch/factorypulse/closed/06-airflow-orchestration/ticket.md:55` and `:59` restate the DAG schedules, retries, run limits, service list and UI port. The code holds them and the tests in review 06 `## Coverage` pin them. Writing rules: "Do not restate what the code or a test already says. Name the test." Judgement call: keep only what a later ticket needs, such as the `api-server` and the absent login.
- **P1 · minor · 2026-11-09** — open, no ticket. The ~28 s wait on an unreachable MinIO is an open finding held in `.scratch/factorypulse/closed/12-lake-read-module/ticket.md:29`, with no ID and no entry in review 12. Spec: "every `minor` finding still open … gets an ID"; the owner of an open finding is the review's `## Open findings`. Its disposition also changed: the old review 12 said "Ticket 09 should decide"; the new text says "open, no ticket", and ticket 09 does not mention it.
- **P2 · minor · 2026-11-09** — open, no ticket. `.scratch/factorypulse/closed/06-airflow-orchestration/ticket.md:75` says fix `00f94f0` fixed "the first review's minor findings". Rereview `fc7e5d6` records the `post-dbt` and `common` names and the cadence strings as deferred; they are open now as S-7 and S-8. Spec: the Log is "rebuilt from the git history"; issue-tracker §Ticket layout: "The result names the finding IDs fixed or deferred".

## Coverage

Doc ticket: no behaviour to test. Checklist item to proof:

| Checklist item | Proof |
| --- | --- |
| Ten closed tickets: contract unchanged except ticks, `## Current state` checked against code, `## Log` rebuilt; no `## Comments` | Scripted diff of each old contract (`git show 1cfbc14:<old path>`) against the new one: ticks only. Current state bullets checked at HEAD (DAG schedules, `FACTORYPULSE_HOST_DIR` refusal, weekly tag selection, `merge_into_delta`, `TABLE_COLUMNS`, `LakeTableMissing`, dashboard `delta_table_exists`). Every Log SHA exists and its prefix fits the role; every commit of `git log -- <old path>` is on a Log line, except two cosmetic edits of ticket 07 (`0e091e0`, `62c8e76`). P2 open |
| Five reviews condensed; each open `minor` has an ID and a disposition | Front-matter points at `closed/`; verdict and axis lines present; all 141 cited test names exist in `tests/`; dropped findings sampled as fixed at HEAD; open ones sampled as still open. S1, P1 open |
| Open findings with no ticket listed in the commit message; no ticket invented | `git show -s ca7842e` matches the five reviews' open IDs; no new ticket file |
| Moved with `git mv` to `closed/<NN>-<slug>/` | `git show --stat ca7842e`: one commit, no rename recorded, as amended by `434e406` |
| Old gotchas file mentions point to area files | No `docs/agents/gotchas.md` in `closed/`; cited entries exist in `dbt.md`, `airflow.md`, `delta.md`, `windows-host.md` |
| Open tickets 09, 10, 14 untouched | `git show --stat ca7842e` |
| Nothing lost | Old facts sampled against their owners; the new `compose.yaml:152-153` comment holds: `apache/kafka:4.1.1` has no `kafka-topics.sh` on its PATH (`docker run … command -v`), and `kafka-init` calls it by absolute path (`compose.yaml:165`) |

Gotcha area touched (`compose.yaml`): every `docs/agents/gotchas/docker.md` entry still holds. Host suite (implementer's run): 358 passed, 19 skipped.
