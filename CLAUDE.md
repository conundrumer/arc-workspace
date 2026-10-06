# arc-workspace
- ARC-AGI-2 work for the 2026 Kaggle competition.
- Python 3.12, `uv`.

## Commands
- `uv run pytest -q`
- `uv run pyright`
- `uv run python scripts/materialize.py`
- `uv run python scripts/run_dl.py`
    - Run every Souffle solver. It takes a long time, so run it only when the user asks to run every solver.
    - `--help` for per-solver tooling.
- `uv run python scripts/run_dl.py <stem>`
    - Run one.
- Souffle binary required for `.dl` solvers (`brew install souffle`).

## Handbook
- The handbook is what a solver session reads.
- To edit a document an agent reads, send a request to the `doc-editor` agent.

## Lib
- When you work to speed up the lib, look in [Souffle: undocumented features](docs/souffle-undocumented.md) for Souffle features the official documentation leaves out.

## Solver console
- `tools/console/` is deprecated. It runs solver sessions as `claude -p` workers in staged chains.
- The module docstrings in [solver_console](tools/console/solver_console) index what each module holds: what a worker session reads and may do, how a stage hands off, and how the user reaches a session.
- Read them before answering a question about how console sessions run.
- A running server re-execs itself when `server.py` or a module under `solver_console/` changes, at its next quiet moment (`solver_console/reload.py`), so a code change needs no restart.
- The page and `ui/` are served from disk on each request.

## Tickets
- `tickets/` is the ticket tracker, which holds the tickets agents file, and [Ticket notes](prompts/agents/notes/tickets.md) states its conventions.

## Decisions
- When the user talks with you and you run no solver pass, read [Decision notes](prompts/agents/notes/decisions.md) before you make a decision on the solver tools or the agents' documents.

## Changes
- Before you launch an agent, read [Launching notes](prompts/agents/notes/launching.md).
- When the user talks with you and you run no solver pass, read [Changes](prompts/agents/notes/changes.md#changes) before you change the code or the documents.
- When the user talks with you and an operator of yours runs, file each change as a `change` ticket in place of running it.

## Worktrees
- When the user talks with you, and an environment update gives as your primary working directory another agent's worktree or the harness refuses your Bash calls in one, act by [Re-invoked in another agent's worktree](prompts/agents/notes/worktree.md#re-invoked-in-another-agents-worktree).

## Reports to the user
- When the user talks with you and an operator of yours runs, and you report to the user an agent's message, a completion notification or an event the harness reports that reached you meanwhile, open that report with a bold label that gives the agent the message is from or the notification concerns, by the full name of its kind and whether it is yours or an operator's, or the harness for an event it reports, and the route by which what you report reached you. Give no agent by its id.

## Cards
- When the user requests a card to help make a decision regarding a solver, send a handbook agent and tell it to make one based on [card_spec.py](src/study/card_spec.py).

## Conventions
- **Patches are the source of truth** for corrections.
    - `data/tasks/` regenerates from them via `scripts/materialize.py`.
    - Upstream is pinned via submodules, and corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **A grid is drawn as a grid**, wherever one is written: one row per line, cells separated by spaces, 0 as `0`.

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
