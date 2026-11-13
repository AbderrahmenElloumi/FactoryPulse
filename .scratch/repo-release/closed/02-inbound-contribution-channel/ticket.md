# 02: Inbound contribution channel

**What to build:** an outside contributor can report a problem, contribute a fix, and see it credited — on a project whose development line they cannot see.

**Blocked by:** 01 Release pipeline

Status: `closed`

- [x] The public repository carries the triage labels, matching the vocabulary document exactly, so triage never writes a label that does not exist.
- [x] The issue templates are reachable on the public repository and use filenames the platform recognises.
- [x] The pull request template is detected by the platform.
- [x] The contributing guide explains, to someone who cannot see the development repository, how to open a pull request, what happens to it after it is accepted, and which release will carry it.
- [x] One contribution is imported into the development line, credited as a co-author in the commit and by name in the changelog entry of the release that carries it, and its pull request is closed naming that release.
- [x] An inbound issue that needs design work becomes a ticket in the internal tracker, with both records referencing each other.

## Current state

- The public repository carries the six vocabulary labels next to GitHub's default labels; the maintainer chose to keep the defaults. Issue templates apply `needs-triage` only.
- Credit uses the commits' name and email, not the GitHub login.
- The import writes the changelog entry itself, so it refuses a pull request that edits, deletes or renames the changelog. The contributing guide tells contributors to leave the changelog unchanged.
- The release closes each pull request linked under `### Contributed` in the released changelog entry. It names each pull request it fails to close after publishing, and exits non-zero.
- The checks against the live repository are opt-in. Template detection uses GitHub's GraphQL template fields, because the community profile reports no issue template for an `ISSUE_TEMPLATE/` directory.

## Log

2026-10-13 · triage · 11bccc7 · split from 01 · -
2026-11-11 · impl · c9c4604..6200479 · labels, template labels, contributing guide, import script, release closes credited pull requests; v1.0.0 and v1.0.1 published; PR #3 walked; issue #1 to ticket 03 · -
2026-11-11 · review · 6352378 · block (P1, P2) · .scratch/repo-release/closed/02-inbound-contribution-channel/review.md
2026-11-11 · fix · 8c8d6a4 · fixed P1, P2, P4, S2 · .scratch/repo-release/closed/02-inbound-contribution-channel/review.md
2026-11-11 · rereview · - · pass · fixed P1, P2, P4, S2 · P3, P5, S1, S3, S4, S5, S6, S7 open, no ticket · .scratch/repo-release/closed/02-inbound-contribution-channel/review.md
2026-11-12 · triage · - · S1 -> 04 · .scratch/repo-release/closed/02-inbound-contribution-channel/review.md
