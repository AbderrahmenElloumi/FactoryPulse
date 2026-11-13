# Repository release pipeline

Status: `ready-for-agent`

## Problem Statement

As the project's maintainer, I need the work to have a public face without
giving up a private place to develop. Developing in public means every
half-finished commit, every ticket closed before it was done, and every review
round is visible while I am still learning — but a project with no public
repository cannot be shown to an interviewer at all. I also need an outside
contributor to be able to reach the project, even though the branch they would
normally open a pull request against is private.

## Solution

Two repositories with one direction of travel.

A **private development repository** holds the work: `dev` is where changes
land, `main` is what has been promoted as release-worthy.

A **public release repository** holds only releases. Its history is one squashed
commit per release, tagged with that version, carrying a changelog entry, the
architecture guide, and a README that describes what actually exists. A script
builds and publishes each one, refusing to publish an inconsistent state.

Issues and pull requests arrive on the public repository. An accepted pull
request is imported into the private development line by patch and credited to
its author; the pull request is then closed, naming the release that carries it.

## User Stories

1. As the maintainer, I want a private repository to develop in, so that I can work through mistakes without an audience.
2. As the maintainer, I want a separate public repository that holds only releases, so that what is visible is only work I chose to publish.
3. As the maintainer, I want the private history to be untouched by publishing, so that publishing cannot rewrite work I am in the middle of.
4. As the maintainer, I want one command that builds and publishes a release, so that the ritual happens correctly when I have not done it in months.
5. As the maintainer, I want that command to refuse a broken or inconsistent state, so that no release ships with failing tests, uncommitted changes, or a version that disagrees with itself.
6. As the maintainer, I want to see the commit a release would build before it exists anywhere public, so that I can check it first.
7. As the maintainer, I want the release step documented in the spec, so that a future session can follow it without re-deriving it.
8. As a repository visitor, I want each release to be a tagged commit with its own changelog entry, so that I can cite an exact version in a report.
9. As a repository visitor, I want the release history to read as a clean list of versions, so that I can see what changed between them without reading development churn.
10. As a repository visitor, I want the README to state the architecture, the tech-stack rationale, and a single command that runs everything, so that I understand and run the project in ten minutes.
11. As a repository visitor, I want the README and the architecture guide to describe what is built rather than what is intended, so that nothing I read misleads me.
12. As a repository visitor, I want local virtualenv and test instructions, so that I can run the test suite without Docker.
13. As an outside contributor, I want issue templates that ask for the information needed to act, so that my report is actionable rather than a round trip.
14. As an outside contributor, I want to open a pull request even though development is private, so that I can contribute a fix rather than only describe it.
15. As an outside contributor, I want to be credited when my patch ships, so that contributing is worth my time.
16. As an outside contributor, I want to know which release carries my change, so that I can verify it landed.
17. As the maintainer, I want a written rule for which tracker holds what, so that inbound reports and internal tickets do not get confused.
18. As the maintainer, I want the public repository's labels to match the vocabulary the tooling uses, so that triage never writes a label that does not exist.
19. As a security-conscious maintainer, I want every credential templated into `.env.example` and interpolated by compose, so that no secret can be committed.
20. As a security-conscious maintainer, I want generated data, virtual environments, and editor-local state excluded, so that the public tree is only source.
21. As the maintainer, I want the public tree to include the specs, tickets, glossary, and decision records, so that the process behind the code is visible as evidence.
22. As the maintainer, I want version numbers to mean one thing, so that a tag never labels two different states.
23. As the maintainer, I want a place for future CI/CD work to be specified, so that it has a home without renumbering what exists.

## Implementation Decisions

**Repositories and remotes.** The development repository is private and is the
local repository's `origin`. The public repository is added as a second remote
named `public`. Branch flow: work lands on `dev`, is merged into `main` when
release-worthy, and only `main` is ever published.

**Release commit construction.** A release commit is built with `git
commit-tree` from `main`'s tree, with the current public tip as its single
parent. Consequences, accepted deliberately: the public history is one linear
sequence of releases, it shares no ancestry with the development history, the
two can never be merged in either direction, and the public repository is never
force-pushed.

