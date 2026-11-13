---
ticket: .scratch/repo-release/closed/05-shared-documents-public-side/ticket.md
verdict: pass
---

# Review: 05 shared documents read true on the public repository

**Final verdict:** pass, on the first review of `7f9263e` (range `ea5fbc4..7f9263e`). No other commit in the range.

**Standards:** no documented standard is broken. Two `minor` judgement calls (S1, S2).

**Spec:** all four checklist items are met in the documents, and each has a test. They agree with the spec's Inbound triage decision and the tracker rule. Three tests guard a narrower form than their checklist item (P1, P2, P3). Leftover ticket numbers and the internal directory name sit in published files outside this ticket's items (P4). All `minor`: each document is correct today.

Runs: `tests/test_documentation.py` and `tests/test_contribution.py` give 69 passed, 4 skipped. Each probe below was appended to or edited into the document, run against the named test, and reverted.

## Open findings

- **P1 · minor · 2026-11-13** — open, no ticket. `tests/test_documentation.py:195-203`. The test rejects only the word `ticket` and a directory name inside a `/home/me/` or `/Users/me/` path. Appended to `.env.example`, these pass: `(06)`, `T06`, `#06`, `(tickets 06)`, `/srv/DataEngProj`, `C:\Users\me\DataEngProj`, a bare `DataEngProj`. Checklist item 3: "carries no internal ticket number and no internal directory name, in its comments or in its example values." Fix: assert `"DataEngProj" not in text`, and reject `\btickets?\b` and a bare two-digit number in brackets.
- **P2 · minor · 2026-11-13** — open, no ticket. `tests/test_documentation.py:108`. The pattern catches "This repository is private." It misses "this repo is private", "The repository is private." and "This repository remains private." Checklist item 1: "A test fails when the README says that this repository is private." The literal sentence is caught, so the item holds; other wordings of the same claim pass.
- **P3 · minor · 2026-11-13** — open, no ticket. `tests/test_contribution.py:127-133`. The test pins the comment marker but not its quantifier, and pins "closed at the release that carries it" as a substring. "Some comments the agent posts start with" at `.github/CONTRIBUTING.md:51` passes, and so does "It is not closed at the release that carries it" at `:59`. Checklist item 4: "marks every comment it posts", "an accepted item is closed at the release that carries it". Fix: pin "Every comment the agent posts starts with" and "It is closed at the release that carries it".
- **P4 · minor · 2026-11-13** — open, no ticket. Published files still cite the private tracker and checkout. `dbt/README.md:1` reads "FactoryPulse dbt project (ticket 05)", which names a different ticket 05. About 40 source, compose and Docker comments outside `.scratch/` and `tests/` cite "ticket NN". `tests/test_airflow_dag.py:30` has `HOST_DIR = "/srv/checkout/DataEngProj"`. Ticket goal: "a visitor of the public repository reads documents that describe the repository they are in." The checklist names only the README, `.env.example` and the contributing guide. No open ticket owns the rest: triage decides.
- **S1 · minor · 2026-11-13** — open, no ticket. `.github/CONTRIBUTING.md:58-59`. The bullet says one fact twice: "stays open until the release that carries its change. It is closed at the release that carries it". Step 4 at `:28-32` already says it for a pull request ("stays open until the next release … closed with a comment naming the release"). Writing rule: "State each fact once." The guide is not a target document, so the rule binds only by analogy. Fix: one sentence that covers issues and pull requests.
- **S2 · minor · 2026-11-13** — open, no ticket. `tests/test_documentation.py:28-30`. `PUBLIC_REPOSITORY` and `PUBLIC_CLONE` restate `PUBLIC = "AbderrahmenElloumi/FactoryPulse"` at `tests/test_contribution.py:31`. A rename of the public repository edits three constants in two files (possible Shotgun Surgery). Fix: derive the three from one value.

## Coverage

Checklist item to test:

| Checklist item | Tests |
| --- | --- |
| 1. README speaks from the public side; a test fails on "this repository is private" | `test_readme_repository_section_speaks_from_the_public_side` [public address, "Development happens in a private repository", no "this … repository is private" in the whole README]; other wordings pass (P2) |
| 2. README says `.scratch/` records cite unpublished role rules | `test_readme_says_the_scratch_records_cite_unpublished_workflow_rules` |
| 3. `.env.example` has no ticket number or internal directory name | `test_env_example_carries_no_internal_ticket_or_directory_name` [word `ticket`, example paths under `/home/me/` and `/Users/me/` name `FactoryPulse`]; other forms pass (P1) |
| 4. Contributing guide says how an inbound item is handled | `test_contributing_guide_says_how_an_inbound_item_is_handled` [triage under the maintainer's decision, comment marker, every accepted item a ticket whatever its size, pull request read before its code runs, closed at the release]; quantifier and negation pass (P3) |

Rejection branches:

| Branch | Tests |
| --- | --- |
| README calls the repository private | `test_readme_repository_section_speaks_from_the_public_side` (`calls_itself_private`) |
| README has no Repository section | `_repository_section` assertion `the README has no Repository section` |
| `.env.example` names a ticket | `test_env_example_carries_no_internal_ticket_or_directory_name` (`\bticket\b`) |
| `.env.example` example path names another directory | same test, `set(clones) == {PUBLIC_CLONE}` |
| `.env.example` gives no example path | same test, `.env.example gives no example repository path` |
