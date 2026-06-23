## Honesty rules (read every turn)

Before claiming a function, class, or import exists, verify it by reading the file or running a grep. Never fabricate symbols.

If you cannot verify something, say "I haven't verified this" explicitly.
Do not write code that depends on the unverified claim.

If a task asks you to use a library you've never seen referenced in this project, ask before adding it.

If a task involved tests or builds, do not claim success unless you actually ran the test or build command in this session.

Never invent error messages, API responses, or stack traces. If you didn't see them, say so.

When you genuinely don't know, the correct answer is "I don't know" or "I need to check first." Both are better than a confident guess.

## Verification protocol

Before writing or editing code that uses a symbol (function, class, type, constant), do one of:

1. Read the file where it's defined and confirm the signature
2. Run `grep -r "symbolName" .` or use the Glob tool to find it
3. Check package.json, requirements.txt, Cargo.toml, or equivalent for the dependency

If you skip verification, prefix the code with a comment:
`// UNVERIFIED: I have not confirmed this symbol exists`

Plan-then-execute mode is preferred for any task touching more than one file. Use Shift+Tab to enter plan mode before starting.

## Automated verification (Layer 3 — enforced by hooks)

These run automatically; do not disable them to make a task "pass".

- **PostToolUse** → `.claude/hooks/verify-edit.sh`: every `.py` write is `py_compile`d and every `.ts/.tsx` write is type-checked with the frontend's `tsc --noEmit`. A fabricated import or symbol fails here immediately (exit 2 blocks and shows the error). Fix it before continuing — do not work around it.
- **Stop** → `.claude/hooks/verify-stop.sh`: runs the offline `test_smoke.py` (imports + grid kernel) before a session can end, so "imports OK / it builds / done" cannot be claimed without proof.
- **fact-checker subagent** → `.claude/agents/fact-checker.md`: invoke it before any commit and before any user-facing "done" summary to independently re-verify claims.

When you add a new top-level Python module or a critical import path, extend `test_smoke.py` so the Stop hook guards it (this is the exact class of bug that broke `okumura_hata`).

## Branch & Deployment Protocol

This repo runs **two separate tracks. Keep them separate** until the owner says otherwise.

- **Production (live, frozen):** the `main` branch and its deployed environments (Vercel / Render / Cloud Run). It serves the current shipped UI/backend. **Do not push to `main`, merge into it, or trigger a production deploy** as part of feature work.
- **New UI / functionality (active dev):** the `feature/spatial-glass-maplibre` branch (Next.js + FastAPI, ITM Longley-Rice). All new work happens here and is validated independently of production.

Rules:
1. Commit and push feature work to the **feature branch only**: `git push origin feature/spatial-glass-maplibre`. Never `git push origin main` and never merge to `main` without an explicit instruction from the owner.
2. Do not deploy feature work to a production domain. The new UI stays separate until the owner is happy with it.
3. **Never leave changes hanging**: when you complete local changes, `git add` / `git commit` / push to the **feature branch**, and keep `CHANGELOG.md` updated.
4. **Report status honestly**: "updated" means committed and pushed to the feature branch **and** the Stop-hook smoke test passed — always state which branch. Do not claim a production domain reflects the change unless you actually verified it (and you should not be deploying to production during feature work anyway).
