# 02: Condense the closed tickets and reviews

**What to build:** every closed ticket and its review follow the layout in `docs/agents/issue-tracker.md` (§Ticket layout, §Review file, §Closing a ticket) and live in `.scratch/<feature>/closed/<NN>-<slug>/` as `ticket.md` and `review.md`. An agent that lists `issues/` sees only live work. A closed ticket shows its contract, the decisions later tickets depend on, and a log, with no superseded statements.

**Blocked by:** 01 Split and verify the gotchas.

Status: `closed`

- [x] Each closed ticket in `.scratch/factorypulse/issues/` (01, 02, 03, 04, 05, 06, 07, 11, 12, 13) has three parts:
  - its contract, unchanged except for the ticked boxes
  - a `## Current state` holding only the decisions that still hold and that later tickets depend on, each checked against the code
  - a `## Log` with one line per round, rebuilt from the git history and the old `## Comments` (commit SHAs, roles, verdicts)

  The `## Comments` section is gone.
- [x] Each review in `.scratch/factorypulse/reviews/` for a closed ticket (06, 07, 11, 12, 13) is condensed. It keeps the front-matter, the final verdict, one summary line per axis, the `## Coverage` map, and every `minor` finding still open. Each of those findings gets an ID and either the ticket it moved to or "open, no ticket".
- [x] A finding that is still open, still relevant, and has no ticket is listed in the commit message, so the maintainer can decide whether to open a ticket. No new ticket is invented.
- [x] The condensed tickets and reviews are moved with `git mv` to `.scratch/factorypulse/closed/<NN>-<slug>/ticket.md` and `review.md`. A closed ticket with no review gets only `ticket.md`.
- [x] Any mention of the old gotchas file in the moved files points to the right area file under `docs/agents/gotchas/`.
- [x] Open tickets (08, 09, 10, 14) stay in `issues/` and are not condensed: they already use the new layout. A ticket that closes before this one runs is condensed and moved by its own reviewer.
- [x] Nothing the old text said that still holds is lost: each surviving fact is in its owner (the table in the implementer prompt's Writing rules section).

## Current state

- None: each fact the condensing kept lives in its owner (the closed tickets and reviews, `docs/agents/issue-tracker.md` §Closing a ticket, the `compose.yaml` comment).

## Log

2026-11-09 · triage · e462342 · created from the doc-hygiene grilling session · -
2026-11-09 · impl · ca7842e · 10 tickets and 5 reviews condensed and moved to closed/; host 358 passed, 19 skipped · -
2026-11-09 · triage · 434e406 · criterion amended: git mv need not keep `--follow` history; read it from the old path · -
2026-11-09 · review · - · pass · S1-S3, P1, P2 open, no ticket · .scratch/agent-docs/closed/02-condense-closed-tickets/review.md
