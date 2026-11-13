# 05: Shared documents read true on the public repository

**What to build:** a visitor of the public repository reads documents that describe the repository they are in, and learns how an inbound item is handled before they open one.

**Blocked by:** none

Status: `closed`

- [x] The README's repository section speaks from the public side. It names the public repository by its address, says that development happens in a private repository, and does not call the repository it is read in private. A test fails when the README says that this repository is private.
- [x] The README's repository section says that the records under `.scratch/` cite role rules of the agent workflow that are not published.
- [x] The example environment file carries no internal ticket number and no internal directory name, in its comments or in its example values.
- [x] The contributing guide says how an inbound item is handled: an AI agent triages it under the maintainer's decision and marks every comment it posts; every accepted item becomes an internal ticket, whatever its size; a pull request is read for malicious or unsafe changes before its code runs; an accepted item is closed at the release that carries it.

## Current state

- The release tree is the promoted branch's tree, so each shared document has one text for both repositories. That text takes the public reader's side.
- The workflow rules stay outside the repository.
- An example path in `.env.example` uses the public clone's directory name, `FactoryPulse`.
- The contributing guide quotes the triage comment marker verbatim, so a reader can recognise an AI comment.

## Log

2026-11-12 · triage · - · created · -
2026-11-13 · impl · 7f9263e · done · -
2026-11-13 · review · - · pass · P1, P2, P3, P4, S1, S2 open, no ticket · .scratch/repo-release/closed/05-shared-documents-public-side/review.md
