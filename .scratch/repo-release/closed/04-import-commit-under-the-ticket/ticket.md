# 04: Contribution import commits under its ticket

**What to build:** importing an accepted pull request produces a commit that the next review picks up by default: its message starts with the implementer's first-round prefix and names the contribution ticket, and it holds only the contributor's patch and the changelog line.

**Blocked by:** none

Status: `closed`

- [x] The import takes the contribution ticket's path together with the pull request number. Its commit message starts with `IMPL:` and names that ticket path, the pull request number, its title and its link.
- [x] The import refuses a missing ticket path, and a path that is not an open ticket file, each with a named reason and no side effects.
- [x] The commit holds only the pull request's patch and its changelog line.
- [x] The co-author credit and the changelog entry are unchanged.

## Current state

- A contribution ticket takes two commits in its first round: the import commit, then the implementer's commit with the ticket edit and any added work.
- The import takes the pull request number first and the ticket path second. The ticket path is relative to the repository root.
- An open ticket file is an existing file at `.scratch/<feature>/issues/NN-<slug>.md`. A closed ticket's path is refused.
- A missing ticket path is a refusal (exit 1). A missing or malformed pull request number is a usage error (exit 2).

## Log

2026-11-12 · triage · - · created; takes S1 of the closed review of ticket 02 · -
2026-11-13 · impl · 6d1b9ab · import takes the ticket path; `IMPL:` commit names it; ticket-path refusals · -
2026-11-13 · review · - · pass · P1, P2, S1 open, no ticket · .scratch/repo-release/closed/04-import-commit-under-the-ticket/review.md
