# Contributing Guidelines

Welcome to the FactoryPulse project! We appreciate your interest in contributing to this local-first IoT predictive maintenance portfolio project.

## Scope & Philosophy

FactoryPulse is designed as a portfolio project showcasing data engineering, local-first IoT ingestion, analytics layers, and observability.

- **Personal Portfolio Scope:** We prioritize clean architecture, clear documentation, robust testing, and real-world data engineering patterns.
- **Forks Welcome:** Feel free to fork the repository, experiment, build your own extensions, or adapt it for your own portfolio needs.

## How releases work

The repository you are reading is the **release repository**. It contains tagged
releases, and its history is one commit per release. Development happens on a
private repository, so your pull request cannot be merged here in the usual way.

That is not a reason to hold back. Open the pull request against `main` anyway:

1. Fork the repository and work on a branch in your fork.
2. Open a pull request against `main` describing what problem it solves.
3. If it is accepted, the change is imported into the private development line
   as one commit, with every author of your pull request's commits credited as
   a co-author. Your name and a link to the pull request are added under
   `### Contributed` in the changelog.
4. The pull request stays open until the next release. That release carries
   your change, lists you in its `CHANGELOG.md` entry, and is tagged
   `vX.Y.Z`. The pull request is then closed with a comment naming the release
   and linking its tag. It shows as closed, not merged, because the release
   history is not the history your branch was based on.

Credit uses the name and email of your commits, so commit with the identity
you want to be credited under.

Small fixes may still be simpler as an issue: if the change is a one-liner, a
clear description in an issue is often faster than a pull request.

## Issue Tracking & Workflow

Two trackers are in use, split by where the work comes from.

- **GitHub Issues** (here) hold anything arriving from outside: bug reports,
  feature requests, questions.
- **`.scratch/`** holds the internal specs and tickets. When an inbound issue
  needs design work, it becomes a ticket there, and the two are cross-referenced.

When submitting contributions, please reference any relevant issue.

## GitHub Issue Templates

When opening issues or feature requests, please use the provided templates under `.github/ISSUE_TEMPLATE/` to help us triage and understand your request quickly.

## Getting Started

1. Fork and clone the repository.
2. Create a feature branch (`git checkout -b feat/your-feature-name`).
3. Set up your local environment following the main README instructions.
4. Implement your changes, adding tests where appropriate.
5. Ensure all tests pass.
6. Open a pull request against `main`. GitHub fills in the pull request template.

## Pull Request Guidelines

- Follow existing coding style and project structure.
- Include unit or integration tests for new features and bug fixes.
- Reference any related issues in your PR description.
- Keep commits focused and descriptive.
- Say which stage of the pipeline your change touches, so it can be verified
  against the right seam.
