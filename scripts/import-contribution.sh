#!/usr/bin/env bash
# FactoryPulse contribution import: bring an accepted pull request from the
# `public` repository into `dev` as one commit.
#
#   bash scripts/import-contribution.sh <pr-number> <ticket-path>
#
# <ticket-path> is the contribution ticket, relative to the repository root
# (.scratch/<feature>/issues/NN-<slug>.md). The commit message starts with
# `IMPL:` and names that path, so a review's default scope picks it up. The
# commit credits every author of the pull request's commits with a
# Co-authored-by trailer, and adds a line naming them under the `### Contributed`
# heading of the changelog's `## Unreleased` section. The release that
# publishes that line closes the pull request, naming its tag
# (scripts/release.sh). Every check runs before anything changes, and a failed
# one exits 1 with "import refused: <reason>".
set -euo pipefail

usage() { echo "usage: scripts/import-contribution.sh <pr-number> <ticket-path>" >&2; exit 2; }
refuse() { echo "import refused: $*" >&2; exit 1; }

[[ $# -le 2 && "${1:-}" =~ ^[1-9][0-9]*$ ]] || usage
number="$1"
ticket="${2:-}"

cd "$(git rev-parse --show-toplevel)"

# ---- Preflight -------------------------------------------------------------

[[ -n "$ticket" ]] || refuse "missing ticket path"
[[ "$ticket" =~ ^\.scratch/[^/]+/issues/[0-9]{2}-[^/]+\.md$ && -f "$ticket" ]] \
  || refuse "$ticket is not an open ticket file"

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
title="$(gh pr view "$url" --json title --jq .title)" || refuse "cannot read the title of $url"
co_authors="$(gh pr view "$url" --json commits \
  --jq '.commits[].authors[] | "\(.name) <\(.email)>"' | awk 'NF && !seen[$0]++')" \
  || refuse "cannot read the commits of $url"
[[ -n "$co_authors" ]] || refuse "pull request #$number has no commit author"

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
patch="$scratch/patch"
gh pr diff "$url" > "$patch" || refuse "cannot read the diff of $url"
git apply --check "$patch" 2>/dev/null || refuse "pull request #$number does not apply to dev"
# The import rewrites CHANGELOG.md from the copy read above, which would drop
# the pull request's own changelog changes. Applying the patch to a scratch
# index catches an edit, a deletion and a rename alike.
GIT_INDEX_FILE="$scratch/index" git read-tree HEAD
GIT_INDEX_FILE="$scratch/index" git apply --cached "$patch"
GIT_INDEX_FILE="$scratch/index" git diff --cached --quiet HEAD -- CHANGELOG.md \
  || refuse "pull request #$number edits CHANGELOG.md"

# ---- Import ----------------------------------------------------------------

git apply --index "$patch"

names="$(sed 's/ <[^>]*>$//' <<<"$co_authors" | paste -sd ',' - | sed 's/,/, /g')"
has_heading="$(awk '$0 == "## Unreleased" { inside = 1; next }
  inside && /^## / { exit } inside && $0 == "### Contributed" { print 1; exit }' <<<"$changelog")"
# ENVIRON, not -v: awk -v would interpret backslashes in the title.
ENTRY="- $title ([#$number]($url)), contributed by $names." awk -v has="$has_heading" '
  BEGIN { entry = ENVIRON["ENTRY"] }
  gap { gap = 0; if ($0 != "") print "" }
  armed {
    armed = 0
    if ($0 == "") { print; print entry; next }
    print entry
  }
  { print }
  done { next }
  /^## / { inside = ($0 == "## Unreleased") }
  !inside { next }
  !has { print ""; print "### Contributed"; print ""; print entry; gap = done = 1 }
  has && $0 == "### Contributed" { armed = done = 1 }
  END { if (armed) { print ""; print entry } }
' <<<"$changelog" > CHANGELOG.md
git add CHANGELOG.md

{
  printf 'IMPL: import public pull request #%s: %s (%s)\n\n%s\n\n' \
    "$number" "$title" "$ticket" "$url"
  sed 's/^/Co-authored-by: /' <<<"$co_authors"
} | git commit -q -F -

echo "imported $url as $(git rev-parse --short HEAD)"
