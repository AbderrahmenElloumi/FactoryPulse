# 10: Documentation & repository

**What to build:** the polish layer — a private GitHub repository with a README that makes the project legible in ten minutes: architecture diagram, one-command setup guide, and tech-stack rationale, plus the workflow to make it public later.

**Blocked by:** 06; 07; 08; 09.

Status: `closed`

- [x] The repo is hosted on GitHub and set to private.
- [x] The README includes an architecture diagram, a setup guide (single command to run everything), and a tech-stack rationale.
- [x] Instructions exist for flipping the repo public later.
- [x] Generated data, credentials, and any cloud usage are excluded from the repository.

## Current state

Decisions later tickets depend on:

- The development repository is `FactoryPulse-prv`, private.
- The "flip public" criterion is met by the README's pointer to the release
  process in `.scratch/repo-release/spec.md`: a separate public release
  repository fed by squashed commits. The release script is repo-release
  ticket 01.
- The single command is `bash scripts/lake.sh all`: the platform with
  `docker compose up -d --build`, then `demo`, `dbt.sh run` and `anomaly`, in
  that order. Airflow stays a separate profile, started on its own.
- Compose reads every credential as `${VAR:-}`, never `${VAR:?}` (see the
  docker gotchas). The consumer refuses the empty value by name: MinIO's
  entrypoint refuses empty credentials, and the DAG file refuses an empty JWT
  secret. `.env.example` declares every variable compose interpolates.
- A developer's existing `.env` needs `AIRFLOW_JWT_SECRET` added from
  `.env.example`; compose no longer falls back to a default.
- The README and the architecture guide name only paths that exist, lake
  tables in the analytics registry, and quality checks the code runs. The
  documentation tests enforce all three.

## Log

2026-11-08 · triage · 76af654 · note added from the ticket 08 triage · -
2026-11-11 · impl · b324086 · lake.sh all, credentials from .env, README and guide from the code · -
2026-11-11 · review · 537209f · block (P1, P2) · .scratch/factorypulse/closed/10-documentation-repo/review.md
2026-11-11 · fix · 13c7fa5 · fixed P1, P2 · .scratch/factorypulse/closed/10-documentation-repo/review.md
2026-11-11 · rereview · - · pass · fixed P1, P2 · P3, P4, P5, P6, S1, S2 open, no ticket · .scratch/factorypulse/closed/10-documentation-repo/review.md
