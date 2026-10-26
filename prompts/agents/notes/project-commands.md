+ document-size-budget: 1200
* comment: when editing this doc
    - Readers: each Claude Code session on the repo and each agent launched in one, by the links of [arc-workspace](CLAUDE.md): before it runs the tests, the type check, a solver, or `scripts/materialize.py`, and before it runs a command that may use much memory or that starts several processes at once.
    - Acts, each with its section:
        - Running the project's commands: [Project commands](#project-commands).
        - Running a command that uses much memory: [Commands that use much memory](#commands-that-use-much-memory).

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

## Commands that use much memory
* comment: The user's words, session 64993706, 2026-10-26T01:38:48Z: "multiple claude sessions using up RAM resulted in OOM: feels like a known problem with a known solution, help me manage this".
- A command is heavy where it may use much memory, or where it starts several processes at once.
    - Where you do not know, count the command heavy.
- Run each heavy command as `<checkout>/scripts/run_heavy.py [--cpus <n>] [--gib <g>] <command> [<arg> ...]`, with `<checkout>` the checkout you work in. Run a command of several simple commands as `<checkout>/scripts/run_heavy.py [--cpus <n>] [--gib <g>] bash -c '<commands>'`.
    - `--cpus` is the processes or threads the command runs at once (default 1), and `--gib` the memory in GiB it may reach (default `1 + <n>`). Give each where the command runs more than one process or thread or may reach more than its default.
    - The time `run_heavy.py` waits for its share or for memory pressure counts toward the Bash call's timeout, so run a heavy command in the background where that wait and its run time together may pass that timeout.
- Where a command starts several heavy processes that you can start one by one, run each of them through `run_heavy.py` in place of the whole command; otherwise run the whole command through it.
