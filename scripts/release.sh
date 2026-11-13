#!/usr/bin/env bash
# FactoryPulse release: publish `main` to the `public` remote as one squashed
# commit, tagged v<version>, whose single parent is the current public tip.
#
#   bash scripts/release.sh [--dry-run] <X.Y.Z>
#
# Every preflight check runs before anything is built or pushed, and a failed
# one exits 1 with "release refused: <reason>". --dry-run builds and reports
# the commit without pushing. RELEASE_TEST_CMD overrides the suite command;
# RELEASE_PYTHON overrides the Python that scans compose.yaml and runs the
# suite (default: .venv's, else python3). The scan needs the docker CLI with
# its compose plugin, not a running daemon.
#
# After the push, each pull request linked under `### Contributed` in this
# version's changelog entry (scripts/import-contribution.sh writes those lines)
# is closed with gh, naming the tag.
set -euo pipefail

usage() { echo "usage: scripts/release.sh [--dry-run] <X.Y.Z>" >&2; exit 2; }
refuse() { echo "release refused: $*" >&2; exit 1; }

dry_run=0
version=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    *) [[ -z "$version" ]] || usage; version="$arg" ;;
  esac
done
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || usage
tag="v$version"

cd "$(git rev-parse --show-toplevel)"

# Read a file as `main` holds it, without carriage returns.
committed() { git show "HEAD:$1" 2>/dev/null | tr -d '\r'; }

# What the public tree must never hold: credentials, generated data, virtual
# environments, editor-local state.
EXCLUDED='(^|/)\.env$|(^|/)\.?venv/|(^|/)__pycache__/|\.py[cod]$|(^|/)data/|^dbt/((target|logs|metastore_db)/|\.user\.yml$)|(^|/)derby\.log$|\.egg-info/|(^|/)(build|dist)/|(^|/)\.(vscode|idea|pytest_cache|mypy_cache)/|(^|/)\.claude/settings\.local\.json$|(^|/)(\.DS_Store|Thumbs\.db)$'

# What the public tree must hold: one ERE per item, matched against its paths.
REQUIRED=(
  '^README\.md$' '^CHANGELOG\.md$' '^pyproject\.toml$' '^compose\.yaml$'
  '^\.env\.example$' '^CONTEXT\.md$' '^src/' '^tests/' '^dbt/' '^dags/'
  '^scripts/' '^docker/' '^docs/adr/' '^docs/agents/' '^\.scratch/design\.md$'
  '^\.scratch/[^/]+/spec\.md$'
  '^\.scratch/[^/]+/(issues/[^/]+\.md|closed/[^/]+/ticket\.md)$'
)

# A name that marks a credential, matched as written (upper case). Wide on
# purpose: a missed secret is published for good, a wrong refusal costs a rename.
CREDENTIAL='PASSWORD|PASSWD|SECRET|TOKEN|CREDENTIAL|ROOT_USER|_KEY$'

# Scan compose.yaml as compose reads it. `docker compose config
# --no-interpolate` resolves anchors, merges, flow collections, explicit keys
# and multi-line scalars, and keeps every `${...}` and `$$` as written; this
# program walks its JSON. It prints `variable NAME` for each interpolated
# variable, and stops at the first embedded credential with `credential <what>`.
# A credential reads only $VAR, ${VAR}, ${VAR:-}, ${VAR-}, ${VAR:?msg} or
# ${VAR?msg}: as the value of a key or of a NAME=value item of a settings list,
# as an interpolation anywhere, and as the password of a URL. A run of an even
# number of `$` is escaped.
read -r -d '' COMPOSE_SCAN <<'PY' || true
import json
import re
import sys

CREDENTIAL = re.compile(sys.argv[1])
NAME = r"[A-Za-z_][A-Za-z0-9_]*"
# What may follow `${NAME` in an allowed interpolation: `}`, `-}`, `:-}`,
# `?msg}` or `:?msg}`.
ALLOWED_TAIL = r"(?::?-)?\}|:?\?[^}]*\}"
ALLOWED = re.compile(rf"\$(?:{NAME}|\{{{NAME}(?:{ALLOWED_TAIL}))")
INTERPOLATION = re.compile(rf"(\$+)(\{{?)({NAME})")
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")


def report_credential(what):
    print("credential", what)
    sys.exit(0)


def check_value(key, value):
    text = "" if value is None else value if isinstance(value, str) else json.dumps(value)
    if CREDENTIAL.search(key) and text and not ALLOWED.fullmatch(text):
        report_credential(key)
    for match in INTERPOLATION.finditer(text):
        dollars, brace, name = match.groups()
        if len(dollars) % 2 == 0:
            continue
        print("variable", name)
        if brace and CREDENTIAL.search(name) and not re.match(ALLOWED_TAIL, text[match.end():]):
            report_credential(name)
    for match in URL.finditer(text):
        # A value that starts with a URL holds its user information up to the
        # last `@`, spaces and slashes included. So `host:port/path/@x` reads
        # as a password and is refused: no rule tells it from `user:p/ss@host`.
        # A URL after the start of a value ends at a space.
        rest = text[match.end():]
        if match.start() > 0:
            rest = re.match(r"\S*", rest)[0]
        userinfo, at, _ = rest.rpartition("@")
        password = userinfo.partition(":")[2]
        if at and password and not ALLOWED.fullmatch(password):
            report_credential(f"password in a URL under {key}")


