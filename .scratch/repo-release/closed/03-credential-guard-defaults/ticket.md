# 03: Credential guard catches secrets in compose defaults

**What to build:** the release refuses a `compose.yaml` that carries a credential in any form compose reads, including an interpolation default, so that no secret reaches the public tree behind a `${VAR:-...}`.

GitHub: https://github.com/AbderrahmenElloumi/FactoryPulse/issues/1

**Blocked by:** none

Status: `closed`

- [x] A name counts as a credential when it contains `PASSWORD`, `PASSWD`, `SECRET`, `TOKEN`, `CREDENTIAL` or `ROOT_USER`, or ends in `_KEY`. The rule applies to the name of a setting and to the name of an interpolated variable, wherever the interpolation stands, a command string included.
- [x] A credential may read only `$VAR`, `${VAR}`, an empty default (`${VAR:-}`, `${VAR-}`) or a required form (`${VAR:?message}`, `${VAR?message}`). Every other form is refused with the reason `credential embedded in compose.yaml`: a literal value, a non-empty default (`${VAR:-secret}`, `${VAR-secret}`), an alternative value (`${VAR:+secret}`).
- [x] A credential in a quoted list item, or under a quoted key, is refused the same way.
- [x] A value that holds a user and a password in a URL (`scheme://user:password@host`) is refused the same way, whatever its name.
- [x] A non-credential default (an endpoint, a bucket name, a path) still passes, and the repository's own compose file passes.
- [x] The drift check also sees a variable interpolated without braces (`$VAR`) and an interpolation that follows an escaped dollar (`$$${VAR}`). An escaped `$$VAR` is still not an interpolation.

## Current state

- The name rule is wide on purpose. A secret the guard misses is published for good; a name it refuses wrongly costs one rename. Names are matched in upper case.
- The inbound issue stays open until the release that carries this change.
- The guard reads `compose.yaml` as compose parses it (`docker compose config --no-interpolate`, every profile), not as text. The maintainer chose this over patching a text scanner form by form.
- The release needs the docker CLI with its compose plugin, not a running daemon. A `compose.yaml` that compose cannot read is refused. The release tests skip without the docker CLI.
- The `.venv` Python walks the parsed file; `RELEASE_PYTHON` overrides it, for the scan and the suite alike.
- Every key is a setting name, whatever its characters. In the lists compose reads as `NAME=value` settings (`environment`, build `args`, `labels`, `annotations`, `sysctls`), the text before an item's first `=` is a setting name too. An `=` in any other list names no setting. Every list item is also checked whole under its list's key.
- A credential setting with an empty value passes: it embeds nothing.
- A URL's password may be one of the allowed interpolation forms, of any variable. Every other password is refused, whatever the setting's name.
- The refusal names the setting or the variable, or the key that holds the URL. It never prints the value.

## Log

2026-11-11 · impl · ca0ef19 · created from inbound issue #1 · -
2026-11-12 · triage · 365dbda · contract settled: credential names, allowed forms, drift forms; takes P3 and P4 of the closed review of ticket 01; the issue closes at the release, not with the ticket; ready-for-agent · -
2026-11-13 · impl · fd49881 · guard scans settings, interpolations and URL passwords; drift sees `$VAR` and `$$${VAR}` · -
2026-11-13 · review · d72ffa7 · block (P1, P3) · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · fix · 49da15f · fixed P1, P3, S1, S3; P2, S2 open · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · rereview · bbac6ac · block (P4, P5) · fixed P1, P3, S1, S3 · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · fix · a1fd4b2 · fixed P4, P5, P2, S2, S4, S5 · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · rereview · fa3148a · block (P6) · fixed P4, P5, P2, S2, S4, S5 · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · fix · f957add · fixed P6, S6, S7; P7 closed by decision (wide URL rule kept); P8 open for triage · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · rereview · 9f32a46 · block (P9) · fixed P6, S6, S7; P7 open (no maintainer decision), P8 open for triage · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · fix · 39ba2c3 · fixed P9, S8; P7, P8 open for triage · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
2026-11-13 · rereview · - · pass · fixed P9, S8 · P7, P8, P10 open, no ticket · .scratch/repo-release/closed/03-credential-guard-defaults/review.md
