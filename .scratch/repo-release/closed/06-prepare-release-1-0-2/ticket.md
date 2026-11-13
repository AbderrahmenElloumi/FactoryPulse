# 06: Prepare release 1.0.2

**What to build:** the development line declares version 1.0.2 and carries its changelog entry, so that the maintainer can promote `dev` to `main` and publish `v1.0.2` with the release script.

**Blocked by:** none

Status: `closed`

- [x] The package metadata declares version `1.0.2`.
- [x] `CHANGELOG.md` has a `## [1.0.2] - YYYY-MM-DD` heading directly under the `## Unreleased` heading, and `## Unreleased` stays, empty.
- [x] The 1.0.2 entry has one line for each change the development line carries beyond `v1.0.1`, grouped under Keep a Changelog headings: the contribution import refuses a pull request that edits the changelog; the import commit is made under its ticket; the release refuses a credential embedded in `compose.yaml` in any form compose reads, including an interpolation default; the README, the contributing guide and `.env.example` read true on the public repository.
- [x] The credential line links public issue #1.
- [x] No other file changes. The test suite stays green.

## Current state

- A release-preparation ticket is the way every release is prepared. Triage writes one per release, after the maintainer approves it.
- The entry describes what a visitor of the public repository sees change. It cites no internal ticket.
- A release-preparation ticket adds no test for the version or the heading: the release script's preflight checks both on `main`.
- A line that closes a path by which a secret reaches the public tree stands under `### Security`.
- The maintainer promotes `dev` to `main` and runs the release. Triage then closes public issue #1 with a comment that names the tag.

## Log

2026-11-13 · triage · aefbcb3 · created · -
2026-11-13 · impl · 7773aef · version 1.0.2 and its changelog entry · -
2026-11-13 · review · - · pass · P1, S1, S2 open, no ticket · .scratch/repo-release/closed/06-prepare-release-1-0-2/review.md
