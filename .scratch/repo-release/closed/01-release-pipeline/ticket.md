# 01: Release pipeline

**What to build:** the mechanism that publishes a release — a public repository fed from the private development line by a single squashed commit per version, through a script that refuses to publish an inconsistent state and can show its work without pushing.

**Blocked by:** ../factorypulse/issues/10-documentation-repo.md

Status: `closed`

- [x] A public repository exists, and the local repository reaches it through a second remote named `public`, while `origin` points at the private development repository.
- [x] The release script refuses a dirty working tree, the wrong branch, a failing test suite, a version argument that disagrees with the package metadata, and a version with no matching changelog heading — each with a named reason and no side effects.
- [x] The script's dry-run builds and reports the release commit without pushing, and that commit's tree equals the promoted branch's tree with the current public tip as its single parent.
- [x] Publishing creates exactly one new commit and one tag on the public repository, and leaves the development history untouched.
- [x] The public repository's history contains one commit per release, and the two histories cannot be merged in either direction.
- [x] No credential is embedded in the compose file; every one is declared in the example environment file and interpolated from the environment, and the release refuses if the two sets drift apart.
- [x] The published tree carries the source, tests, transformation project, orchestration, scripts, and the working material under `.scratch/` — specs, tickets, the design record, the glossary, and the decision record.
- [x] The published tree excludes credentials, generated data, virtual environments, and editor-local state, and the release refuses if any of them would be published.

## Current state

- The public repository is `AbderrahmenElloumi/FactoryPulse`, reached through the remote `public`. No release is published yet: the first one needs `dev` promoted to `main`, the version bumped in `pyproject.toml`, and a matching changelog heading. That is the maintainer's call.
- The release script runs from Git Bash with a version argument and an optional dry-run flag. It reads every file as `main`'s last commit holds it. Every refusal names its reason and exits 1; a missing or malformed version prints the usage and exits 2.
- The excluded paths cover every generated, credential and editor entry of `.gitignore`, and editor-local state that `.gitignore` does not list. A new ignore entry of that kind needs a matching exclusion and a case in `test_release_refuses_a_tree_that_would_publish_an_excluded_path`.
- The first release on an empty public repository is a root commit. Every later release has the public tip as its single parent.
- The tag `v<X.Y.Z>` exists only on the public repository. The script pushes the branch and the tag in one atomic push, creates no local tag, and refuses a version already tagged there.
- Drift means compose interpolates a variable `.env.example` does not declare. The reverse is allowed: `.env.example` also serves host processes.
- `RELEASE_TEST_CMD` overrides the suite command. The tests stub it, because the real suite would run the release tests again.

## Log

2026-10-13 · triage · fe944da · split: the inbound side moved to 02 · -
2026-11-11 · impl · b6d4122 · public repository and remote, release script with dry-run and refusals · -
2026-11-11 · review · 2d7642a · block (P1, P2) · .scratch/repo-release/closed/01-release-pipeline/review.md
2026-11-11 · fix · 6e27db3 · fixed P1, P2, P6, S2 · .scratch/repo-release/closed/01-release-pipeline/review.md
2026-11-11 · rereview · - · pass · fixed P1, P2, P6, S2 · P3, P4, P5, P7, S1, S3, S4, S5, S6 open, no ticket · .scratch/repo-release/closed/01-release-pipeline/review.md
2026-11-12 · triage · - · P3, P4 -> 03 · .scratch/repo-release/closed/01-release-pipeline/review.md
