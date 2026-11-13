---
ticket: .scratch/repo-release/closed/06-prepare-release-1-0-2/ticket.md
verdict: pass
---

# Review: 06 prepare release 1.0.2

**Final verdict:** pass, on the first review of `7773aef` (range `aefbcb3..7773aef`). No other commit in the range.

**Standards:** no documented standard is broken. Two `minor` judgement calls (S1, S2). Both start in the ticket contract, not in the implementer's text.

**Spec:** all five checklist items are met. Each of the four entry lines is true of the code that `git diff v1.0.1 HEAD` carries. The entry holds exactly the four changes the contract names; the development line carries other changes a visitor can see (P1, `minor`).

Runs: the full suite gives 586 passed, 36 skipped. `test_the_repository_tree_passes_every_release_check` runs and passes with the docker CLI present. Public issue #1 exists, is open, and reports the defect the credential line describes.

## Open findings

- **P1 · minor · 2026-11-13** — open, no ticket. `CHANGELOG.md:10-26`. Checklist item 3: "one line for each change the development line carries beyond `v1.0.1`". The entry has the four changes the item names. `git diff v1.0.1 HEAD` also carries these, with no line: the release needs the docker CLI with its compose plugin and refuses with `docker compose cannot read compose.yaml` (`scripts/release.sh:164-166`); `RELEASE_PYTHON` selects the Python of the release (`scripts/release.sh:154-162`); the glossary's **Window** is fixed to a calendar boundary (`CONTEXT.md:45-46`); the tracker and label documents under `docs/agents/` state the inbound-item rules. Triage decides whether the contract's list is complete, before the promotion to `main`.
- **S1 · minor · 2026-11-13** — open, no ticket. `CHANGELOG.md:24`. "The release refuses a credential": the glossary defines **Release** as "a version of the project published from a tagged commit" (`CONTEXT.md:64`), and says "Use these words exactly". The release script refuses. The wording copies checklist item 3. Fix: "The release script refuses".
- **S2 · minor · 2026-11-13** — open, no ticket. `pyproject.toml:7`, `CHANGELOG.md:16-17`. The changelog header declares Semantic Versioning. A patch version holds backward-compatible fixes; the import script's argument changes from a pull request alone to a ticket path. The contract fixes the version at 1.0.2. The bump holds if the maintainer's scripts are outside the public interface: triage decides, and the decision belongs in the spec.

## Coverage

Checklist item to test:

| Checklist item | Tests |
| --- | --- |
| 1. Package metadata declares 1.0.2 | `test_the_repository_tree_passes_every_release_check` [reads the version from `pyproject.toml`, dry-runs the release on a copy of the tree]; the literal `1.0.2` has no test, by the ticket's decision |
| 2. `## [1.0.2] - YYYY-MM-DD` directly under an empty `## Unreleased` | heading for the declared version: same test, through the preflight's `no changelog heading for` check. Placement and the empty `## Unreleased`: no test, by the ticket's decision; read at `CHANGELOG.md:8-10` |
| 3. One line per change, under Keep a Changelog headings | no test, by the ticket's decision; each line read against `git diff v1.0.1 HEAD` (P1) |
| 4. The credential line links public issue #1 | no test, by the ticket's decision; read at `CHANGELOG.md:26` |
| 5. No other file changes; suite green | `git show --stat 7773aef` lists `CHANGELOG.md`, `pyproject.toml` and the ticket; 586 passed, 36 skipped |

Rejection branches: the change adds none.
