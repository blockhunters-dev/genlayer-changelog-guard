#!/usr/bin/env bash
# Verifies docs/WATCHTOWER_API.md against the pinned Watchtower source revision, and reports drift.
set -euo pipefail
SRC_REPO="${WATCHTOWER_REPO:-../watchlayer}"
PIN_COMMIT=ef0e47f4fe7c56325afce7d4ebaba503801d0b03
PIN_SHA=2cc5b6a14a570fbc1aea249b755bf4f237023e43df36b9efbbb1d29764222dba
here="$(cd "$(dirname "$0")/.." && pwd)/docs/WATCHTOWER_API.md"

[ "$(sha256sum "$here" | cut -d' ' -f1)" = "$PIN_SHA" ] || { echo "FAIL: copy hash != pin"; exit 1; }
git -C "$SRC_REPO" show "$PIN_COMMIT:docs/API.md" | cmp - "$here" || { echo "FAIL: copy != $PIN_COMMIT:docs/API.md"; exit 1; }
echo "OK: copy is byte-identical to $PIN_COMMIT:docs/API.md ($PIN_SHA)"

head_sha="$(git -C "$SRC_REPO" show HEAD:docs/API.md | sha256sum | cut -d' ' -f1)"
if [ "$head_sha" = "$PIN_SHA" ]; then echo "source HEAD matches the pin"; else
  echo "DRIFT: source HEAD $(git -C "$SRC_REPO" rev-parse --short HEAD) has docs/API.md sha256 $head_sha (pin is older; C uses none of the changed endpoints)"; fi
