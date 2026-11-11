#!/usr/bin/env bash
# FactoryPulse contribution import: bring an accepted pull request from the
# `public` repository into `dev` as one commit.
#
#   bash scripts/import-contribution.sh <pr-number>
#
# The commit credits every author of the pull request's commits with a
# Co-authored-by trailer, and adds a line naming them under the `### Contributed`
# heading of the changelog's `## Unreleased` section. The release that
# publishes that line closes the pull request, naming its tag
# (scripts/release.sh). Every check runs before anything changes, and a failed
# one exits 1 with "import refused: <reason>".
set -euo pipefail

usage() { echo "usage: scripts/import-contribution.sh <pr-number>" >&2; exit 2; }
refuse() { echo "import refused: $*" >&2; exit 1; }

[[ $# -eq 1 && "$1" =~ ^[1-9][0-9]*$ ]] || usage
number="$1"

cd "$(git rev-parse --show-toplevel)"

# ---- Preflight -------------------------------------------------------------

[[ "$(git symbolic-ref --short -q HEAD || true)" == dev ]] || refuse "not on dev"
[[ -z "$(git status --porcelain)" ]] || refuse "dirty working tree"

remote="$(git remote get-url public 2>/dev/null)" || refuse "no remote named public"
[[ "$remote" =~ ^https://github\.com/([^/]+/[^/]+)$ ]] \
  || refuse "public is not a GitHub repository: $remote"
url="https://github.com/${BASH_REMATCH[1]%.git}/pull/$number"

changelog="$(tr -d '\r' < CHANGELOG.md)"
grep -qx '## Unreleased' <<<"$changelog" || refuse "no Unreleased heading in CHANGELOG.md"

state="$(gh pr view "$url" --json state --jq .state 2>/dev/null)" || refuse "cannot read $url"
[[ "$state" == OPEN ]] || refuse "pull request #$number is $state"
title="$(gh pr view "$url" --json title --jq .title)"
co_authors="$(gh pr view "$url" --json commits \
  --jq '.commits[].authors[] | "\(.name) <\(.email)>"' | awk 'NF && !seen[$0]++')"
[[ -n "$co_authors" ]] || refuse "pull request #$number has no commit author"

patch="$(mktemp)"
trap 'rm -f "$patch"' EXIT
gh pr diff "$url" > "$patch"
git apply --check "$patch" 2>/dev/null || refuse "pull request #$number does not apply to dev"

# ---- Import ----------------------------------------------------------------

git apply --index "$patch"

names="$(sed 's/ <[^>]*>$//' <<<"$co_authors" | paste -sd ',' - | sed 's/,/, /g')"
has_heading="$(awk '$0 == "## Unreleased" { inside = 1; next }
  inside && /^## / { exit } inside && $0 == "### Contributed" { print 1; exit }' <<<"$changelog")"
# ENVIRON, not -v: awk -v would interpret backslashes in the title.
ENTRY="- $title ([#$number]($url)), contributed by $names." awk -v has="$has_heading" '
  BEGIN { entry = ENVIRON["ENTRY"] }
  { print }
  done { next }
  $0 == "## Unreleased" { inside = 1; next }
  !inside { next }
  has && $0 == "### Contributed" { armed = 1; next }
  (armed || !has) && $0 == "" {
    if (!has) { print "### Contributed"; print "" }
    print entry
    if (!has) print ""
    done = 1
  }
' <<<"$changelog" > CHANGELOG.md
git add CHANGELOG.md

{
  printf 'Import public pull request #%s: %s\n\n%s\n\n' "$number" "$title" "$url"
  sed 's/^/Co-authored-by: /' <<<"$co_authors"
} | git commit -q -F -

echo "imported $url as $(git rev-parse --short HEAD)"
