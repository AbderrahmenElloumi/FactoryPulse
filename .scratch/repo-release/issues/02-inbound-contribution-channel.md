# 02: Inbound contribution channel

**What to build:** an outside contributor can report a problem, contribute a fix, and see it credited — on a project whose development line they cannot see.

**Blocked by:** 01 Release pipeline

Status: `ready-for-agent`

- [ ] The public repository carries the triage labels, matching the vocabulary document exactly, so triage never writes a label that does not exist.
- [ ] The issue templates are reachable on the public repository and use filenames the platform recognises.
- [ ] The pull request template is detected by the platform.
- [ ] The contributing guide explains, to someone who cannot see the development repository, how to open a pull request, what happens to it after it is accepted, and which release will carry it.
- [ ] One contribution is imported into the development line, credited as a co-author in the commit and by name in the changelog entry of the release that carries it, and its pull request is closed naming that release.
- [ ] An inbound issue that needs design work becomes a ticket in the internal tracker, with both records referencing each other.

## Current state

- Blocked by 01 because it needs the public repository to exist.
- Verification differs from 01: walk one contribution end to end and confirm it reached the public tree with credit. 01 is verified by the script's refusals and a dry-run.
- Creating the labels is a one-off maintainer action on the platform. Everything else is verifiable from the repository.

## Log

2026-10-13 · triage · - · split from 01 · -
