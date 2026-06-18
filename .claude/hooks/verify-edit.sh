#!/usr/bin/env bash
# PostToolUse hook (Layer 3) — verify-edit.sh
#
# Claude Code runs this after every Write/Edit/MultiEdit. It type-/syntax-checks
# the file that was just written so a fabricated import or symbol fails IMMEDIATELY
# instead of being claimed as "done". Hook contract: the tool-call JSON arrives on
# stdin; exit code 2 feeds stderr back to Claude as a blocking error.
#
# Tooling is detected, never assumed: Python -> venv py_compile; TS/TSX -> the
# frontend's local tsc. If a tool is genuinely absent the hook skips silently
# (exit 0) rather than failing on every edit.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
input="$(cat 2>/dev/null || true)"
file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)"

[ -z "$file" ] && exit 0
[ -f "$file" ] || exit 0

case "$file" in
  *.py)
    py="$ROOT/venv/bin/python"
    [ -x "$py" ] || py="$(command -v python3 || command -v python || true)"
    [ -n "$py" ] || exit 0
    if ! out="$("$py" -m py_compile "$file" 2>&1)"; then
      {
        echo "BLOCKED by verify-edit hook: py_compile failed on $file."
        echo "Fix the syntax error before claiming this task is done:"
        printf '%s\n' "$out"
      } >&2
      exit 2
    fi
    ;;
  *.ts|*.tsx)
    tsc="$ROOT/frontend/node_modules/.bin/tsc"
    [ -x "$tsc" ] || exit 0   # frontend deps not installed -> skip
    out="$( (cd "$ROOT/frontend" && "$tsc" --noEmit --pretty false 2>&1) | grep 'error TS' | head -30 )"
    if [ -n "$out" ]; then
      {
        echo "BLOCKED by verify-edit hook: tsc --noEmit reported type errors after editing $file."
        echo "A 'Cannot find module' / 'has no exported member' here usually means a fabricated import."
        echo "Fix before claiming this task is done:"
        printf '%s\n' "$out"
      } >&2
      exit 2
    fi
    ;;
esac
exit 0
