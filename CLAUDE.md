# arc-workspace
- ARC-AGI-2 work for the 2026 Kaggle competition.
- Python 3.12, `uv`.

## Commands
- `uv run pytest -q`
- `uv run python scripts/materialize.py`
- `uv run python scripts/run_dl.py`
    - Run all Souffle solvers; `--help` for per-solver tooling.
- `uv run python scripts/run_dl.py <stem>`
    - Run one.
- `uv run python scripts/context.py`
    - The solver session's entry document: the handbook, and the passes it runs.
- `uv run python scripts/context.py --write`
    - Generate the files used by handbook readers.
- `uv run python -m controlled_markdown check`
    - Check the agent-facing documents.
- Souffle binary required for `.dl` solvers (`brew install souffle`).

## Handbook
- The handbook is what a solver session reads.
- [Editing the agent-facing documents](docs/handbook/editing.md) says what it is made of and how it is edited.

## Solver console
- `tools/console/` runs solver sessions as `claude -p` workers in staged chains.
- The module docstrings in [solver_console](tools/console/solver_console) index what each module holds: what a worker session reads and may do, how a stage hands off, and how the user reaches a session.
- Read them before answering a question about how console sessions run.
- A running server re-execs itself when `server.py` or a module under `solver_console/` changes, at its next quiet moment (`solver_console/reload.py`), so a code change needs no restart.
- The page and `ui/` are served from disk on each request.

## Cards
- When the user requests a card to help make a decision regarding a solver, send a handbook agent and tell it to make one based on [card_spec.py](src/study/card_spec.py).

## Conventions
- **Patches are the source of truth** for corrections.
    - `data/tasks/` regenerates from them via `scripts/materialize.py`.
    - Upstream is pinned via submodules, and corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **A grid is drawn as a grid**, wherever one is written: one row per line, cells separated by spaces, background as `.`.

## Tests
- A test costs an edit each time the code it pins changes, and a later session pays it.
- So the default is no test, and a test has to earn its place.
- Before you write one, ask: if this broke, what would a run show?
- When a run would show it (a wrong grid, a failed command, a changed line on the page or in the feed), the run is the check, and the test is not written.
- A test stays only when the failure would be silent in use, like a race, a half-written file, a lost edit, or a parser of an external format that accepts the wrong input.
- Ask the same of a test your change broke.
- When a run would show what it guards, delete it; don't update it.
- Assertions you need while you work go under `tests/scratch/`.
- It is collected and not committed.

## Codex
- Codex already has the handbook in context.
- When using Codex for prose editing tasks, the purpose is to avoid the prose being in your register, so ensure Codex uses its own words and does not copy yours.
- When specifying an issue in prose to fix, also specify the span the fix may change.
