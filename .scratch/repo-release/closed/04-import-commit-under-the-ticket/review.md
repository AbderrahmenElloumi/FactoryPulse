---
ticket: .scratch/repo-release/closed/04-import-commit-under-the-ticket/ticket.md
verdict: pass
---

# Review: 04 contribution import commits under its ticket

**Final verdict:** pass, on the first review of `6d1b9ab` (range `80902ea..6d1b9ab`).

**Standards:** no documented standard is broken. The ticket-path checks run before the branch and tree checks, every `gh` call and every git write, so the header line "Every check runs before anything changes" holds. One `minor` judgement call (S1).

**Spec:** all four checklist items are met and each has a test. Exit 1 for a missing ticket path follows the ticket's `## Current state`. Two `minor` findings (P1, P2).

Runs: `tests/test_contribution.py` gives 41 passed and 3 skipped. The 3 skips are the opt-in GitHub tests (`FACTORYPULSE_GITHUB_TESTS=1`). No Docker test touches this change.

## Open findings

- **P1 · minor · 2026-11-13** — open, no ticket. `scripts/import-contribution.sh:30`. The feature segment `[^/]+` matches `.` and `..`. `.scratch/../issues/09-x.md` and `.scratch/./issues/09-x.md` pass the pattern, and the import accepts them when the resolved file exists. Neither is an open ticket file. Ticket: "refuses ... a path that is not an open ticket file". The path stays inside the repository, and only the maintainer supplies it. Fix: `[^/.][^/]*` for the feature segment, and a `TICKET_REFUSALS` case for `..`.
- **P2 · minor · 2026-11-13** — open, no ticket. `tests/test_contribution.py:159`. `## Current state`: "The ticket path is relative to the repository root." The script gets this from `cd "$(git rev-parse --show-toplevel)"` (`scripts/import-contribution.sh:25`). Every `_import` runs from the repository root, so no test runs the import from a subdirectory.
- **S1 · minor · 2026-11-13** — open, no ticket. Possible Mysterious Name. `tests/test_contribution.py:395-397`. `["7", TICKET, TICKET]` is a wrong argument count with a valid number, but it sits under `test_import_refuses_a_missing_or_malformed_pull_request_number`. Rename the test to cover the usage error, or move the case to its own test.

## Coverage

Checklist item to test (`tests/test_contribution.py`):

| Checklist item | Tests |
| --- | --- |
| 1. Ticket path and number; `IMPL:` message names path, number, title, link | `test_import_commits_the_pull_request_with_its_authors_as_co_authors` |
| 2. Refuses a missing path and a path that is not an open ticket file | `test_import_refuses_an_argument_that_names_no_open_ticket` [missing, empty, absent, closed, not a ticket, directory] |
| 3. Commit holds only the patch and its changelog line | `test_import_commit_holds_only_the_patch_and_the_changelog_line` |
| 4. Co-author credit and changelog entry unchanged | `test_import_commits_the_pull_request_with_its_authors_as_co_authors` (trailers), `test_import_credits_the_authors_by_name_under_unreleased`, `test_a_second_import_joins_the_existing_contributed_section`, `test_import_credits_under_unreleased_whatever_the_blank_lines` [4 shapes] |

Rejection branches:

| Branch | Tests |
| --- | --- |
| Missing or empty ticket path (exit 1, no side effects, no `gh` call) | `test_import_refuses_an_argument_that_names_no_open_ticket` [missing, empty] |
| Not an open ticket file (exit 1, no side effects, no `gh` call) | `test_import_refuses_an_argument_that_names_no_open_ticket` [absent, closed, not a ticket, directory]; `.` and `..` segments not refused (P1) |
| Missing or malformed number, too many arguments (exit 2) | `test_import_refuses_a_missing_or_malformed_pull_request_number` |
| Preflight, `gh` and patch refusals with a ticket path | `test_import_refuses_a_broken_state_with_a_named_reason_and_no_side_effects`, `test_import_refuses_a_pull_request_that_renames_the_changelog` |