# The lists compose reads as NAME=value settings. Other lists, such as
# `command`, `entrypoint` and `healthcheck.test`, hold text whose `=` names no
# setting.
SETTINGS_LISTS = {"environment", "args", "labels", "annotations", "sysctls"}


# A key names the scalars under it. An item of a settings list is a setting
# named by the text before its first `=`, whatever its characters. Every list
# item is also checked whole under its list's key.
def walk(node, key):
    if isinstance(node, dict):
        for child, value in node.items():
            walk(value, child)
    elif isinstance(node, list):
        for item in node:
            if key in SETTINGS_LISTS and isinstance(item, str) and "=" in item:
                check_value(*item.split("=", 1))
            walk(item, key)
    else:
        check_value(key, node)


walk(json.load(sys.stdin), "")
PY

# ---- Preflight -------------------------------------------------------------

[[ "$(git symbolic-ref --short -q HEAD || true)" == main ]] || refuse "not on main"
[[ -z "$(git status --porcelain)" ]] || refuse "dirty working tree"

declared_version="$(committed pyproject.toml | sed -n 's/^version = "\([^"]*\)".*/\1/p' | head -n 1)"
[[ "$declared_version" == "$version" ]] \
  || refuse "version mismatch: pyproject.toml says $declared_version"

changelog="$(committed CHANGELOG.md)"
grep -qE "^## \[${version//./\\.}\]( |$)" <<<"$changelog" \
  || refuse "no changelog heading for $version"

paths="$(git ls-tree -r --name-only HEAD)"
excluded="$(grep -E "$EXCLUDED" <<<"$paths" | head -n 1 || true)"
[[ -z "$excluded" ]] || refuse "excluded path in release tree: $excluded"
for pattern in "${REQUIRED[@]}"; do
  grep -qE "$pattern" <<<"$paths" || refuse "missing from release tree: $pattern"
done

if [[ -n "${RELEASE_PYTHON:-}" ]]; then
  python="$RELEASE_PYTHON"
elif [[ -x .venv/Scripts/python.exe ]]; then
  python=.venv/Scripts/python.exe
elif [[ -x .venv/bin/python ]]; then
  python=.venv/bin/python
else
  python=python3
fi

compose="$(committed compose.yaml \
  | docker compose -f - --profile '*' config --no-interpolate --format json 2>/dev/null)" \
  || refuse "docker compose cannot read compose.yaml"
scan="$("$python" -I -c "$COMPOSE_SCAN" "$CREDENTIAL" <<<"$compose")" \
  || refuse "cannot scan compose.yaml with $python"
embedded="$(sed -n 's/^credential //p' <<<"$scan")"
[[ -z "$embedded" ]] || refuse "credential embedded in compose.yaml: $embedded"

interpolated="$(sed -n 's/^variable //p' <<<"$scan" | sort -u)"
declared="$(committed .env.example | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' | sort -u)"
undeclared="$(comm -23 <(echo "$interpolated") <(echo "$declared") | grep . | paste -sd ' ' - || true)"
[[ -z "$undeclared" ]] || refuse ".env.example does not declare: $undeclared"

git remote get-url public >/dev/null 2>&1 || refuse "no remote named public"
public_tags="$(git ls-remote --tags public "refs/tags/$tag")" || refuse "cannot reach public"
[[ -z "$public_tags" ]] || refuse "$tag already tagged on public"

printf -v suite '%q -m pytest -q' "$python"
suite="${RELEASE_TEST_CMD:-$suite}"
bash -c "$suite" >&2 || refuse "test suite failed"

# ---- Build -----------------------------------------------------------------

tip="$(git ls-remote public refs/heads/main | cut -f 1)"
parent=()
if [[ -n "$tip" ]]; then
  git fetch -q public main
  parent=(-p "$tip")
fi

notes="$(awk -v heading="## [$version]" \
  'index($0, heading) == 1 { found = 1; next } found && /^## / { exit } found' <<<"$changelog")"
tree="$(git rev-parse "HEAD^{tree}")"
commit="$(printf 'Release %s\n\n%s\n' "$tag" "$notes" | git stripspace | git commit-tree "$tree" "${parent[@]}")"

# Pull requests this release credits: links under its `### Contributed` heading.
contributed="$(awk '/^### / { inside = ($0 == "### Contributed") } inside' <<<"$notes" \
  | grep -oE 'https://github\.com/[^/ )]+/[^/ )]+/pull/[0-9]+' | awk '!seen[$0]++' || true)"

echo "release commit: $commit"
echo "tree: $tree"
echo "parent: ${tip:-none}"
echo "tag: $tag"

if (( dry_run )); then
  [[ -z "$contributed" ]] || sed 's/^/would close: /' <<<"$contributed"
  echo "dry run: nothing pushed"
  exit 0
fi

git push -q --atomic public "$commit:refs/heads/main" "$commit:refs/tags/$tag"
echo "published $tag to public"

unclosed=0
while read -r pr; do
  [[ -n "$pr" ]] || continue
  comment="Released in $tag (${pr%/pull/*}/tree/$tag), imported into the development line and credited in its changelog entry."
  gh pr close "$pr" --comment "$comment" >/dev/null || { echo "could not close: $pr" >&2; unclosed=1; }
done <<<"$contributed"
exit "$unclosed"
