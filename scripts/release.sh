#!/usr/bin/env bash
# FactoryPulse release: publish `main` to the `public` remote as one squashed
# commit, tagged v<version>, whose single parent is the current public tip.
#
#   bash scripts/release.sh [--dry-run] <X.Y.Z>
#
# Every preflight check runs before anything is built or pushed, and a failed
# one exits 1 with "release refused: <reason>". --dry-run builds and reports
# the commit without pushing. RELEASE_TEST_CMD overrides the suite command.
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

# A compose setting whose name marks a credential.
CREDENTIAL='^[[:space:]]*-?[[:space:]]*[A-Z0-9_]*(PASSWORD|SECRET|ACCESS_KEY|ROOT_USER|TOKEN)[A-Z0-9_]*[[:space:]]*[:=]'

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

compose="$(committed compose.yaml)"
embedded="$(grep -E "$CREDENTIAL" <<<"$compose" \
  | sed -E 's/^[[:space:]]*-?[[:space:]]*([A-Z0-9_]+)[[:space:]]*[:=][[:space:]]*/\1 /' \
  | awk '$2 != "" && $2 !~ /^["'\'']?\$\{/ { print $1; exit }')"
[[ -z "$embedded" ]] || refuse "credential embedded in compose.yaml: $embedded"

# `$${VAR}` is an escaped dollar for the container shell, not interpolation.
interpolated="$(grep -oE '\$+\{[A-Za-z_][A-Za-z0-9_]*' <<<"$compose" \
  | grep -vE '^\$\$' | sed 's/^\${//' | sort -u || true)"
declared="$(committed .env.example | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' | sort -u)"
undeclared="$(comm -23 <(echo "$interpolated") <(echo "$declared") | grep . | paste -sd ' ' - || true)"
[[ -z "$undeclared" ]] || refuse ".env.example does not declare: $undeclared"

git remote get-url public >/dev/null 2>&1 || refuse "no remote named public"
public_tags="$(git ls-remote --tags public "refs/tags/$tag")" || refuse "cannot reach public"
[[ -z "$public_tags" ]] || refuse "$tag already tagged on public"

if [[ -n "${RELEASE_TEST_CMD:-}" ]]; then
  suite="$RELEASE_TEST_CMD"
elif [[ -x .venv/Scripts/python.exe ]]; then
  suite=".venv/Scripts/python.exe -m pytest -q"
elif [[ -x .venv/bin/python ]]; then
  suite=".venv/bin/python -m pytest -q"
else
  suite="python3 -m pytest -q"
fi
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
