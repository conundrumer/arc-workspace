+ budget: 1300
* comment: when editing this doc
    - Readers: each Claude Code session on the repo and each agent launched in one, by the link of [arc-workspace](CLAUDE.md), before it answers a question about how console sessions run or changes the console.
    - Acts, each with its section:
        - Answering a question about console sessions, and changing the console: [Solver console](#solver-console).

# Solver console notes
- The statements on the solver console that [arc-workspace](CLAUDE.md) links.

## Solver console
- `tools/console/` runs solver sessions as `claude -p` workers in staged chains.
- Before you answer a question about how console sessions run, read the module docstrings in [solver_console](tools/console/solver_console), which index what each module holds: what a worker session reads and may do, how a stage hands off, and how the user reaches a session.
- A running server re-execs itself when `server.py` or a module under `solver_console/` changes, at its next quiet moment (`solver_console/reload.py`), so a code change needs no restart.
- The page and `ui/` are served from disk on each request.
