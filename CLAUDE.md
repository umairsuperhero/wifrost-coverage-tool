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

## Deployment & Production Testing Protocol

1. **Never leave changes hanging**: If a user asks to implement a feature or fix a bug, and you complete the local changes, you must immediately `git add`, `git commit -m "..."`, and `git push origin main`.
2. **Verify Production Deployment**: After pushing, you must wait for the CI/CD pipeline (e.g. Vercel, Cloud Run) to complete and then explicitly verify that the changes are live on the production domain before claiming the task is complete.
3. **Report Status**: Do not say "it is updated" until you have confirmed the push was successful and the production environment reflects the changes.
