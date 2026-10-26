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
- Run each heavy command as `<checkout>/scripts/ram_slot.py <command> [<arg> ...]`, with `<checkout>` the checkout you work in. Run a command of several simple commands as `<checkout>/scripts/ram_slot.py bash -c '<commands>'`.
    - `ram_slot.py` starts the command once it holds a slot, the swap in use is at most 2 GiB, the 1-minute load average is at most twice the core count, and the memory `vm_stat` gives as free or inactive is at least 6 GiB. A command that runs under another `ram_slot.py` call waits for none of these.
    - The time `ram_slot.py` waits for a slot, for swap, for load or for memory counts toward the Bash call's timeout, so run a heavy command in the background where that wait and its run time together may pass that timeout.
- Where a command starts several heavy processes that you can start one by one, run each of them through `ram_slot.py` in place of the whole command; otherwise run the whole command through it.
