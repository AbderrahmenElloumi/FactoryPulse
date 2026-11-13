---
ticket: .scratch/repo-release/closed/02-inbound-contribution-channel/ticket.md
verdict: pass
---

# Review: 02 inbound contribution channel

**Final verdict:** pass, on the re-review of `8c8d6a4` (range `6352378..8c8d6a4`).

**Standards:** no documented standard is broken. S2 is fixed: `## Current state` holds decisions only. Four `minor` findings from the first review stay open (S1, S3, S4, S5). Two new `minor` judgement calls (S6, S7). The close rewrites the passive "is named after publishing" bullet in active voice.

**Spec:** all six checklist items are met. P1 is fixed: the scratch-index check refuses an edit, a deletion, a mode change and a rename of `CHANGELOG.md` before anything changes. P2 is fixed: the insert awk ends the section at the next `## ` heading, and the entry lands under `## Unreleased` / `### Contributed` for every traced shape (existing subsections, no blank lines, last line of the file, CRLF). `scripts/release.sh` still finds the link when no blank line separates it from the next heading. The "refuse when no entry was written" half of P2 is not built: the `has_heading` probe and the insert awk scan the same region, and preflight guarantees `## Unreleased`, so no input reaches that branch. P4 is fixed: `gh` failures on the title, commits and diff refuse with named reasons. P3 stays open; one new `minor` (P5).

Runs: the full suite gives 509 passed and 36 skipped. `tests/test_contribution.py` gives 32 passed and 3 skipped. The nine new cases fail against the script at `6352378` (temporary worktree, removed). Under `core.autocrlf=true`, `git apply --check` and `git apply --cached` agree on an LF patch against a CRLF working copy.

## Open findings

- **P3 · minor · 2026-11-11** — open, no ticket. `tests/test_contribution.py:481`. The ticket contract says "matching the vocabulary document exactly". The test asserts a subset (`<=`), because the maintainer kept GitHub's default labels (ticket `## Current state`). Triage corrects the stale contract wording.
- **P5 · minor · 2026-11-11** — open, no ticket. `scripts/import-contribution.sh:52-53`. `git read-tree` and `git apply --cached` on the scratch index have no `|| refuse`. `git apply --check` (`:48`) reads the working tree, so a patch can pass it and fail against the index. Reproduced by the Spec axis: an ignored `.env` in the working tree and a pull request that edits `.env` exit 1 with `error: .env: does not exist in index`, not `import refused:`. Nothing changes. The script header (`:11-12`): "a failed one exits 1 with "import refused: <reason>"". No test covers it. Fix: `|| refuse "pull request #$number does not apply to dev"`.
- **S1 · minor · 2026-11-11** — moved to `.scratch/repo-release/issues/04-import-commit-under-the-ticket.md`. `scripts/import-contribution.sh:84`, commit 733d86f. The import commit is titled `Import public pull request #N: <title>`, with no role prefix and no ticket path. Workflow §Commit prefixes: "Every commit message starts with the prefix of the role and round that made it." Under §Fixed point, a review leaves such a commit out of scope unless the maintainer names it. Triage decided for the rule: the import commit takes `IMPL:` and the ticket path.
- **S3 · minor · 2026-11-11** — open, no ticket. `tests/test_contribution.py:25`. The module imports the `repos` fixture and helpers from `test_release`, and `# noqa: F401` hides an unused `VALID_TREE`. `tests/conftest.py:1`: "Fixtures shared by more than one host test module." Move `repos` to `conftest.py`.
- **S4 · minor · 2026-11-11** — open, no ticket. `tests/test_contribution.py:37-46`. The `gh` fake ignores `--jq`, so the filters at `scripts/import-contribution.sh:36` and `:40` never run in a test. A field-name error in a later edit would still pass the suite.
- **S5 · minor · 2026-11-11** — open, no ticket. Possible Duplicated Code. `scripts/import-contribution.sh:15-16`, `:25-26` repeat `usage`, `refuse` and the branch and dirty-tree preflight of `scripts/release.sh:16-17`, `:53-54`.
- **S6 · minor · 2026-11-11** — open, no ticket. `scripts/import-contribution.sh:65-79`. The insert awk carries four state flags (`gap`, `armed`, `done`, `inside`) and an `END` insert, with no comment. Writing rules: "Why code does something unusual: a code comment next to it."
- **S7 · minor · 2026-11-11** — open, no ticket. Possible Duplicated Code. `tests/test_contribution.py:219` `ENTRY` repeats the local `entry` at `:199`. `test_import_refuses_a_pull_request_that_renames_the_changelog` (`:356-367`) copies the body of the refusal test (`:345-353`), because `REFUSALS` is keyed by reason and two cases cannot share one. Fix: key the table by case, and fold the rename case in.

## Coverage

Checklist item to test (`tests/test_contribution.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. Labels | `test_public_repository_carries_every_triage_label` (gated; subset, see P3), `test_vocabulary_holds_the_five_triage_roles_and_closed` |
| 2. Issue templates | `test_issue_templates_use_names_and_front_matter_github_recognises`, `test_issue_templates_apply_only_vocabulary_labels`, `test_github_detects_the_templates_and_guide_on_the_public_repository` (gated) |
| 3. Pull request template | the same gated test, `test_pull_request_template_uses_the_name_github_detects` (`tests/test_documentation.py`) |
| 4. Contributing guide | `test_contributing_guide_explains_the_path_of_a_pull_request` |
| 5. Contribution | `test_import_commits_the_pull_request_with_its_authors_as_co_authors`, `test_import_credits_the_authors_by_name_under_unreleased`, `test_a_second_import_joins_the_existing_contributed_section`, `test_import_credits_under_unreleased_whatever_the_blank_lines` [4 shapes], `test_publishing_closes_each_pull_request_the_release_credits_naming_its_tag`, `test_dry_run_reports_the_pull_requests_it_would_close_and_closes_none`. Live: 733d86f matches `gh pr diff 3`, the `v1.0.1` changelog credits PR #3, and PR #3 is closed naming `v1.0.1`. |
| 6. Inbound issue | `test_every_ticket_from_an_inbound_issue_is_referenced_back_by_that_issue` (gated). Ticket 03 carries `GitHub:` issue #1. |

Rejection branches:

| Branch | Tests |
| --- | --- |
| Preflight, `gh` and patch refusals, exit 1, no side effects | `test_import_refuses_a_broken_state_with_a_named_reason_and_no_side_effects` [not on dev, dirty working tree, no remote named public, public is not a GitHub repository, no Unreleased heading, cannot read, CLOSED, no commit author, cannot read the title, cannot read the commits, cannot read the diff, does not apply, edits CHANGELOG.md] |
| Changelog renamed | `test_import_refuses_a_pull_request_that_renames_the_changelog` |
| Missing or malformed number (exit 2) | `test_import_refuses_a_missing_or_malformed_pull_request_number` |
| Failed close after the push | `test_a_pull_request_that_fails_to_close_is_named_after_publishing` |
| Patch passes the working tree, fails the index | no test (P5) |
