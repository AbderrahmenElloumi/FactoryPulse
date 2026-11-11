# 03: Credential guard catches secrets in compose defaults

**What to build:** the release refuses a `compose.yaml` that carries a credential in any form compose reads, including an interpolation default, so that no secret reaches the public tree behind a `${VAR:-...}`.

GitHub: https://github.com/AbderrahmenElloumi/FactoryPulse/issues/1

**Blocked by:** none

Status: `needs-triage`

- [ ] A credential written as an interpolation default (`${VAR:-secret}`, `${VAR-secret}`) is refused with the reason `credential embedded in compose.yaml`; an empty default (`${VAR:-}`) still passes.
- [ ] A credential in a quoted list item, or under a quoted key, is refused the same way.
- [ ] The set of setting names that count as a credential is decided and written down, and a non-credential default (an endpoint, a bucket name) still passes.
- [ ] The inbound issue is closed together with this ticket.

## Current state

- Design question open: which setting names count as a credential. Too wide refuses legitimate defaults; too narrow misses `*_PASSWD` and DSNs carrying `user:pass@`.

## Log

2026-11-11 · impl · - · created from inbound issue #1 · -
