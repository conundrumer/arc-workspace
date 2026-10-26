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
    * comment: The user's words, session 58147d46, 2026-10-26T20:03:17Z: "if a test is for in-progress, it cannot gate anything".
    - It runs only the checks of in-progress features, which fail on purpose and gate nothing.
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
- Run each heavy command as `<checkout>/scripts/run_heavy.py [--cpus <n>] [--need now|soon|idle] [--minutes <m>] [--wait <seconds>] <command> [<arg> ...]`, with `<checkout>` the checkout you work in. Run a command of several simple commands through it as `bash -c '<commands>'`.
    - `--cpus` is the processes or threads the command runs at once (default 1). Give it where the command runs more than one.
    - `--need` is who waits on the result. `now`: someone waits for it before the next step can start. `soon` (default): the result feeds the next step, and nothing sits idle for it. `idle`: nothing waits on it.
    * comment: The user's words, session 5954de00, 2026-10-26T15:16:09Z: "it depends!! \"merge\" might need to be high prio based on a needed feature, or low prio if it's not loadbearing." Request 24-1. Each of the four sessions reported it has no priority ranking.
    - `--minutes` is the time the command is to run (default 5).
    - The time `run_heavy.py` waits for its share counts toward the Bash call's timeout, so give `--wait <seconds>` under that timeout: the call then gives up with exit 125 and its expected start. Run a heavy command in the background where its wait and its run time together may pass that timeout.
    * comment: Lead's message in session 5954de00, 2026-10-26: "Twice an agent's command timed out while still waiting and never ran." Request 24-1.
    - `<checkout>/scripts/run_heavy.py queue` prints the jobs that hold a share, the processes of sessions that run outside `run_heavy.py` and count against the budget, and each waiting call with its expected start.
    * comment: Request 24-1. Lead and Alt-lead each reported an agent's command that timed out while it still waited for shares, and without the expected start a caller waits blind.
- Where a command starts several heavy processes that you can start one by one, run each of them through `run_heavy.py` in place of the whole command; otherwise run the whole command through it.
