# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings and the `closed` lifecycle state)
- Reviews are one file per ticket at `.scratch/<feature-slug>/reviews/<NN>-<slug>.md`
- A closed ticket and its review live in one folder per ticket: `.scratch/<feature-slug>/closed/<NN>-<slug>/ticket.md` and `review.md`. Numbers never change, so a `Blocked by:` line still resolves.
- A garden run and its review live in one folder per garden: `.scratch/garden/<NN>-<YYYY-MM-DD>/garden.md` and `review.md` (see §Garden record).

## Ticket layout

A ticket file has three parts, in this order. It holds what is true now, not
how it got there: git history and the review file hold the story.

1. **Contract.** The body the ticket was created with: title, `What to
   build`, `Blocked by`, `Status`, the acceptance criteria, and any
   `Implementation Decisions` or `Testing Decisions` sections. After
   creation, only the checkboxes and `Status:` change, except that triage
   corrects a stale fact and says so in its `## Log` line.
2. **`## Current state`.** Edited in place, never appended to. It holds the
   decisions taken during the work that still hold, and the current blocker
   if there is one. A decision that is reversed is deleted, not struck
   through. No `file:line` references and no code snippets: they go stale.
   Name the concept or the test instead.
3. **`## Log`.** One line per round, newest last:
   `YYYY-MM-DD · <role> · <commit> · <result> · <review path or ->`.
   Roles: `impl`, `fix`, `review`, `rereview`, `triage`, `garden`,
   `regarden`, matching the commit prefixes `IMPL:`, `FIX:`, `REVIEW:`,
   `REREVIEW:`, `TRIAGE:`, `GARDEN:`, `REGARDEN:`. The result names the finding IDs
   fixed or deferred, e.g. `block (P1) · fixed S2 · S3 -> 14`.
   On the line for the commit you are making, write `-` as the commit: a
   commit cannot contain its own hash. `git log` on the file gives it.

State each fact once. Write what is true now, not how it was found.

## Review file

One file per ticket, rewritten on every review round, never appended to.

- The file starts with this front-matter. `ticket:` is the literal ticket
  path, or `none`. A missing review file counts as `verdict: block`.

  ```yaml
  ---
  ticket: .scratch/<feature>/issues/NN-<slug>.md
  verdict: pass | block
  ---
  ```

- `## Open findings`: every finding still open, whichever round raised it.
  Each finding has a stable ID (`S1`, `S2`… for Standards; `P1`, `P2`… for
  Spec), the date it was raised, a severity (`blocker`, `major`, `minor`), and
  a `file:line` citation.
- On a re-review, check every earlier open finding against the code. Fixed:
  drop it from the file and name it in the ticket's `## Log` line. Still
  open: keep it with its original ID and date. Moved to another ticket: drop
  it and name the ticket in the `## Log` line.
- In a closed review, triage drops a finding it fixes, or edits the
  disposition of one it decides, and names it in its `## Log` line.
- `## Coverage`: the checklist item to test map, and the rejection branches
  with their tests.
- Earlier rounds are read from git (`git show <sha>:<path>`), not kept in
  the file.

## Closing a ticket

The reviewer that passes a ticket also condenses it:

- **Ticket:** the contract with every box ticked, `## Current state` cut to
  the decisions later tickets depend on, and the `## Log`.
- **Review:** the front-matter, the final verdict, one summary line per axis,
  the `## Coverage` map, and any `minor` finding still open with the ticket
  it moved to.
- Move both files with `git mv` in the same commit: the ticket to
  `.scratch/<feature-slug>/closed/<NN>-<slug>/ticket.md`, the review to
  `.scratch/<feature-slug>/closed/<NN>-<slug>/review.md`. Point the review's
  `ticket:` front-matter and the ticket's `## Log` review paths at the new
  paths.
- Git does not follow a condensed file across the move: the new text shares
  too little with the old one, so `git log --follow` stops at the close. Read
  the history before the close with `git log -- <old issues/ or reviews/
  path>`, or `git show` the hashes on the `## Log` lines. One commit per close
  stays the rule.

## Garden record

A garden run checks the living docs (the open features' `spec.md`,
`CONTEXT.md`, the gotcha files) against the code. Frozen working material,
such as `.scratch/design.md`, is out of scope. A garden has no ticket.

- **Folder:** `.scratch/garden/<NN>-<YYYY-MM-DD>/`. `NN` counts from `01`, like
  ticket numbers. The date is the day the first round ran. Neither changes
  when later rounds run on other days.
- **Files:** always `garden.md` (the record) and `review.md` (its review).
- **One open garden at a time.** Fix and review rounds work on the open
  garden: the folder whose `garden.md` says `status: open`. A new garden takes
  the next number, and only once the previous one is closed.

The record starts with:

```yaml
---
garden: NN
started: YYYY-MM-DD
status: open | closed
---
```

- `## Scope`: the files read.
- `## Decisions`: every question put to the maintainer, **exactly as it was
  asked**, with its options and the answer. A reviewer checks the framing as
  well as the answer.
- `## Changes`: one line per statement changed, moved or deleted, with a
  stable ID (`G1`, `G2`…), the file, and the reason. A fix round edits the
  lines in place and adds new IDs; it does not append a second list.
- `## Log`: one line per round, as in a ticket, each with its own date.
  Roles `garden`, `regarden`, `review`, `rereview`, `triage`.

Its review is `review.md` in the same folder, in the §Review file format,
with `garden: .scratch/garden/<NN>-<YYYY-MM-DD>/garden.md` in the
front-matter instead of `ticket:`. The Spec axis checks each change against
the code and against its decision; the Coverage map is each `G` change to its
evidence.

A pass sets `status: closed`. Nothing moves: the folder is already the
archive.

## Two trackers

This repo has two trackers, split by where the work comes from. The rule is
written here because it is the one that gets violated by accident.

- **`.scratch/`** holds the specs and the internal tickets. Tickets here are
  written by the maintainer, carry acceptance criteria, and are worked
  blockers-first.
- **GitHub Issues** on the public repository hold anything arriving from
  outside: bug reports, feature requests, questions.

Cross-reference both ways. A ticket file records the inbound issue it came from
on a `GitHub:` line near the top; the GitHub issue records the ticket path in a
comment. An inbound issue that needs design work becomes a `.scratch` ticket,
and the two are closed together. An inbound issue that is a one-line fix is
fixed directly and closed with the release that carries it.

The private development repository's own GitHub Issues stay disabled: for
private work, `.scratch/` is the tracker.

## Blocking

A ticket records its prerequisites on a `Blocked by:` line near the top,
listing ticket numbers. A ticket is unblocked when every ticket it lists is
`closed`. A blocker in another feature directory is written as a path, e.g.
`Blocked by: ../factorypulse/issues/10-documentation-repo.md`.

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly. A closed ticket is at `closed/<NN>-<slug>/ticket.md`, not under `issues/`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
