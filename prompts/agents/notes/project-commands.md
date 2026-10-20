+ document-size-budget: 1200
* comment: when editing this doc
    - Readers: each Claude Code session on the repo and each agent launched in one, by the link of [arc-workspace](CLAUDE.md), before it runs the tests, the type check, a solver, or `scripts/materialize.py`.
    - Acts, each with its section:
        - Running the project's commands: [Project commands](#project-commands).

# Project command notes
- The project's commands, that [arc-workspace](CLAUDE.md) links.

## Project commands
- `uv run pytest -q`
- `uv run pyright`
- `uv run python scripts/materialize.py`
- `uv run python scripts/run_dl.py`
    * comment: The user's words, session 6f8c73e4, 2026-10-02T22:45:12Z: "it needs to be known it is an expensive op".
    - Run every Souffle solver. It takes a long time, so run it only when the user asks to run every solver.
    - `--help` for per-solver tooling.
        + xref: src/cli/main.py:main
- `uv run python scripts/run_dl.py <stem>`
    - Run one.
- Souffle binary required for `.dl` solvers (`brew install souffle`).
