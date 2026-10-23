---
name: session
description: Deprecated. On user ask, bootstrap a solver session for arc-workspace.
argument-hint: [solver|<task_id>]
---

# Session
- First, when the handbook is not in your system prompt, read the output of `uv run python scripts/context.py` in full.
- Read the file itself when the work is on the doc.
- Then dispatch on `$ARGUMENTS`:
    - `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the creation pass.
    - a task id — work that solver per the creation pass.
    - anything else — an ordinary working request; proceed with the docs as context.
        - A solver session is declared by keyword, never inferred from prose.

## Entry
- `uv run python scripts/context.py --write` writes the agents, and `scripts/claude.py` does that before it starts `claude`.
- `claude` registers the agent files at its start only, so a session cannot write them for itself.
- When one is missing, say so before any spawn.
- Read the lib before writing or editing a solver, as the handbook renders it.
- When a lib relation's interface leaves the semantics open, read its body in the module.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver and its estimated complexity.

## `next`
- User trigger to advance to the next solver.
- No advance without it.
- Clear all completed tasks before advancing.
