#!/usr/bin/env bash
# Stop hook (Layer 3) — verify-stop.sh
#
# Runs before Claude is allowed to end a session/turn. It executes the offline
# backend smoke test (imports + grid kernel) so "imports OK / it builds / done"
# cannot be claimed without proof. Exit code 2 blocks the stop and shows the
# failure to Claude. The stop_hook_active guard prevents infinite re-trigger loops.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
input="$(cat 2>/dev/null || true)"

# Already blocked once this turn -> let the session stop to avoid a loop.
if [ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
  exit 0
fi

py="$ROOT/venv/bin/python"
[ -x "$py" ] || py="$(command -v python3 || command -v python || true)"
[ -n "$py" ] || exit 0
[ -f "$ROOT/test_smoke.py" ] || exit 0

if ! out="$( (cd "$ROOT" && "$py" test_smoke.py 2>&1) )"; then
  {
    echo "BLOCKED by verify-stop hook: backend smoke test FAILED."
    echo "Do not claim the work is done. Address this first:"
    printf '%s\n' "$out" | tail -25
  } >&2
  exit 2
fi
exit 0
