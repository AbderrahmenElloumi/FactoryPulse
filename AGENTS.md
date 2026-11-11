# Agent Skills

## Issue tracker

Issues and specs live as markdown files under `docs/agents/`-recorded convention `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

## Triage labels

Canonical roles map 1:1 to label strings; spec/tickets carry a `Status:` line, e.g. `ready-for-agent`. See `docs/agents/triage-labels.md`.

## Workflow

The implementer, reviewer and gardener rules live outside this repo, in the maintainer's workflow prompts. Each prompt carries the rules its run needs. Ticket, review and garden record layout: `docs/agents/issue-tracker.md`.

## Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Working preferences

gotchas (`docs/agents/gotchas/README.md`), host-change consent, no Microsoft Store, Caveman full mode; dev-branch workflow; in a session, abandon subagents if failing more than one time due to harness/agent/model error, work on your own for the rest of the session.
