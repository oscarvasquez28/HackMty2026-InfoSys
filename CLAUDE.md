# CLAUDE.md

This project's agent instructions live in [`AGENTS.md`](AGENTS.md) — architecture, commands,
routing into `doc/`, code conventions, verification steps, and known gotchas. Read that file
first; it is the single source of truth. Do not fork or duplicate its content here — if something
there is stale, fix it in `AGENTS.md` directly so every agent (not just Claude Code) benefits.

This file only holds the handful of things that are specific to working in Claude Code on this
repo.

## Claude Code specifics

- **Platform**: development on this machine is Windows (PowerShell). The venv activation command
  in `AGENTS.md` (`.\venv\Scripts\activate`) and path separators are already Windows-flavored;
  don't "correct" them to POSIX syntax.
- **Long-running dev servers** (`uvicorn --reload`, `npm run dev`, `docker compose up`): start
  these with the `run` skill / Browser preview tooling rather than a blocking foreground shell
  command, so the session isn't left stuck waiting on a server that never exits.
- **`.next` lock on Windows**: if `npm run build` fails because `.next/trace` is locked, do not
  force-delete build output or kill another contributor's process — ask the user, per section 6 of
  `AGENTS.md`.
- **Frontend-only ownership boundary** (`AGENTS.md` §7): backend code, tests, services, and config
  are owned by another contributor. Default to frontend-only changes; if a task seems to require
  touching the backend, confirm with the user before editing it.
- **Before finishing a change**, run the verification steps in `AGENTS.md` §5
  (`pytest backend/tests/test_pipeline.py`, `npm run build` for TS/TSX changes) rather than
  assuming they pass.
