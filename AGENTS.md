# AGENTS.md — Hard Red Lines

Operational rules for any agent (Codex, Claude, etc.) working in this repo.
These are non-negotiable. Everything else (setup, env vars, architecture) is in `README.md`.

1. **Never run `python main.py`.** A full run pushes a live report to DingTalk. Use `--dry-run` / `--no-push` only.

2. **Use `.venv/bin/python`** for everything. System `python3` is 3.9 — too old for this 3.12 codebase and will crash at runtime.

3. **Self-test before reporting a task done.** At minimum: import/compile the modules you touched and run `.venv/bin/python -m pytest`. For scraper/analyzer changes also run the relevant `--dry-run`.

4. **Do not `git push`.** Commit locally; pushing is the human's call.

5. **Ship schema changes complete in one commit:** SQL migration + README note + a local verification command, together.
