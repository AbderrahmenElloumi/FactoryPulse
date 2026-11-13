---
ticket: .scratch/repo-release/closed/03-credential-guard-defaults/ticket.md
verdict: pass
---

# Review: 03 credential guard catches secrets in compose defaults

**Final verdict:** pass, on the re-review of `39ba2c3` (range `9f32a46..39ba2c3`). No other commit in the range.

**Standards:** S8 is fixed: the header comment states the settings-list rule as the code applies it. No documented standard is broken. The settings-list comment overstates how precise the rule is (part of P10).

**Spec:** P9 is fixed. A `command`, `entrypoint` or `healthcheck.test` item with a credential name before an `=` passes, and no command text is printed. Every checklist item has a test. Three `minor` findings stay open for triage (P7, P8, P10).

Runs: `tests/test_release.py` gives 128 passed. Compose v5.6.0 keeps the list form of `environment`, `args`, `labels`, `annotations` and `sysctls` in `config --format json`, so the settings-list branch runs. Each P10 case was run through `docker compose config --no-interpolate --format json` and the scan programs at `9f32a46` and `39ba2c3`.

## Open findings

- **P10 · minor · 2026-11-13** — open, no ticket. `scripts/release.sh:109-112`, `:124`. The settings-list gate matches the bare key name at any depth, not the compose path. Two effects:
  - Lists outside the set lose the item-name check that their mapping forms keep. `x-env: ["DB_PASSWORD=admin"]` and `extra_hosts: ["API_TOKEN=1.2.3.4"]` pass, while `x-env: {DB_PASSWORD: admin}` is refused. Both lists were refused at `9f32a46`. An `x-` list used through an anchor in `environment` is still refused.
  - A settings-list key inside an `x-` block is still split. `x-cfg: {labels: ["curl -H TOKEN: abc --retry=3"]}` is refused as `credential curl -H TOKEN: abc --retry`, which prints command text.

  Ticket goal: "refuses a `compose.yaml` that carries a credential in any form compose reads". `## Current state`: "It never prints the value." The comment at `:109-111` says "The lists compose reads as NAME=value settings". Triage decides whether `x-` blocks and `extra_hosts` count, and whether the gate moves to the compose path.
- **P7 · minor · 2026-11-13** — open, no ticket. `scripts/release.sh:95-106`. A value that starts with a URL holds its password up to the last `@` of the whole value. `MINIO_ENDPOINT: http://minio:9000/bucket/@scope` is refused as `password in a URL under MINIO_ENDPOINT` (`tests/test_release.py:440`), and so is `HEALTH: "http://minio:9000/health ; notify ops@example.com"`. Checklist item 5: "A non-credential default (an endpoint, a bucket name, a path) still passes." The maintainer has not decided between the wide rule and the contract.
- **P8 · minor · 2026-11-13** — open, no ticket. `scripts/release.sh:88-94`, `:118-128`. Text that compose hands on without reading it as settings is not scanned for a credential: a shell default behind an escaped dollar, `command: "sh -c 'echo $${DB_PASSWORD:-admin}'"`, and inline config content, `configs: {app: {content: "DB_PASSWORD=admin"}}`. Both pass, and the literal `admin` ships. Ticket goal: "so that no secret reaches the public tree behind a `${VAR:-...}`". Checklist item 6 says an escaped `$$VAR` is not an interpolation.

## Coverage

Checklist item to test (`tests/test_release.py`):

| Checklist item | Tests |
| --- | --- |
| 1. Credential names, settings and interpolations, command strings | `test_release_refuses_a_credential_embedded_in_compose` [non-empty default(s), alternative value, literal around an interpolation, name with SECRET, name with CREDENTIAL, name ending in _KEY, interpolated variable under another name, interpolation in a command string, flow mapping, flow sequence, value on the next line, the nine P4 forms, list item named with a hyphen, with a dot, with a space before the equals sign, build argument named with a hyphen, build label, label, annotation, sysctl]; REFUSALS `credential embedded in compose.yaml: MINIO_ROOT_USER` |
| 2. Allowed and refused forms | `test_release_accepts_a_compose_that_embeds_no_credential` [bare variable, braced variable, empty default without colon, required, required without colon, quoted list item, empty values, interpolation on the next line, flow mapping]; refusals [non-empty default, non-empty default without colon, alternative value] |
| 3. Quoted list items and quoted keys | refusals [unquoted, double-quoted and single-quoted list item, quoted key, single-quoted key] |
| 4. Password in a URL | refusals [password in a URL, with a slash, with a space, inside a command, before an equals sign in a command]; accepted [interpolated password in a URL] |
| 5. Non-credential defaults and the repository's compose pass | accepted [non-credential defaults, escaped dollar, credential name before an equals sign in a command, credential setting in a healthcheck]; `test_the_repository_tree_passes_every_release_check`; endpoint with a port and a later `@` refused (P7) |
| 6. Drift | `test_release_refuses_an_undeclared_interpolation` [bare variable, interpolation after an escaped dollar, interpolation before an equals sign]; accepted [escaped dollar, credential setting in a healthcheck] |

Rejection branches and declared behaviours:

| Branch | Tests |
| --- | --- |
| Credential key (`scripts/release.sh:86-87`) | `test_release_refuses_a_credential_embedded_in_compose` [setting, P4 and P6 cases]; `test_release_refuses_a_broken_state_with_a_named_reason_and_no_side_effects` (`_embedded_credential`) |
| Settings-list item name (`scripts/release.sh:124-125`) | refusals [list item cases, build argument, build label, label, annotation, sysctl]; other lists pass: accepted [credential name before an equals sign in a command, credential setting in a healthcheck] |
| Whole list item under its list's key (`scripts/release.sh:126`) | refusals [password in a URL before an equals sign in a command]; drift [interpolation before an equals sign] |
| Nested collections (`scripts/release.sh:118-128`) | refusals [second item of a flow mapping, flow mapping inside a flow mapping, flow mapping inside a flow sequence] |
| Credential interpolation (`scripts/release.sh:88-94`) | refusals [interpolated variable under another name, interpolation in a command string] |
| URL password (`scripts/release.sh:95-106`) | refusals [password in a URL, with a slash, with a space, inside a command, before an equals sign in a command, endpoint with a port and a later @] |
| Empty-value pass, comment skip | accepted [empty values, commented credential] |
| Compose cannot read the file (`scripts/release.sh:164-166`) | REFUSALS `docker compose cannot read compose.yaml` [publish, dry-run] |
| Scan fails (`scripts/release.sh:167-168`) | REFUSALS `cannot scan compose.yaml with missing-python` [publish, dry-run] |
| Undeclared interpolation | `test_release_refuses_an_undeclared_interpolation`; `test_release_refuses_a_broken_state_with_a_named_reason_and_no_side_effects` (`_undeclared_variable`) |
| No docker CLI | module skip in `tests/test_release.py` (`pytestmark`) |
