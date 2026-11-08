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
- `scripts/engine_build.sh SHA NAME [PART...]`, through `scripts/run_heavy.py`
    - Build an engine build from a commit, in the one shared build checkout and target folder, so only the crates a commit changes recompile. Its header names the parts and the folders.

## Large data
* comment: The user's words, session 12a37de8, 2026-11-06: "All large data from all agents must be in compressed stream format always".
- Write all large data as streamable zstd from the start, with no uncompressed intermediate. This holds in a scratchpad too.

## Commands that use much memory
* comment: The user's words, session 64993706, 2026-10-26T01:38:48Z: "multiple claude sessions using up RAM resulted in OOM: feels like a known problem with a known solution, help me manage this".
- A command is heavy where it may use much memory, or where it starts several processes at once.
    - Where you do not know, count the command heavy.
- Run each heavy command as `<checkout>/scripts/run_heavy.py [--cpus <n>] [--need now|soon|idle] <command> [<arg> ...]`, with `<checkout>` the checkout you work in. Run a command of several simple commands through it as `bash -c '<commands>'`.
    - Every call starts at once.
    - `--cpus` is the processes or threads the command runs at once (default 1). Give it where the command runs more than one.
    - `--need` is who waits on the result, and sets the nice value of the command, which each process it starts inherits. `now`: someone waits for it before the next step can start, nice value 0. `soon` (default): the result feeds the next step, and nothing sits idle for it, 5. `idle`: nothing waits on it, 15.
    * comment: The user's words, session 5954de00, 2026-10-26T15:16:09Z: "it depends!! \"merge\" might need to be high prio based on a needed feature, or low prio if it's not loadbearing." Request 24-1. Each of the four sessions reported it has no priority ranking.
    * comment: The user's words, session 5954de00, 2026-10-26T22:34:10Z: "go", which approved the proposal of 22:31:46Z that has `run_heavy.py` accept `--minutes` and `--wait` and ignore them as it does `--gib`, give `now` nice 0, `soon` nice 5 and `idle` nice 15, and add `need <pid> <tier>`. Request 24-33.
    - `--gib`, `--minutes` and `--wait` are accepted and have no effect.
    * comment: The user's words, session 5954de00, 2026-10-26T22:34:10Z: "go", which approved the proposal of 22:31:46Z that has this line. Request 24-33.
    - `<checkout>/scripts/run_heavy.py queue` prints the running jobs with their need and the processes that sessions run outside `run_heavy.py` and that count against the machine.
    - `<checkout>/scripts/run_heavy.py need <pid> now|soon|idle` changes the nice value of a running job's processes. A user cannot lower a nice value, so only raising it works (for example `soon` to `idle`). Where the system refuses it says so and exits 125.
    * comment: The user's words, session 5954de00, 2026-10-26T22:34:10Z: "go", which approved the proposal of 22:31:46Z that has this line. Request 24-33.
    - A job that runs at `now` for 10 minutes or more becomes `soon`: the daemon raises its nice value as `need <pid> soon` does, `queue` shows `soon`, and the session gets one message. A Bash call waits at most 10 minutes, so no call waits on such a job. Start a run that may take that long with `--need soon`.
- Where a command starts several heavy processes that you can start one by one, run each of them through `run_heavy.py` in place of the whole command; otherwise run the whole command through it.