**The release script.** `scripts/release.sh <version>` performs preflight checks
— clean working tree, on `main`, test suite green, package metadata version
equal to the argument, a changelog heading for that version, a release tree
with every required path and no excluded one, a `compose.yaml` that embeds no
credential and interpolates only variables `.env.example` declares, a `public`
remote that does not hold the tag yet — then builds the commit, tags it, and
pushes branch and tag to `public`. The compose checks read compose's own parse,
so a release needs the docker CLI with its compose plugin, not a running
daemon. It supports a dry-run that builds and reports the commit without
pushing. Every failed preflight exits with a named reason and no side effects.

**Importing a contribution.** An accepted pull request is imported into `dev`
as a patch, and the contributor is credited as a co-author in the commit and by
name in the changelog entry of the release that carries it. The pull request is
closed with a comment naming that release. The release repository's `main` never
receives a commit that did not come from the development line.

**Inbound triage.** Every accepted issue and every accepted pull request
becomes an internal ticket, whatever its size, and passes the same implement
and review rounds as internal work. A pull request is read for malicious or
unsafe changes before any of its code runs, and again at review. Triage is the
only role that writes to the public repository's issues and pull requests;
the maintainer confirms each action, and every comment says that an AI wrote
it. A refused enhancement is recorded, so that the same request is recognised
when it returns. An accepted item is closed at the release that carries it.

**Two trackers.** GitHub Issues on the public repository hold anything arriving
from outside; `.scratch/` holds the specs and internal tickets. The rule and the
cross-referencing convention are recorded in the tracker documentation, which is
the file that already owns tracker convention. The private repository's own
issues stay disabled.

**Labels.** The triage vocabulary document is the source of truth, and the same
strings are created as labels on the public repository. Creating them is a
one-off GitHub action performed by the maintainer, not something the tooling can
do from the local repository.

**Templates and contribution docs.** Issue templates and the contributing guide
live in the development tree and reach the public repository through the release
squash, so there is never a second copy to keep in sync. The pull request
template uses the filename GitHub actually detects.

**Secrets.** No credential is embedded in compose: each one is templated in
`.env.example` and interpolated from the environment. `.env` stays ignored.
One endpoint variable covers the difference between a container reaching MinIO
by service name and a host process reaching it on localhost.

**The published README.** Rewritten per release to describe built behaviour:
architecture diagram, tech-stack rationale, single-command quickstart, local
virtualenv and pytest instructions, and an honest statement of what each stage
does. No placeholder tokens.

**What the public tree contains.** The source, tests, dbt project, DAGs,
scripts, Dockerfiles, compose, documentation, the glossary, the ADRs, and the
working material under `.scratch/` — specs, tickets, and the design document.
Excluded: `.env`, generated data, virtual environments, and editor state.
Included on purpose: the agent docs under `docs/agents/`, the gotcha files
included, as evidence of how the work is done.

## Testing Decisions

Good tests here assert published facts and refused states, not the mechanics of
git plumbing. The surface is the release script's contract, the repository's own
invariants, and the public-facing documents.

- **Release script, dry-run:** the preflight refuses each broken state
  separately — dirty tree, wrong branch, failing suite, version argument that
  disagrees with package metadata, changelog with no matching heading — each
  with a named reason and no side effects. The dry-run then asserts the built
  commit's tree equals `main`'s tree and its parent is the current public tip.
- **Repository invariants:** the pull request template exists under the name
  GitHub detects, and no file remains under the old name.
- **Secrets:** compose interpolates the MinIO variables rather than embedding
  values, and `.env.example` declares every variable compose interpolates, so
  the two cannot drift.
- **Documentation honesty:** the README carries no placeholder tokens and does
  not name a component the repository does not contain.
- **Prior art:** the existing tests that read repository files and assert
  consistency are the model — the documentation tests and the test that locks
  the dbt models against the analytics registry. These are cheap, fast, and
  catch exactly the class of defect this project has already produced once.

## Out of Scope

- CI/CD workflows. Deferred; this feature directory is where they will be
  specified when picked up.
- Mirroring the development repository's full history to the public one.
- Publishing container images to a registry.
- Governance documents: code of conduct, security policy, funding metadata.
- Multi-maintainer review requirements or branch protection rules.

## Further Notes

- Tags live only in the public repository, so a version number always means
  exactly one thing.
